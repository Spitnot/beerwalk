from pydantic import BaseModel


class MatchedEntity(BaseModel):
    id: str | None = None          # id en PocketBase si hubo match
    name: str | None = None        # nombre canónico matcheado
    raw: str                       # texto tal cual salió del OCR
    score: float = 0.0             # score de similitud rapidfuzz (0-100)


class ScanItem(BaseModel):
    line: str                      # línea completa detectada en la pizarra
    brewery: MatchedEntity | None = None
    style: MatchedEntity | None = None
    beer_name: str | None = None   # lo que queda de la línea tras extraer entidades
    confidence: float              # confianza media del OCR para esa línea (0-1)


class OcrResponse(BaseModel):
    items: list[ScanItem]
    raw: list[dict]                # salida cruda de PaddleOCR (se guarda en scans.raw_ocr_json)
