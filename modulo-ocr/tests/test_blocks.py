"""
Tests del agrupamiento espacial y del disparador de Gemini Vision — sin red:
  cd modulo-ocr && pytest tests/test_blocks.py
"""
from app.blocks import group_lines
from app.matching import match_block
from app.schemas import MatchedEntity, ScanItem
from app.vision import merge_items, should_use_vision


def _line(text: str, x: float, y: float, w: float = 100, h: float = 20, conf: float = 0.9) -> dict:
    return {
        "text": text,
        "confidence": conf,
        "box": [[x, y], [x + w, y], [x + w, y + h], [x, y + h]],
    }


def test_agrupa_rejilla_2x2_en_cuatro_bloques():
    # Cuatro paneles: dos líneas apiladas por panel, separación grande entre paneles
    lines = [
        _line("Basqueland", 0, 0), _line("Pink Flamingos", 0, 25),
        _line("SOMA", 300, 0), _line("Boost DIPA", 300, 25),
        _line("Cierzo", 0, 200), _line("Restium Tripel", 0, 225),
        _line("Dougall's", 300, 200), _line("942 APA", 300, 225),
    ]
    blocks = group_lines(lines)
    assert len(blocks) == 4
    texts = [b["text"] for b in blocks]
    assert "Basqueland Pink Flamingos" in texts
    assert "Cierzo Restium Tripel" in texts


def test_une_fragmentos_lado_a_lado():
    # precio y ABV a la misma altura pertenecen al mismo panel
    lines = [_line("SOMA Boost", 0, 0), _line("8%", 110, 2, w=30), _line("6,50", 150, 2, w=40)]
    blocks = group_lines(lines)
    assert len(blocks) == 1
    assert "8%" in blocks[0]["text"]


def test_orden_de_lectura_por_filas():
    lines = [_line("B", 300, 0), _line("A", 0, 3), _line("C", 0, 200), _line("D", 300, 203)]
    blocks = group_lines(lines)
    assert [b["text"] for b in blocks] == ["A", "B", "C", "D"]


BEERS = {
    "Boost": {"id": "beer1", "brewery_id": "b1", "brewery_name": "SOMA",
              "style_id": "s1", "style_name": "DIPA"},
}


def test_match_block_prioriza_catalogo_beers():
    brewery, style, beer, beer_name = match_block("SOMA Boost 8%", {"SOMA": "b1"}, {"DIPA": "s1"}, BEERS)
    assert beer and beer.id == "beer1"
    assert brewery and brewery.id == "b1"
    assert style and style.id == "s1"


def test_match_block_sin_catalogo_cae_a_fuzzy_normal():
    brewery, style, beer, _ = match_block("SOMA Boost 8%", {"SOMA": "b1"}, {"DIPA": "s1"}, {})
    assert beer is None
    assert brewery and brewery.id == "b1"


def _item(line: str, resolved: bool, conf: float = 0.9) -> ScanItem:
    ent = MatchedEntity(id="b1", name="X", raw=line, score=90.0) if resolved else None
    return ScanItem(line=line, brewery=ent, confidence=conf)


def test_vision_se_dispara_con_muchos_bloques_sin_reconocer():
    items = [_item("basura1", False), _item("basura2", False), _item("Espiga IPA", True)]
    needed, reason = should_use_vision(items)
    assert needed and "sin_reconocer" in reason


def test_vision_se_dispara_con_confianza_media_baja():
    items = [_item("Espiga IPA", True, conf=0.5), _item("Cierzo Lager", True, conf=0.6)]
    needed, reason = should_use_vision(items)
    assert needed and "confianza" in reason


def test_vision_no_se_dispara_si_paddle_va_bien():
    items = [_item("Espiga IPA", True), _item("Cierzo Lager", True), _item("raro", False)]
    needed, _ = should_use_vision(items)
    assert not needed


def test_merge_prioriza_vision_en_fallos_y_conserva_aciertos():
    paddle = [
        _item("flWFPiSt.eiknn", False),      # basura de Paddle
        _item("Espiga Garden IPA", True),     # acierto de Paddle
    ]
    vision_blocks = [
        {"brewery": "Homo Sibaris", "beer_name": "Melisa", "style": "Session IPA", "price": "4,00"},
        {"brewery": "Espiga", "beer_name": "Garden", "style": "IPA", "price": "4,50"},
    ]
    merged = merge_items(paddle, vision_blocks, {"Espiga": "b9"}, {"IPA": "s9"}, {})
    # el acierto de Paddle se conserva (misma entidad, no reemplazada)...
    espiga = next(it for it in merged if "Espiga" in it.line)
    assert espiga.source == "paddle" and espiga.price == "4,50"
    # ...y el bloque nuevo de Vision entra con sus entidades enlazadas si matchean
    melisa = next(it for it in merged if "Melisa" in it.line)
    assert melisa.source == "vision" and melisa.price == "4,00"
    assert melisa.brewery and melisa.brewery.id is None  # nombrada, sin ficha aún
