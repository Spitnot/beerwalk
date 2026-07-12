"""
BeerWalk — microservicio OCR (pipeline híbrido)
POST /ocr  -> imagen de pizarra -> bloques {cervecera, cerveza, estilo, precio, confianza}

1ª pasada: PaddleOCR (gratis, local) + agrupamiento espacial por bloques +
matching fuzzy (catálogo `beers` primero, luego cerveceras/estilos).
2ª pasada (solo si la primera sale mal): Gemini Vision sobre la imagen
completa, fusionando sus bloques con los que PaddleOCR ya resolvió.

Prueba rápida una vez levantado:
  curl -F "image=@tests/fixtures/pizarra_prueba.png" http://localhost:8000/ocr
"""
import logging
import uuid

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .blocks import group_lines
from .config import ENRICH_MAX_ITEMS_PER_SCAN
from .dictionary import get_dictionaries
from .enrichment import enrich_item, enrichment_configured, should_enrich
from .matching import match_block
from .ocr import run_ocr
from .schemas import OcrResponse, ScanItem
from .vision import (
    merge_items,
    record_scan_metric,
    should_use_vision,
    vision_configured,
    vision_extract,
    weekly_stats,
)

log = logging.getLogger("beerwalk.ocr")

app = FastAPI(title="BeerWalk OCR", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # MVP: restringir en producción a los dominios de la app
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/stats")
async def stats():
    """% de escaneos que necesitaron refuerzo Gemini Vision, por semana ISO.
    La señal de que el catálogo madura es ver `vision_pct` bajando."""
    try:
        return {"weeks": await weekly_stats()}
    except Exception:
        raise HTTPException(503, "Métricas no disponibles (¿ocr_metrics sin importar o sin credenciales?)")


@app.post("/dictionary/refresh")
async def refresh_dictionary():
    """Llamar desde el panel admin tras editar el diccionario maestro."""
    breweries, styles, beers = await get_dictionaries(force_refresh=True)
    return {"breweries": len(breweries), "styles": len(styles), "beers": len(beers)}


@app.post("/ocr", response_model=OcrResponse)
async def ocr_endpoint(background: BackgroundTasks, image: UploadFile = File(...)):
    if image.content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(415, "Formato no soportado (jpeg/png/webp)")

    image_bytes = await image.read()
    if len(image_bytes) > 10 * 1024 * 1024:
        raise HTTPException(413, "Imagen demasiado grande (máx 10MB)")

    # ── 1ª pasada: PaddleOCR + agrupamiento espacial + matching ─────────
    raw_lines = run_ocr(image_bytes)
    blocks = group_lines(raw_lines)
    breweries, styles, beers = await get_dictionaries()

    items: list[ScanItem] = []
    for block in blocks:
        text = block["text"].strip()
        if len(text) < 3:  # ruido: precios sueltos, símbolos...
            continue
        brewery, style, beer, beer_name = match_block(text, breweries, styles, beers)
        items.append(
            ScanItem(
                line=text,
                brewery=brewery,
                style=style,
                beer=beer,
                beer_name=beer_name,
                confidence=round(block["confidence"], 3),
            )
        )

    unmatched = sum(1 for it in items if it.beer is None and it.brewery is None and it.style is None)
    unmatched_ratio = unmatched / len(items) if items else 1.0
    avg_confidence = sum(it.confidence for it in items) / len(items) if items else 0.0

    # ── 2ª pasada (condicional): refuerzo Gemini Vision ─────────────────
    vision_used, vision_reason, vision_usage = False, None, None
    if vision_configured():
        needed, reason = should_use_vision(items)
        if needed:
            try:
                vision_blocks, vision_usage = await vision_extract(image_bytes, image.content_type)
                if vision_blocks:
                    items = merge_items(items, vision_blocks, breweries, styles, beers)
                vision_used, vision_reason = True, reason
                log.info("vision reforzó el escaneo (%s): %d bloques", reason, len(vision_blocks))
            except Exception:
                # Vision es refuerzo: si falla, la 1ª pasada sigue valiendo
                log.exception("fallo en el refuerzo de vision; se devuelve solo PaddleOCR")

    # Métrica de maduración del catálogo (una fila por escaneo, no bloquea)
    background.add_task(
        record_scan_metric, vision_used, vision_reason, unmatched_ratio, avg_confidence, vision_usage
    )

    # Enriquecimiento web en background para bloques sin resolver ────────
    if enrichment_configured():
        launched = 0
        for item in items:
            if launched >= ENRICH_MAX_ITEMS_PER_SCAN:
                break
            if should_enrich(item):
                item.enrichment_id = str(uuid.uuid4())
                background.add_task(enrich_item, item.enrichment_id, item.line, item.beer_name)
                launched += 1

    return OcrResponse(
        items=items,
        raw=raw_lines,
        vision_used=vision_used,
        vision_reason=vision_reason,
        vision_usage=vision_usage,
    )
