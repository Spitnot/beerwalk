"""
Alias de jerga de mostrador -> nombre canónico de estilo (NEIPA -> Hazy IPA,
DIPA -> Double IPA...). Sin red, sin PocketBase: resolve_style_alias es una
función pura.
"""
from app.matching import resolve_style_alias

STYLES = {
    "IPA": "s1",
    "Hazy IPA": "s2",
    "Double IPA": "s3",
    "Best Bitter": "s4",
    "Wheat": "s5",
}


def test_neipa_resuelve_a_hazy_ipa():
    hit = resolve_style_alias("Soma NEIPA", STYLES)
    assert hit is not None
    assert hit.name == "Hazy IPA"  # canónico, NUNCA "NEIPA" ni el genérico "IPA"
    assert hit.id == "s2"


def test_dipa_resuelve_a_double_ipa():
    hit = resolve_style_alias("Cierzo DIPA 8%", STYLES)
    assert hit is not None
    assert hit.name == "Double IPA"
    assert hit.id == "s3"


def test_hefeweizen_variantes_resuelven_a_wheat():
    for jerga in ("Hefeweizen", "Weizen", "Weissbier"):
        hit = resolve_style_alias(f"Ayinger {jerga}", STYLES)
        assert hit is not None, jerga
        assert hit.name == "Wheat"


def test_esb_resuelve_a_best_bitter():
    hit = resolve_style_alias("Fuller's ESB", STYLES)
    assert hit is not None
    assert hit.name == "Best Bitter"


def test_texto_sin_jerga_conocida_no_resuelve():
    assert resolve_style_alias("Espiga Garden IPA", STYLES) is None
    assert resolve_style_alias("Cerveza de trigo artesana", STYLES) is None


def test_fallo_seguro_canonico_ausente_del_catalogo():
    # "Black IPA" NO está en este catálogo: CDA nunca debe inventar un id.
    sin_black_ipa = {"IPA": "s1", "Hazy IPA": "s2"}
    assert resolve_style_alias("Cierzo CDA", sin_black_ipa) is None


def test_no_pisa_estilo_real_con_el_mismo_nombre_del_alias():
    # Caso hipotético: si "APA" existiera algún día como estilo REAL y
    # DISTINTO de "Pale Ale" en el catálogo, el alias nunca debe secuestrar
    # ese texto hacia "Pale Ale" — se deja sin resolver aquí (el match_line
    # normal encontraría el "APA" real por su cuenta).
    con_apa_real = {"APA": "s9", "Pale Ale": "s10"}
    assert resolve_style_alias("Barrilete APA", con_apa_real) is None


def test_requiere_token_completo_no_substring():
    # "capadipa" no es DIPA aunque contenga la subcadena "dipa"
    assert resolve_style_alias("Cerveza Capadipa Especial", STYLES) is None


def test_texto_vacio_no_resuelve():
    assert resolve_style_alias("", STYLES) is None
