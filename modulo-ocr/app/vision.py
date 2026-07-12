"""
Refuerzo Gemini Vision del pipeline híbrido de lectura de pizarras.

PaddleOCR (gratis, local) es SIEMPRE la primera pasada. Vision solo entra
cuando esa pasada sale mal — demasiados bloques sin reconocer o confianza
media baja — y se le pide que lea la imagen completa extrayendo
cervecera/nombre/estilo/precio por panel. La fusión prioriza Vision en los
bloques que PaddleOCR falló y conserva los que ya iban bien.

Efecto esperado con el tiempo: según el catálogo `beers` crece con el
enriquecimiento, el matching resuelve más bloques a la primera y el % de
escaneos que necesita Vision BAJA. Eso se audita en la collection
`ocr_metrics` (una fila por escaneo) y se agrega por semana en GET /stats.
"""
import base64
import json
import logging

import httpx
from rapidfuzz import fuzz

from .config import (
    GEMINI_API_KEY,
    GEMINI_VISION_MODEL,
    MATCH_THRESHOLD,
    PB_SERVICE_EMAIL,
    POCKETBASE_URL,
    VISION_ENABLED,
    VISION_ITEM_CONFIDENCE,
    VISION_MIN_AVG_CONFIDENCE,
    VISION_UNMATCHED_RATIO,
)
from .enrichment import _pb_auth, _pb_create
from .matching import _best_match
from .schemas import MatchedEntity, ScanItem, VisionUsage

log = logging.getLogger("beerwalk.vision")


def vision_configured() -> bool:
    return VISION_ENABLED and bool(GEMINI_API_KEY)


def _is_resolved(item: ScanItem) -> bool:
    return item.beer is not None or item.brewery is not None or item.style is not None


def should_use_vision(items: list[ScanItem]) -> tuple[bool, str | None]:
    """Decide si la pasada de PaddleOCR necesita refuerzo."""
    if not items:
        return True, "paddle_sin_bloques"
    unmatched = sum(1 for it in items if not _is_resolved(it))
    ratio = unmatched / len(items)
    if ratio > VISION_UNMATCHED_RATIO:
        return True, f"bloques_sin_reconocer={ratio:.0%}"
    avg_conf = sum(it.confidence for it in items) / len(items)
    if avg_conf < VISION_MIN_AVG_CONFIDENCE:
        return True, f"confianza_media_baja={avg_conf:.2f}"
    return False, None


_VISION_PROMPT = """Esta es la foto de una pizarra de bar con cervezas de grifo,
normalmente organizada en paneles o bloques (uno por cerveza). Puede estar
escrita a mano con tiza/rotulador de colores.

Lee CADA panel/bloque que veas y devuelve JSON con este esquema exacto:
{
  "blocks": [
    {
      "brewery": str|null,    // nombre de la cervecera tal como está escrito
      "beer_name": str|null,  // nombre comercial de la cerveza
      "style": str|null,      // estilo si aparece (IPA, NEIPA, Tripel, Sour...)
      "price": str|null       // precio(s) tal como aparecen, ej. "4,50 / 6,00"
    }
  ]
}

Reglas:
- Un elemento por panel físico de la pizarra, en orden de lectura.
- Transcribe lo que está escrito; no inventes datos que no se vean.
- Si un campo no aparece en el panel, null."""


async def vision_extract(image_bytes: bytes, mime_type: str) -> tuple[list[dict], VisionUsage]:
    """Segunda pasada: Gemini Vision sobre la imagen completa. Devuelve los
    bloques leídos y los tokens REALES consumidos (usageMetadata de la API).
    Reintenta en 429/5xx: el tier gratuito devuelve 503 transitorios."""
    import asyncio

    body = {
        "contents": [{
            "parts": [
                {"inline_data": {"mime_type": mime_type,
                                 "data": base64.b64encode(image_bytes).decode()}},
                {"text": _VISION_PROMPT},
            ]
        }],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.1},
    }
    async with httpx.AsyncClient(timeout=60) as client:
        for attempt in range(3):
            r = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_VISION_MODEL}:generateContent",
                params={"key": GEMINI_API_KEY},
                json=body,
            )
            if r.status_code in (429, 500, 503) and attempt < 2:
                await asyncio.sleep(2 * (attempt + 1))
                continue
            break
        r.raise_for_status()
        payload = r.json()

    meta = payload.get("usageMetadata", {})
    usage = VisionUsage(
        prompt_tokens=meta.get("promptTokenCount", 0),
        # candidates + thinking: todo se factura como salida
        output_tokens=meta.get("candidatesTokenCount", 0) + meta.get("thoughtsTokenCount", 0),
        total_tokens=meta.get("totalTokenCount", 0),
    )
    try:
        text = payload["candidates"][0]["content"]["parts"][0]["text"]
        blocks = json.loads(text).get("blocks", [])
    except (KeyError, IndexError, json.JSONDecodeError):
        blocks = []
    return blocks, usage


def _entity_or_named(name: str | None, dictionary: dict[str, str], raw: str) -> MatchedEntity | None:
    """Enlaza el nombre que leyó Vision con el diccionario si hay match fuzzy;
    si no, lo conserva como entidad SIN id (visible en la app, sin relación)."""
    if not name:
        return None
    matched = _best_match(name, dictionary)
    if matched and matched.score >= MATCH_THRESHOLD:
        return matched
    return MatchedEntity(id=None, name=name, raw=raw, score=0.0)


def build_vision_item(block: dict, breweries: dict, styles: dict, beers: dict) -> ScanItem | None:
    parts = [block.get("brewery"), block.get("beer_name"), block.get("style")]
    line = " ".join(p for p in parts if p)
    if not line:
        return None

    beer_ent = None
    if beers:
        hit = _best_match(line, {name: rec["id"] for name, rec in beers.items()})
        if hit:
            beer_ent = hit
    return ScanItem(
        line=line,
        brewery=_entity_or_named(block.get("brewery"), breweries, line),
        style=_entity_or_named(block.get("style"), styles, line),
        beer=beer_ent,
        beer_name=block.get("beer_name"),
        price=block.get("price"),
        confidence=VISION_ITEM_CONFIDENCE,
        source="vision",
    )


def _is_strongly_resolved(item: ScanItem) -> bool:
    """Solo un match de catálogo o una cervecera CON ficha justifica conservar
    el bloque de PaddleOCR frente al de Vision; un estilo suelto ("NEIPA") con
    el resto de la línea destrozada no."""
    return item.beer is not None or (item.brewery is not None and item.brewery.id is not None)


def merge_items(paddle_items: list[ScanItem], vision_blocks: list[dict],
                breweries: dict, styles: dict, beers: dict) -> list[ScanItem]:
    """Fusión: Vision manda en los bloques que PaddleOCR falló; los bloques
    que PaddleOCR ya resolvió bien se conservan (no se paga por reprocesar
    lo que funcionaba), rellenando solo lo que Paddle no extrae (precio,
    estilo si faltaba)."""
    replaced: set[int] = set()
    paired: set[int] = set()
    merged: list[ScanItem] = list(paddle_items)
    extras: list[ScanItem] = []

    for block in vision_blocks:
        item = build_vision_item(block, breweries, styles, beers)
        if item is None:
            continue
        # Emparejar con el bloque de PaddleOCR más parecido aún libre.
        # Un solo bloque Vision por bloque Paddle: si Paddle fusionó varios
        # paneles en un megabloque, solo el primero lo consume y el resto
        # entra como items nuevos (no se pierden paneles).
        best_i, best_score = None, 0.0
        for i, pit in enumerate(paddle_items):
            if i in paired:
                continue
            score = fuzz.token_set_ratio(item.line.lower(), pit.line.lower())
            if score > best_score:
                best_i, best_score = i, score
        if best_i is None or best_score < 55:
            # Respaldo: mismo panel si la cervecera que leyó Vision aparece
            # como token en el bloque de Paddle ("CIERZO JABIER…" ↔ "CIERZO
            # RESTRIUM 45", donde la línea completa difiere demasiado).
            brewery_tokens = [
                t for t in (block.get("brewery") or "").lower().split() if len(t) >= 4
            ]
            for i, pit in enumerate(paddle_items):
                if i in paired:
                    continue
                pit_tokens = pit.line.lower().split()
                if any(
                    fuzz.ratio(bt, pt) >= 85
                    for bt in brewery_tokens for pt in pit_tokens
                ):
                    best_i, best_score = i, 55.0
                    break
        if best_i is not None and best_score >= 55:
            paired.add(best_i)
            if _is_strongly_resolved(paddle_items[best_i]):
                # PaddleOCR ya lo tenía bien: conservar y rellenar huecos
                if item.price and not merged[best_i].price:
                    merged[best_i].price = item.price
                if item.style and not merged[best_i].style:
                    merged[best_i].style = item.style
                continue
            merged[best_i] = item
            replaced.add(best_i)
            continue
        extras.append(item)

    # Limpieza de ruido: Vision lee la imagen COMPLETA, así que un bloque de
    # Paddle sin resolver que ningún bloque de Vision reclamó ("LaDan",
    # "586b", fragmentos ilegibles) es basura de OCR de un panel que Vision
    # ya cubrió — no una cerveza que Vision no vio. Los resueltos se
    # conservan siempre.
    if vision_blocks:
        merged = [
            it for i, it in enumerate(merged)
            if i in paired or i in replaced or _is_resolved(it)
        ]

    return merged + extras


# ── Métrica de maduración del catálogo ───────────────────────────────────


async def record_scan_metric(vision_used: bool, reason: str | None,
                             unmatched_ratio: float, avg_confidence: float,
                             usage: VisionUsage | None) -> None:
    """Una fila por escaneo en `ocr_metrics` (PocketBase) para poder ver el
    % semanal de refuerzo Vision bajando según madura el catálogo. Si la
    collection no existe o no hay credenciales, queda al menos el log."""
    log.info(
        "scan_metric vision_used=%s reason=%s unmatched=%.2f avg_conf=%.2f prompt_tokens=%s output_tokens=%s",
        vision_used, reason, unmatched_ratio, avg_confidence,
        usage.prompt_tokens if usage else 0, usage.output_tokens if usage else 0,
    )
    if not PB_SERVICE_EMAIL:
        return
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            token = await _pb_auth(client)
            await _pb_create(
                client, token, "ocr_metrics",
                {
                    "vision_used": vision_used,
                    "reason": reason or "",
                    "unmatched_ratio": round(unmatched_ratio, 3),
                    "avg_confidence": round(avg_confidence, 3),
                    "prompt_tokens": usage.prompt_tokens if usage else 0,
                    "output_tokens": usage.output_tokens if usage else 0,
                },
            )
    except Exception:
        log.warning("no se pudo registrar la métrica en ocr_metrics (¿esquema sin importar?)")


async def weekly_stats() -> list[dict]:
    """% de escaneos con refuerzo Vision por semana ISO (para GET /stats)."""
    async with httpx.AsyncClient(timeout=10) as client:
        token = await _pb_auth(client)
        rows: list[dict] = []
        page = 1
        while True:
            r = await client.get(
                f"{POCKETBASE_URL}/api/collections/ocr_metrics/records",
                params={"page": page, "perPage": 500, "fields": "created,vision_used"},
                headers={"Authorization": token},
            )
            r.raise_for_status()
            data = r.json()
            rows.extend(data["items"])
            if page >= data["totalPages"]:
                break
            page += 1

    from datetime import datetime

    weeks: dict[str, dict] = {}
    for row in rows:
        dt = datetime.fromisoformat(row["created"].replace(" ", "T").replace("Z", "+00:00"))
        iso = dt.isocalendar()
        key = f"{iso.year}-W{iso.week:02d}"
        bucket = weeks.setdefault(key, {"week": key, "scans": 0, "vision_used": 0})
        bucket["scans"] += 1
        if row.get("vision_used"):
            bucket["vision_used"] += 1
    out = sorted(weeks.values(), key=lambda w: w["week"])
    for w in out:
        w["vision_pct"] = round(100.0 * w["vision_used"] / w["scans"], 1)
    return out
