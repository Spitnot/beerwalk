"""
BeerWalk — microservicio OCR
POST /ocr  -> imagen de pizarra  ->  items {cervecera, estilo, confianza}

Prueba rápida una vez levantado:
  curl -F "image=@tests/fixtures/pizarra_prueba.png" http://localhost:8000/ocr
"""
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .dictionary import get_dictionaries
from .matching import match_line
from .ocr import run_ocr
from .schemas import OcrResponse, ScanItem

app = FastAPI(title="BeerWalk OCR", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # MVP: restringir en producción a los dominios de la app
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/dictionary/refresh")
async def refresh_dictionary():
    """Llamar desde el panel admin tras editar el diccionario maestro."""
    breweries, styles = await get_dictionaries(force_refresh=True)
    return {"breweries": len(breweries), "styles": len(styles)}


@app.post("/ocr", response_model=OcrResponse)
async def ocr_endpoint(image: UploadFile = File(...)):
    if image.content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(415, "Formato no soportado (jpeg/png/webp)")

    image_bytes = await image.read()
    if len(image_bytes) > 10 * 1024 * 1024:
        raise HTTPException(413, "Imagen demasiado grande (máx 10MB)")

    raw_lines = run_ocr(image_bytes)
    breweries, styles = await get_dictionaries()

    items: list[ScanItem] = []
    for line in raw_lines:
        text = line["text"].strip()
        if len(text) < 3:  # ruido: precios sueltos, símbolos...
            continue
        brewery, style, beer_name = match_line(text, breweries, styles)
        items.append(
            ScanItem(
                line=text,
                brewery=brewery,
                style=style,
                beer_name=beer_name,
                confidence=round(line["confidence"], 3),
            )
        )

    return OcrResponse(items=items, raw=raw_lines)
