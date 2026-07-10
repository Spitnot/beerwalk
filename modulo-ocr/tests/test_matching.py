"""
Tests del matching fuzzy — se ejecutan SIN PocketBase ni PaddleOCR:
  cd modulo-ocr && pip install rapidfuzz pydantic pytest && pytest
"""
from app.matching import match_line

BREWERIES = {
    "Garage Beer Co": "b1",
    "Basqueland": "b2",
    "Espiga": "b3",
    "La Pirata": "b4",
}
STYLES = {
    "IPA": "s1",
    "Hazy IPA": "s2",
    "Imperial Stout": "s3",
    "Lager": "s4",
}


def test_match_exacto():
    brewery, style, _ = match_line("Garage Beer Co - Soup - Hazy IPA", BREWERIES, STYLES)
    assert brewery and brewery.name == "Garage Beer Co"
    assert style and style.name == "Hazy IPA"


def test_match_con_errores_de_ocr():
    # el OCR suele comerse letras o confundirlas en pizarras escritas a mano
    brewery, style, _ = match_line("Basqueiand Imperia1 Stout", BREWERIES, STYLES)
    assert brewery and brewery.name == "Basqueland"
    assert style and style.name == "Imperial Stout"


def test_linea_sin_match():
    brewery, style, beer_name = match_line("Patatas bravas 4,50", BREWERIES, STYLES)
    assert brewery is None
    assert style is None
    assert beer_name  # la línea entera queda como texto libre


def test_beer_name_extraido():
    _, _, beer_name = match_line("Espiga Garden IPA", BREWERIES, STYLES)
    assert beer_name and "Garden" in beer_name
