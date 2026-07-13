"""
Enriquecimiento automático del catálogo desde la web.

Cuando el matching fuzzy no reconoce la cervecera de una línea OCR con
confianza suficiente, en background: búsqueda web (SearxNG self-hosted,
misma filosofía que LibreTranslate) + extracción/corroboración/parafraseo
con LLM (Gemini, tier gratuito) → si el resultado
es de alta confianza se crean las fichas en PocketBase (brewery si falta,
beer siempre) con source="auto-web" y se publican sin aprobación manual.
Los estilos NUNCA se auto-crean: solo se enlazan por fuzzy a los existentes
(vocabulario controlado por admin). Si la búsqueda no es concluyente no se
publica nada a medias: el item queda "sin detectar" como hasta ahora.

Reconciliación con el escaneo: cada tarea lleva un enrichment_id (UUID) que
también viaja en la respuesta OCR. La tarea escribe su resultado en la
collection `enrichments` y además actualiza cualquier scan_item ya guardado
con ese enrichment_id; la app, al guardar, consulta `enrichments` por si el
resultado llegó primero. Así se cubren ambos órdenes de llegada.

LIMITACIÓN MVP (deliberada): esto corre como BackgroundTask nativa de
FastAPI, sin cola de trabajos. Si el proceso se reinicia a mitad de una
búsqueda, esa tarea se pierde SIN reintento. Aceptable con el volumen
actual; si el volumen de escaneos crece, migrar a una cola real (Redis/
arq, Celery...) con reintentos y persistencia.
"""
import asyncio
import html
import json
import logging
import re
import unicodedata

import httpx

from .config import (
    ENRICH_ENABLED,
    ENRICH_MIN_CONFIDENCE,
    GEMINI_API_KEY,
    GEMINI_MODEL,
    MATCH_THRESHOLD,
    PB_SERVICE_EMAIL,
    PB_SERVICE_PASSWORD,
    POCKETBASE_URL,
    SEARXNG_URL,
)
from .dictionary import BRAND_SUFFIXES, get_dictionaries
from .matching import _best_match, beer_candidates
from .schemas import ScanItem

log = logging.getLogger("beerwalk.enrichment")

USER_AGENT = "BeerWalkBot/0.1 (+https://beerwalk.app; enriquecimiento de catalogo)"
MAX_PAGES_TO_FETCH = 3
MAX_PAGE_CHARS = 6000

# Dedupe de tareas en vuelo: evita que 6 líneas de la misma cervecera
# desconocida en una pizarra (o dos escaneos casi simultáneos) disparen
# tareas paralelas que crearían fichas duplicadas.
_in_flight: set[str] = set()
_in_flight_lock = asyncio.Lock()


def enrichment_configured() -> bool:
    # La búsqueda (SearxNG propio) no necesita key; el LLM y PocketBase sí.
    return ENRICH_ENABLED and bool(GEMINI_API_KEY and PB_SERVICE_EMAIL)


def should_enrich(item: ScanItem) -> bool:
    """Un bloque es candidato si se leyó con confianza, NO está ya en el
    catálogo `beers`, y su cervecera no tiene ficha enlazada. Los bloques de
    Vision con cervecera nombrada pero sin id (id=None) SÍ son candidatos:
    son nombres limpios ideales para crear la ficha — y cada ficha creada
    reduce la necesidad de Vision en escaneos futuros."""
    if item.confidence < ENRICH_MIN_CONFIDENCE:
        return False
    if item.beer is not None:  # ya está en el catálogo
        return False
    if item.brewery is not None and item.brewery.id is not None:
        return False
    text = (item.beer_name or item.line or "").strip()
    return len(text) >= 4


def _normalize_key(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    return re.sub(r"[^a-z0-9 ]", "", text).strip()


def _strip_html(raw: str) -> str:
    """Reducción cruda de HTML a texto para dárselo al LLM. No pretende ser
    un parser correcto; suficiente como contexto de extracción."""
    raw = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", raw)
    raw = re.sub(r"(?s)<[^>]+>", " ", raw)
    return re.sub(r"\s+", " ", html.unescape(raw)).strip()


# ── Fuentes externas ─────────────────────────────────────────────────────


async def _searx_search(client: httpx.AsyncClient, query: str) -> list[dict]:
    """Búsqueda contra la instancia SearxNG propia. Requiere que settings.yml
    de la instancia incluya "json" en search.formats (si no, responde 403)."""
    r = await client.get(
        f"{SEARXNG_URL}/search",
        params={"q": query, "format": "json"},
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    r.raise_for_status()
    results = r.json().get("results", [])
    return [
        {"title": x.get("title", ""), "url": x.get("url", ""), "description": x.get("content", "")}
        for x in results[:5]
    ]


async def _fetch_pages(client: httpx.AsyncClient, urls: list[str]) -> list[dict]:
    """Descarga las primeras páginas de resultados (UA identificado, timeout
    corto, texto truncado). Errores individuales se ignoran: son solo
    contexto adicional para el LLM."""
    pages = []
    for url in urls[:MAX_PAGES_TO_FETCH]:
        if not url.startswith(("http://", "https://")):
            continue
        try:
            r = await client.get(url, headers={"User-Agent": USER_AGENT}, follow_redirects=True)
            if r.status_code == 200 and "text/html" in r.headers.get("content-type", ""):
                pages.append({"url": url, "text": _strip_html(r.text)[:MAX_PAGE_CHARS]})
        except httpx.HTTPError:
            continue
    return pages


def _clean_for_search(text: str) -> str:
    """Quita precios, porcentajes y números sueltos ("4,50 6,00 5%") que
    arruinan las búsquedas web; deja solo los tokens con letras."""
    tokens = [t for t in text.split() if re.search(r"[a-zA-ZÀ-ÿ]{2,}", t)]
    return " ".join(tokens) or text


# Paso 0 del flujo cervecera-primero: HIPÓTESIS de marca. El texto OCR llega
# tan destrozado ("Aymgar") que los buscadores devuelven 0 resultados con él;
# un LLM sí sabe qué marca real se parece, y la búsqueda pasa a ser
# CONFIRMACIÓN de la hipótesis en vez de adivinación a ciegas.
_BREWERY_GUESS_PROMPT = """Texto detectado por OCR en la pizarra de un bar de cervezas artesanas.
Suele contener el nombre de una cervecera real, posiblemente con errores
graves de OCR (letras cambiadas, ej. "Aymgar" → "Ayinger").

Texto OCR: {line}

Devuelve JSON: {{"candidates": [str]}} — hasta 3 nombres de CERVECERAS REALES
que podrían corresponder a este texto, ordenadas de más a menos probable.
Solo marcas que existan de verdad; si nada encaja, lista vacía."""

# Paso 1: identificar/confirmar la MARCA con evidencia web. Reducir el
# espacio de búsqueda a una cervecera confirmada mejora mucho la precisión
# del paso 2 (la cerveza concreta dentro de lo que esa marca produce).
_BREWERY_PROMPT = """Eres un verificador de datos de cerveceras artesanas para un catálogo.

Texto detectado por OCR en la pizarra de un bar (puede tener errores graves
de OCR, ej. "Aymgar" en vez de "Ayinger"):
{line}

Resultados de búsqueda web:
{search_results}

Extractos de las páginas:
{pages}

Devuelve JSON con este esquema exacto:
{{
  "found": bool,            // true SOLO si identificas con claridad una cervecera REAL
  "brewery_name": str|null, // nombre canónico real de la cervecera
  "origin": str|null,       // ciudad/región y país, ej. "Aying, Alemania"
  "description_es": str|null, // 2-3 frases en español: perfil (artesanal/industrial),
                              // origen y mención breve de qué otras cervezas produce.
                              // PARAFRASEADO CON TUS PROPIAS PALABRAS, prohibido
                              // copiar frases literales de las fuentes.
  "source_url": str|null    // la URL más fiable (ideal: web oficial de la marca)
}}

Sé estricto: ante ambigüedad devuelve found=false."""

# Paso 2: la cerveza CONCRETA, con la búsqueda ya acotada a la marca.
_BEER_PROMPT = """Eres un verificador de datos de cervezas artesanas para un catálogo.

Cervecera CONFIRMADA: {brewery}
Texto detectado por OCR junto a la cervecera (puede tener errores, y puede
ser el NOMBRE de la cerveza o un DESCRIPTOR de estilo en castellano/catalán,
ej. "BLAT" = trigo → la cerveza de trigo de esa marca): {beer_hint}

Resultados de búsqueda web (acotada a esa cervecera):
{search_results}

Extractos de las páginas:
{pages}

Estilos existentes en el catálogo (SOLO puedes usar uno de estos, o null):
{styles}

Devuelve JSON con este esquema exacto:
{{
  "found": bool,          // true SOLO si identificas una cerveza real de ESA cervecera
  "corroborated": bool,   // true si lo confirman ≥2 fuentes independientes O la web oficial
  "beer_name": str|null,  // nombre comercial real de la cerveza
  "style_name": str|null, // EXACTAMENTE uno de los estilos del catálogo, o null
  "abv": float|null,
  "description_es": str|null,    // 1-2 frases en español: reseña general de la cerveza.
                                 // PARAFRASEADO, nunca copiado literal.
  "tasting_notes_es": str|null,  // notas de cata específicas (aroma, sabor, cuerpo),
                                 // distintas de la descripción. PARAFRASEADO.
  "source_url": str|null
}}

Sé estricto: si hay ambigüedad o solo una fuente débil, found=false.
Es mejor no crear la ficha que crearla mal."""


async def _llm_json(client: httpx.AsyncClient, prompt: str) -> dict | None:
    for attempt in range(3):
        r = await client.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent",
            params={"key": GEMINI_API_KEY},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"responseMimeType": "application/json", "temperature": 0.1},
            },
        )
        if r.status_code in (429, 500, 503) and attempt < 2:
            if r.status_code == 429:
                # Cuota por minuto del tier gratuito: espera larga (somos una
                # background task, la latencia no molesta a nadie)
                retry_after = int(r.headers.get("retry-after") or 0)
                await asyncio.sleep(max(retry_after, 30))
            else:
                await asyncio.sleep(2 * (attempt + 1))  # 5xx transitorios
            continue
        break
    r.raise_for_status()
    try:
        # Gemini 3.5 puede intercalar parts de razonamiento ({"thought": true})
        # antes de la respuesta: quedarnos solo con los parts de respuesta.
        parts = r.json()["candidates"][0]["content"]["parts"]
        text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
        return json.loads(text)
    except (KeyError, IndexError, json.JSONDecodeError):
        return None


# ── PocketBase (escrituras como superusuario) ────────────────────────────


async def _pb_auth(client: httpx.AsyncClient) -> str:
    r = await client.post(
        f"{POCKETBASE_URL}/api/collections/_superusers/auth-with-password",
        json={"identity": PB_SERVICE_EMAIL, "password": PB_SERVICE_PASSWORD},
    )
    r.raise_for_status()
    return r.json()["token"]


def _pb_filter_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


async def _pb_create(client: httpx.AsyncClient, token: str, collection: str, body: dict) -> dict:
    r = await client.post(
        f"{POCKETBASE_URL}/api/collections/{collection}/records",
        json=body,
        headers={"Authorization": token},
    )
    r.raise_for_status()
    return r.json()


async def _pb_get(client: httpx.AsyncClient, token: str, collection: str, record_id: str) -> dict:
    r = await client.get(
        f"{POCKETBASE_URL}/api/collections/{collection}/records/{record_id}",
        headers={"Authorization": token},
    )
    r.raise_for_status()
    return r.json()


async def _pb_patch(client: httpx.AsyncClient, token: str, collection: str, record_id: str, body: dict) -> dict:
    r = await client.patch(
        f"{POCKETBASE_URL}/api/collections/{collection}/records/{record_id}",
        json=body,
        headers={"Authorization": token},
    )
    r.raise_for_status()
    return r.json()


async def _pb_find_first(client: httpx.AsyncClient, token: str, collection: str, filter_expr: str) -> dict | None:
    r = await client.get(
        f"{POCKETBASE_URL}/api/collections/{collection}/records",
        params={"filter": filter_expr, "perPage": 1},
        headers={"Authorization": token},
    )
    r.raise_for_status()
    items = r.json().get("items", [])
    return items[0] if items else None


async def _reconcile_scan_items(
    client: httpx.AsyncClient, token: str, enrichment_id: str, patch: dict
) -> None:
    """Actualiza los scan_items ya guardados que llevan este enrichment_id.
    Si el usuario aún no ha guardado, no habrá ninguno: la app enlazará ella
    misma consultando `enrichments` en el momento de guardar."""
    r = await client.get(
        f"{POCKETBASE_URL}/api/collections/scan_items/records",
        params={"filter": f'enrichment_id = "{_pb_filter_escape(enrichment_id)}"', "perPage": 50},
        headers={"Authorization": token},
    )
    r.raise_for_status()
    for record in r.json().get("items", []):
        await client.patch(
            f"{POCKETBASE_URL}/api/collections/scan_items/records/{record['id']}",
            json=patch,
            headers={"Authorization": token},
        )


# ── Tarea principal ──────────────────────────────────────────────────────


async def _set_enrichment(
    client: httpx.AsyncClient, token: str, enrichment_id: str, fields: dict
) -> dict:
    """Upsert del registro `enrichments` de esta tarea. La tarea escribe
    `pending` nada más arrancar (la app lo muestra en vivo vía realtime) y
    el resultado final PATCHea ese mismo registro — nunca hay dos filas para
    un mismo enrichment_id."""
    existing = await _pb_find_first(
        client, token, "enrichments",
        f'enrichment_id = "{_pb_filter_escape(enrichment_id)}"',
    )
    if existing:
        return await _pb_patch(client, token, "enrichments", existing["id"], fields)
    return await _pb_create(
        client, token, "enrichments", {"enrichment_id": enrichment_id, **fields}
    )


async def enrich_item(enrichment_id: str, line: str, beer_name_hint: str | None) -> None:
    """Background task: busca la línea en la web y, con corroboración clara,
    publica brewery (si falta) + beer en PocketBase y deja el resultado en
    `enrichments`. Cualquier fallo deja el item como estaba (sin detectar)."""
    key = _normalize_key(beer_name_hint or line)
    async with _in_flight_lock:
        if key in _in_flight:
            return
        _in_flight.add(key)
    try:
        # Señal inmediata de "trabajando en ello" para la UI (Bloque 4). Si
        # este write falla, la tarea sigue: el estado es cosmético, el
        # resultado no.
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                token = await _pb_auth(client)
                await _set_enrichment(client, token, enrichment_id, {"status": "pending"})
        except Exception:
            log.warning("enrichment %s: no se pudo escribir el estado pending", enrichment_id)
        await _enrich_item_inner(enrichment_id, line, beer_name_hint)
    except Exception:
        log.exception("enrichment %s failed", enrichment_id)
        # Best effort: dejar rastro del fallo para auditoría
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                token = await _pb_auth(client)
                await _set_enrichment(client, token, enrichment_id, {"status": "error"})
        except Exception:
            pass
    finally:
        async with _in_flight_lock:
            _in_flight.discard(key)


async def _resolve_brewery(
    client: httpx.AsyncClient, token: str, line: str, breweries: dict[str, str]
) -> tuple[str, str] | None:
    """PASO 1 (cervecera primero): devuelve (brewery_id, nombre_canonico) o
    None si no se puede confirmar ninguna cervecera real.

    - Ficha existente CON description → se usa tal cual, sin gastar búsqueda.
    - Ficha existente SIN description → se busca solo para completarla.
    - Sin ficha → búsqueda web + creación con description parafraseada."""
    matched = _best_match(line, breweries)
    record: dict | None = None
    if matched and matched.id:
        record = await _pb_get(client, token, "breweries", matched.id)
        if record.get("description"):
            return record["id"], record["name"]

    clean = _clean_for_search(line)

    # Paso 0: hipótesis de marca (el OCR garbled da 0 resultados en buscadores)
    guess = await _llm_json(client, _BREWERY_GUESS_PROMPT.format(line=clean))
    candidates = [c for c in (guess or {}).get("candidates", []) if isinstance(c, str) and c.strip()]

    # Buscar: primero las hipótesis (nombres reales → resultados reales),
    # después el texto crudo limpio como último recurso
    search_results: list[dict] = []
    for query in [f'cervecera "{c}" brewery beer' for c in candidates[:2]] + [f"{clean} cerveza"]:
        search_results = await _searx_search(client, query)
        if search_results:
            break
    pages = await _fetch_pages(client, [x["url"] for x in search_results])
    data = await _llm_json(client, _BREWERY_PROMPT.format(
        line=f"{clean} (hipótesis a verificar: {', '.join(candidates) or 'ninguna'})",
        search_results=json.dumps(search_results, ensure_ascii=False, indent=1),
        pages=json.dumps(pages, ensure_ascii=False, indent=1),
    ))
    if not data or not data.get("found") or not data.get("brewery_name"):
        # Si al menos hay ficha (aunque incompleta), seguimos con ella
        return (record["id"], record["name"]) if record else None

    # ¿El nombre confirmado coincide con una ficha existente distinta?
    if record is None:
        matched = _best_match(data["brewery_name"], breweries)
        if matched and matched.id:
            record = await _pb_get(client, token, "breweries", matched.id)

    if record:
        # Completar los huecos de la ficha existente (sin pisar lo que ya hay)
        patch = {
            k: v for k, v in {
                "description": data.get("description_es"),
                "origin": data.get("origin"),
                "source_url": data.get("source_url"),
            }.items() if v and not record.get(k)
        }
        if patch:
            record = await _pb_patch(client, token, "breweries", record["id"], patch)
        return record["id"], record["name"]

    created = await _pb_create(
        client, token, "breweries",
        {
            "name": data["brewery_name"],
            "origin": data.get("origin") or "",
            "description": data.get("description_es") or "",
            "source": "auto-web",
            "source_url": data.get("source_url") or "",
            "verified": False,
        },
    )
    return created["id"], created["name"]


async def _enrich_item_inner(enrichment_id: str, line: str, beer_hint: str | None) -> None:
    async with httpx.AsyncClient(timeout=20) as client:
        token = await _pb_auth(client)
        breweries, styles, beers_idx = await get_dictionaries(force_refresh=True)

        # ── PASO 1: resolver la CERVECERA ────────────────────────────────
        resolved = await _resolve_brewery(client, token, line, breweries)
        if not resolved:
            await _set_enrichment(
                client, token, enrichment_id,
                {"status": "no_match", "detail": "cervecera no confirmada"},
            )
            return
        brewery_id, brewery_name = resolved

        # ── PASO 2: la cerveza CONCRETA, acotada a la marca confirmada ───
        hint = _clean_for_search(beer_hint or line)
        # Marca corta para buscar: "Ayinger Privatbrauerei" rinde peor que
        # "Ayinger" (la gente escribe la marca, no la razón social)
        brand_tokens = [t for t in brewery_name.split() if t.lower().strip(".") not in BRAND_SUFFIXES]
        brand = " ".join(brand_tokens[:2]) or brewery_name
        # Dos consultas complementarias, resultados fusionados sin duplicar
        seen_urls: set[str] = set()
        search_results = []
        for q in (f"{brand} {hint} cerveza", f"{brand} {hint} beer style"):
            for res in await _searx_search(client, q):
                if res["url"] not in seen_urls:
                    seen_urls.add(res["url"])
                    search_results.append(res)
        search_results = search_results[:6]
        pages = await _fetch_pages(client, [x["url"] for x in search_results])
        data = await _llm_json(client, _BEER_PROMPT.format(
            brewery=brewery_name,
            beer_hint=hint,
            search_results=json.dumps(search_results, ensure_ascii=False, indent=1),
            pages=json.dumps(pages, ensure_ascii=False, indent=1),
            styles=json.dumps(sorted(styles.keys()), ensure_ascii=False),
        ))
        if not data or not data.get("found") or not data.get("corroborated") or not data.get("beer_name"):
            await _set_enrichment(
                client, token, enrichment_id,
                {"status": "no_match",
                 "detail": f"cerveza no corroborada (cervecera: {brewery_name})"},
            )
            return

        # Estilo: SOLO enlazar a existentes (vocabulario controlado)
        style_id: str | None = None
        if data.get("style_name"):
            matched = _best_match(data["style_name"], styles)
            if matched and matched.score >= MATCH_THRESHOLD:
                style_id = matched.id

        # Beer: idempotente — si existe, completar huecos; si no, crear
        name_esc = _pb_filter_escape(data["beer_name"])
        fields = {
            **({"style": style_id} if style_id else {}),
            **({"abv": data["abv"]} if isinstance(data.get("abv"), (int, float)) else {}),
            "description": data.get("description_es") or "",
            "tasting_notes": data.get("tasting_notes_es") or "",
            "source_url": data.get("source_url") or "",
        }
        existing = await _pb_find_first(
            client, token, "beers", f'name = "{name_esc}" && brewery = "{brewery_id}"'
        )
        if not existing:
            # Dedupe fuzzy: el LLM varía el naming ("Bräuweisse" vs "Ayinger
            # Bräuweisse") — si ya hay una beer parecida de ESTA cervecera,
            # completarla en vez de crear una casi-duplicada
            same_brewery = {
                name: rec["id"]
                for name, rec in beer_candidates(beers_idx, brewery_id).items()
            }
            fuzzy = _best_match(data["beer_name"], same_brewery)
            if fuzzy and fuzzy.id:
                existing = await _pb_get(client, token, "beers", fuzzy.id)
        if existing:
            patch = {k: v for k, v in fields.items() if v and not existing.get(k)}
            beer = await _pb_patch(client, token, "beers", existing["id"], patch) if patch else existing
        else:
            beer = await _pb_create(
                client, token, "beers",
                {"name": data["beer_name"], "brewery": brewery_id, "source": "auto-web", **fields},
            )

        await _set_enrichment(
            client, token, enrichment_id, {"status": "created", "beer": beer["id"]},
        )
        await _reconcile_scan_items(
            client, token, enrichment_id,
            {"beer": beer["id"], "brewery": brewery_id, **({"style": style_id} if style_id else {})},
        )
        # Que el diccionario en memoria conozca la nueva cervecera/beer ya mismo
        await get_dictionaries(force_refresh=True)
        log.info("enrichment %s -> beer %s (%s · %s)", enrichment_id, beer["id"], brewery_name, data["beer_name"])
