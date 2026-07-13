"""
Extracción de ABV (grado alcohólico) desde el texto OCR de un bloque, para
el desempate de Fase 1 (ver matching.py).

Regla estricta a propósito: en una pizarra real conviven precios ("4,50",
siempre a DOS decimales en España) y volúmenes de servicio ("0,33L") junto
al grado real ("5,1%"). Exigir el símbolo % o un patrón de UN SOLO decimal
descarta los precios; el rango de cordura descarta además los volúmenes en
litros, que también encajarían en el patrón de un solo decimal.
"""
import re

_WITH_PERCENT = re.compile(r"(\d{1,2}(?:[.,]\d)?)\s*%")
_STRICT_NO_PERCENT = re.compile(r"(?<!\d)(\d{1,2}[.,]\d)(?!\d)")

# Rango real de ABV de cerveza; también filtra volúmenes de servicio en
# litros ("0,5L", "0,33L") que calzan el patrón de un solo decimal.
_MIN_ABV, _MAX_ABV = 2.0, 20.0


def extract_abv(text: str) -> float | None:
    """ABV limpio del bloque, o None si no hay uno fiable. Fallo seguro:
    ante cualquier duda se devuelve None — nunca se inventa un valor."""
    match = _WITH_PERCENT.search(text) or _STRICT_NO_PERCENT.search(text)
    if not match:
        return None
    value = float(match.group(1).replace(",", "."))
    return value if _MIN_ABV <= value <= _MAX_ABV else None
