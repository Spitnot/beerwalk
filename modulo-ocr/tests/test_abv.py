"""Extracción de ABV — regla estricta para no confundir precios/volúmenes con grado."""
from app.abv import extract_abv


def test_abv_con_simbolo_porcentaje():
    assert extract_abv("Ayinger Bräuweisse 5,1%") == 5.1
    assert extract_abv("IPA 6.5 %") == 6.5
    assert extract_abv("Stout 9%") == 9.0  # entero + % también vale


def test_abv_sin_simbolo_pero_un_solo_decimal():
    assert extract_abv("Espiga Blat 5,1") == 5.1


def test_precio_espanol_no_se_confunde_con_abv():
    # Precio real con DOS decimales: nunca debe leerse como grado
    assert extract_abv("Patatas bravas 4,50") is None
    assert extract_abv("Ración 4.50€") is None


def test_volumen_de_servicio_no_se_confunde_con_abv():
    # "0,5L"/"0,33L" caen en el rango de cordura (fuera de 2-20) y se descartan
    assert extract_abv("Caña 0,33L") is None
    assert extract_abv("Copa 0,5L") is None


def test_sin_patron_reconocible():
    assert extract_abv("CIERZO RESTRIUM 45") is None
    assert extract_abv("Ayinger BLAT 510 600 0047") is None


def test_texto_vacio():
    assert extract_abv("") is None
