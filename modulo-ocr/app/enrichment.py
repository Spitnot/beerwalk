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
from .dictionary import get_dictionaries
from .matching import _best_match
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


_EXTRACTION_PROMPT = """Eres un verificador de datos de cervezas artesanas para un catálogo.

Línea detectada por OCR en la pizarra de un bar (puede contener errores de OCR):
{line}

Resultados de búsqueda web:
{search_results}

Extractos de las páginas:
{pages}

Estilos existentes en el catálogo (SOLO puedes usar uno de estos, o null):
{styles}

Devuelve JSON con este esquema exacto:
{{
  "found": bool,          // true SOLO si identificas con claridad cervecera Y cerveza reales
  "corroborated": bool,   // true si lo confirman ≥2 fuentes independientes O la web oficial de la marca
  "brewery_name": str|null,   // nombre canónico de la cervecera
  "beer_name": str|null,      // nombre comercial de la cerveza
  "style_name": str|null,     // EXACTAMENTE uno de los estilos del catálogo, o null si ninguno encaja
  "abv": float|null,
  "description_es": str|null, // 1-2 frases en español, PARAFRASEADAS CON TUS PROPIAS PALABRAS.
                              // PROHIBIDO copiar frases literales de las fuentes.
  "source_url": str|null      // la URL más fiable de donde salen los datos
}}

Sé estricto: si hay ambigüedad, contradicción entre fuentes, o solo un resultado
débil, devuelve found=false. Es mejor no crear la ficha que crearla mal."""


async def _llm_extract(
    client: httpx.AsyncClient, line: str, search_results: list[dict], pages: list[dict], style_names: list[str]
) -> dict | None:
    prompt = _EXTRACTION_PROMPT.format(
        line=line,
        search_results=json.dumps(search_results, ensure_ascii=False, indent=1),
        pages=json.dumps(pages, ensure_ascii=False, indent=1),
        styles=json.dumps(style_names, ensure_ascii=False),
    )
    r = await client.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent",
        params={"key": GEMINI_API_KEY},
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.1},
        },
    )
    r.raise_for_status()
    try:
        text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
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
        await _enrich_item_inner(enrichment_id, line)
    except Exception:
        log.exception("enrichment %s failed", enrichment_id)
        # Best effort: dejar rastro del fallo para auditoría
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                token = await _pb_auth(client)
                await _pb_create(
                    client, token, "enrichments",
                    {"enrichment_id": enrichment_id, "status": "error"},
                )
        except Exception:
            pass
    finally:
        async with _in_flight_lock:
            _in_flight.discard(key)


async def _enrich_item_inner(enrichment_id: str, line: str) -> None:
    async with httpx.AsyncClient(timeout=20) as client:
        search_results = await _searx_search(client, f'"{line}" cerveza cervecera craft beer')
        if not search_results:
            search_results = await _searx_search(client, f"{line} cerveza")
        pages = await _fetch_pages(client, [x["url"] for x in search_results])

        _, styles, _ = await get_dictionaries()
        data = await _llm_extract(client, line, search_results, pages, sorted(styles.keys()))

        token = await _pb_auth(client)

        if not data or not data.get("found") or not data.get("corroborated") or not data.get("beer_name"):
            await _pb_create(
                client, token, "enrichments",
                {"enrichment_id": enrichment_id, "status": "no_match"},
            )
            return

        breweries, styles, _ = await get_dictionaries(force_refresh=True)

        # Cervecera: reutilizar por fuzzy si ya existe; crear solo si no
        brewery_id: str | None = None
        if data.get("brewery_name"):
            matched = _best_match(data["brewery_name"], breweries)
            if matched and matched.score >= MATCH_THRESHOLD:
                brewery_id = matched.id
            else:
                created = await _pb_create(
                    client, token, "breweries",
                    {
                        "name": data["brewery_name"],
                        "source": "auto-web",
                        "source_url": data.get("source_url") or "",
                        "verified": False,
                    },
                )
                brewery_id = created["id"]

        # Estilo: SOLO enlazar a existentes (vocabulario controlado)
        style_id: str | None = None
        if data.get("style_name"):
            matched = _best_match(data["style_name"], styles)
            if matched and matched.score >= MATCH_THRESHOLD:
                style_id = matched.id

        # Beer: idempotencia — si ya existe una con ese nombre y cervecera, reusar
        name_esc = _pb_filter_escape(data["beer_name"])
        existing = await _pb_find_first(
            client, token, "beers",
            f'name = "{name_esc}"' + (f' && brewery = "{brewery_id}"' if brewery_id else ""),
        )
        if existing:
            beer = existing
        else:
            beer = await _pb_create(
                client, token, "beers",
                {
                    "name": data["beer_name"],
                    **({"brewery": brewery_id} if brewery_id else {}),
                    **({"style": style_id} if style_id else {}),
                    **({"abv": data["abv"]} if isinstance(data.get("abv"), (int, float)) else {}),
                    "description": data.get("description_es") or "",
                    "source_url": data.get("source_url") or "",
                    "source": "auto-web",
                },
            )

        await _pb_create(
            client, token, "enrichments",
            {"enrichment_id": enrichment_id, "status": "created", "beer": beer["id"]},
        )
        await _reconcile_scan_items(
            client, token, enrichment_id,
            {
                "beer": beer["id"],
                **({"brewery": brewery_id} if brewery_id else {}),
                **({"style": style_id} if style_id else {}),
            },
        )
        # Que el diccionario en memoria conozca la nueva cervecera ya mismo
        await get_dictionaries(force_refresh=True)
        log.info("enrichment %s -> beer %s (%s)", enrichment_id, beer["id"], data["beer_name"])
