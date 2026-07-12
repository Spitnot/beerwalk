"""
Tests del gating de enriquecimiento — sin red, sin PocketBase:
  cd modulo-ocr && pytest tests/test_enrichment.py
"""
from app.enrichment import _normalize_key, should_enrich
from app.schemas import MatchedEntity, ScanItem


def _item(**kwargs) -> ScanItem:
    base = dict(line="Cervesa Inventada Triple NEIPA", brewery=None, style=None,
                beer_name="Inventada Triple", confidence=0.92)
    base.update(kwargs)
    return ScanItem(**base)


def test_candidata_sin_cervecera_y_confianza_alta():
    assert should_enrich(_item())


def test_descarta_confianza_baja():
    assert not should_enrich(_item(confidence=0.60))


def test_descarta_si_cervecera_ya_matcheo():
    matched = MatchedEntity(id="b1", name="Espiga", raw="Espiga IPA", score=95.0)
    assert not should_enrich(_item(brewery=matched))


def test_descarta_texto_sin_sustancia():
    assert not should_enrich(_item(beer_name=None, line="5,5"))


def test_normalize_key_agrupa_variantes():
    # el dedupe en vuelo debe tratar variantes de OCR como la misma tarea
    assert _normalize_key("Garage Béer Co.") == _normalize_key("garage beer co")
