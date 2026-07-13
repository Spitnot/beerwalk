"""
Tests del matching fuzzy — se ejecutan SIN PocketBase ni PaddleOCR:
  cd modulo-ocr && pip install rapidfuzz pydantic pytest && pytest
"""
from app.matching import beer_candidates, match_block, match_line

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


# ── Fase 1 del desempate: filtro de ABV ─────────────────────────────────

def test_abv_desempata_nombres_empatados_en_score():
    # "Blat" y "Blanc" empatan a 100 de partial_ratio contra este texto
    # (verificado con rapidfuzz directamente); SIN Fase 1 el criterio de
    # siempre (nombre más largo) elegiría "Blanc", que es el incorrecto.
    beers = {
        "Blat": [{"id": "beer-blat", "abv": 5.1, "brewery_id": "b3",
                  "brewery_name": "Espiga", "style_id": None, "style_name": None}],
        "Blanc": [{"id": "beer-blanc", "abv": 7.0, "brewery_id": "b3",
                   "brewery_name": "Espiga", "style_id": None, "style_name": None}],
    }
    candidates = beer_candidates(beers, "b3")
    assert set(candidates) == {"Blat", "Blanc"}  # confirma el empate real

    brewery, style, beer, beer_name = match_block(
        "Espiga Blat Blanc 5,1", BREWERIES, STYLES, beers
    )
    assert beer_name == "Blat"  # el ABV del bloque (5,1) confirma Blat, no Blanc
    assert beer and beer.id == "beer-blat"


def test_abv_no_descarta_por_ausencia_de_dato_en_el_bloque():
    # Mismo empate, pero el bloque no trae un ABV limpio: fallo seguro,
    # se mantiene el criterio de siempre (nombre más largo).
    beers = {
        "Blat": [{"id": "beer-blat", "abv": 5.1, "brewery_id": "b3",
                  "brewery_name": "Espiga", "style_id": None, "style_name": None}],
        "Blanc": [{"id": "beer-blanc", "abv": 7.0, "brewery_id": "b3",
                   "brewery_name": "Espiga", "style_id": None, "style_name": None}],
    }
    _, _, beer, beer_name = match_block("Espiga Blat Blanc", BREWERIES, STYLES, beers)
    assert beer_name == "Blanc"  # sin ABV en el bloque, comportamiento sin cambios


def test_abv_no_descarta_por_ausencia_de_dato_en_la_ficha():
    # Empate de nombres, ABV limpio en el bloque, pero NINGUNA candidata
    # empatada tiene `abv` en catálogo: fallo seguro, sigue el criterio de
    # siempre sin filtrar nada.
    beers = {
        "Blat": [{"id": "beer-blat", "abv": None, "brewery_id": "b3",
                  "brewery_name": "Espiga", "style_id": None, "style_name": None}],
        "Blanc": [{"id": "beer-blanc", "abv": None, "brewery_id": "b3",
                   "brewery_name": "Espiga", "style_id": None, "style_name": None}],
    }
    _, _, _, beer_name = match_block("Espiga Blat Blanc 5,1", BREWERIES, STYLES, beers)
    assert beer_name == "Blanc"  # ninguna ficha tiene abv: no hay nada que desempatar


def test_abv_precio_no_se_confunde_con_grado():
    # "Patatas bravas 4,50" ya se prueba en test_linea_sin_match (match_line);
    # aquí confirmamos que match_block tampoco lo trata como ABV para desempatar.
    beers = {
        "Blat": [{"id": "beer-blat", "abv": 4.5, "brewery_id": "b3",
                  "brewery_name": "Espiga", "style_id": None, "style_name": None}],
        "Blanc": [{"id": "beer-blanc", "abv": 7.0, "brewery_id": "b3",
                   "brewery_name": "Espiga", "style_id": None, "style_name": None}],
    }
    # "4,50" tiene DOS decimales: nunca se lee como ABV, aunque coincida con
    # el de "Blat" si se leyera mal como "4,5"
    _, _, _, beer_name = match_block("Espiga Blat Blanc 4,50", BREWERIES, STYLES, beers)
    assert beer_name == "Blanc"  # sigue el criterio de siempre, no hay ABV limpio
