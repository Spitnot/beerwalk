from pydantic import BaseModel


class MatchedEntity(BaseModel):
    id: str | None = None          # id en PocketBase si hubo match
    name: str | None = None        # nombre canónico matcheado
    raw: str                       # texto tal cual salió del OCR
    score: float = 0.0             # score de similitud rapidfuzz (0-100)


class ScanItem(BaseModel):
    line: str                      # texto completo del bloque detectado
    brewery: MatchedEntity | None = None
    style: MatchedEntity | None = None
    # Cerveza del catálogo `beers` si el bloque matcheó una ficha completa.
    # Se prueba ANTES que brewery/style sueltos: resuelve el bloque de golpe.
    beer: MatchedEntity | None = None
    beer_name: str | None = None   # lo que queda del bloque tras extraer entidades
    price: str | None = None       # precio leído en la pizarra (solo vía vision)
    confidence: float              # confianza media del OCR para ese bloque (0-1)
    source: str = "paddle"         # "paddle" | "vision" — quién leyó este bloque
    # UUID asignado si esta línea disparó enriquecimiento web en background.
    # La app lo guarda en scan_items para que el resultado (collection
    # `enrichments`) pueda reconciliarse con el escaneo, llegue antes o después.
    enrichment_id: str | None = None


class VisionUsage(BaseModel):
    """Tokens reales devueltos por la API de Gemini Vision (auditoría de coste)."""
    prompt_tokens: int = 0
    output_tokens: int = 0         # incluye thinking tokens si el modelo los usó
    total_tokens: int = 0


class OcrResponse(BaseModel):
    items: list[ScanItem]
    raw: list[dict]                # salida cruda de PaddleOCR (se guarda en scans.raw_ocr_json)
    vision_used: bool = False      # ¿hizo falta refuerzo de Gemini Vision?
    vision_reason: str | None = None
    vision_usage: VisionUsage | None = None
