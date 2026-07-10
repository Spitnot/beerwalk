"""
Envoltorio de PaddleOCR. El modelo se carga UNA vez (lazy) porque tarda
varios segundos y ocupa memoria.
"""
import io

from PIL import Image, ImageOps
import numpy as np

from .config import OCR_LANG

_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        from paddleocr import PaddleOCR

        _engine = PaddleOCR(use_angle_cls=True, lang=OCR_LANG, show_log=False)
    return _engine


def run_ocr(image_bytes: bytes) -> list[dict]:
    """
    Devuelve una lista de líneas: [{"text": str, "confidence": float, "box": [...]}]
    ordenadas de arriba a abajo (como se leen en una pizarra).
    """
    img = Image.open(io.BytesIO(image_bytes))
    img = ImageOps.exif_transpose(img).convert("RGB")
    arr = np.array(img)

    result = _get_engine().ocr(arr, cls=True)
    lines: list[dict] = []
    if not result or result[0] is None:
        return lines
    for box, (text, conf) in result[0]:
        lines.append({"text": text, "confidence": float(conf), "box": box})
    # orden vertical por la Y del primer punto de la caja
    lines.sort(key=lambda l: l["box"][0][1])
    return lines
