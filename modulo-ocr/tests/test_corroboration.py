"""
Listón de corroboración del enriquecimiento — arreglo del caso real
"Capricorn Feat Artesants" corroborada para el hint "Blat" de Espiga.

Sin red, sin PocketBase ni LLM: _verify_corroboration es una función pura
que audita en código las citas que dice aportar el LLM.
"""
from app.enrichment import _verify_corroboration


def test_patron_capricorn_se_rechaza():
    # Reproduce el caso real: el hint era "Blat" (trigo, en catalán) para
    # la cervecera Espiga. La búsqueda trajo una página sobre una cerveza
    # de OTRA marca ("Capricorn Feat Artesants") que solo menciona el
    # descriptor de estilo, nunca "Espiga". El listón viejo (booleano
    # autoevaluado) lo dejó pasar; el nuevo debe rechazarlo.
    pages = [
        {
            "url": "https://tangencial.example/capricorn",
            "text": "Capricorn Feat Artesants es una cerveza de trigo (blat) "
                    "elaborada de forma artesanal en un obrador local.",
        },
    ]
    quotes = [
        {"url": "https://tangencial.example/capricorn",
         "quote": "Capricorn Feat Artesants es una cerveza de trigo (blat)"},
    ]
    assert not _verify_corroboration(
        quotes, pages, brand="Espiga", beer_name="Blat", brewery_domain="espiga.cat"
    )


def test_dos_fuentes_independientes_que_mencionan_marca_y_cerveza_juntas():
    pages = [
        {"url": "https://blogcerveza.example/resena",
         "text": "La Espiga Blat es una cerveza de trigo muy refrescante, "
                 "elaborada por la cervecera catalana Espiga."},
        {"url": "https://guiacraft.example/cataluna",
         "text": "Entre las novedades destaca Espiga Blat, otra apuesta de "
                 "la marca Espiga por el estilo de trigo."},
    ]
    quotes = [
        {"url": "https://blogcerveza.example/resena",
         "quote": "La Espiga Blat es una cerveza de trigo muy refrescante"},
        {"url": "https://guiacraft.example/cataluna",
         "quote": "Espiga Blat, otra apuesta de la marca Espiga"},
    ]
    assert _verify_corroboration(
        quotes, pages, brand="Espiga", beer_name="Blat", brewery_domain=""
    )


def test_una_sola_fuente_basta_si_es_la_web_oficial():
    pages = [
        {"url": "https://www.espiga.cat/cervezas/blat",
         "text": "Espiga Blat, nuestra cerveza de trigo insignia."},
    ]
    quotes = [
        {"url": "https://www.espiga.cat/cervezas/blat",
         "quote": "Espiga Blat, nuestra cerveza de trigo insignia"},
    ]
    assert _verify_corroboration(
        quotes, pages, brand="Espiga", beer_name="Blat", brewery_domain="espiga.cat"
    )


def test_una_sola_fuente_no_oficial_no_basta():
    pages = [
        {"url": "https://blogcerveza.example/resena",
         "text": "La Espiga Blat es una cerveza de trigo muy refrescante."},
    ]
    quotes = [
        {"url": "https://blogcerveza.example/resena",
         "quote": "La Espiga Blat es una cerveza de trigo muy refrescante"},
    ]
    assert not _verify_corroboration(
        quotes, pages, brand="Espiga", beer_name="Blat", brewery_domain="espiga.cat"
    )


def test_cita_inventada_no_localizable_se_descarta():
    # El LLM alucina una cita que no está literalmente en la página dada.
    pages = [
        {"url": "https://blogcerveza.example/resena",
         "text": "Un repaso a las novedades de cerveza artesana este mes."},
    ]
    quotes = [
        {"url": "https://blogcerveza.example/resena",
         "quote": "Espiga Blat es la mejor cerveza de trigo de Cataluña"},
    ]
    assert not _verify_corroboration(
        quotes, pages, brand="Espiga", beer_name="Blat", brewery_domain=""
    )


def test_cita_de_url_no_incluida_en_pages_se_descarta():
    pages = [
        {"url": "https://real.example/pagina",
         "text": "Espiga Blat, cerveza de trigo de la cervecera Espiga."},
    ]
    quotes = [
        {"url": "https://otra.example/no-esta-en-pages",
         "quote": "Espiga Blat, cerveza de trigo de la cervecera Espiga"},
    ]
    assert not _verify_corroboration(
        quotes, pages, brand="Espiga", beer_name="Blat", brewery_domain=""
    )


def test_cita_demasiado_larga_se_descarta():
    long_text = "Espiga Blat es una cerveza de trigo. " + ("Relleno de más texto. " * 20)
    pages = [{"url": "https://real.example/pagina", "text": long_text}]
    quotes = [{"url": "https://real.example/pagina", "quote": long_text}]
    assert not _verify_corroboration(
        quotes, pages, brand="Espiga", beer_name="Blat", brewery_domain=""
    )


def test_ayinger_sigue_pasando_el_liston_mas_estricto():
    # Caso real ya enriquecido (Bloque 1, "Aymgar" -> Ayinger): confirma que
    # el listón más estricto no rompe lo que sí debe corroborarse.
    pages = [
        {"url": "https://www.ayinger.de/bier/braeuweisse",
         "text": "Die Ayinger Bräuweisse ist ein bayerisches Weißbier aus "
                 "der Privatbrauerei Ayinger in Aying."},
        {"url": "https://craftbeer.example/reviews/ayinger-brauweisse",
         "text": "Ayinger Bräuweisse is a classic Bavarian wheat beer from "
                 "the Ayinger brewery, well balanced and refreshing."},
    ]
    quotes = [
        {"url": "https://www.ayinger.de/bier/braeuweisse",
         "quote": "Die Ayinger Bräuweisse ist ein bayerisches Weißbier"},
        {"url": "https://craftbeer.example/reviews/ayinger-brauweisse",
         "quote": "Ayinger Bräuweisse is a classic Bavarian wheat beer from the Ayinger brewery"},
    ]
    assert _verify_corroboration(
        quotes, pages, brand="Ayinger", beer_name="Bräuweisse", brewery_domain="ayinger.de"
    )
