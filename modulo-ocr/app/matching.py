"""
Matching fuzzy de líneas OCR contra el diccionario maestro
(cerveceras y estilos) usando rapidfuzz.

Estrategia MVP, deliberadamente simple:
1. Se busca la cervecera con partial_ratio contra la línea completa.
2. Se busca el estilo igual.
3. Lo que no es ni cervecera ni estilo se considera nombre de la cerveza.
"""
from rapidfuzz import fuzz, process, utils

from .config import MATCH_THRESHOLD
from .schemas import MatchedEntity


def _best_match(line: str, dictionary: dict[str, str]) -> MatchedEntity | None:
    """dictionary: {nombre_canonico: id_pocketbase}"""
    if not dictionary:
        return None
    results = process.extract(
        line,
        dictionary.keys(),
        scorer=fuzz.partial_ratio,
        # default_process: case-insensitive — las pizarras van en MAYÚSCULAS
        # y el diccionario en Title Case; sin esto casi nada matchea
        processor=utils.default_process,
        score_cutoff=MATCH_THRESHOLD,
        limit=5,
    )
    if not results:
        return None
    # Los nombres muy cortos ("IPA") dan falsos positivos con partial_ratio
    # ("Patatas bravas" → 80): exigirles aparecer como token completo.
    line_tokens = utils.default_process(line).split()
    results = [
        r for r in results
        if len(utils.default_process(r[0])) > 4
        or process.extractOne(r[0], line_tokens, scorer=fuzz.ratio,
                              processor=utils.default_process, score_cutoff=85)
    ]
    if not results:
        return None
    # Con partial_ratio, "IPA" y "Hazy IPA" pueden empatar a 100:
    # ante empate de score, gana el nombre más largo (más específico).
    name, score, _ = max(results, key=lambda r: (r[1], len(r[0])))
    return MatchedEntity(id=dictionary[name], name=name, raw=line, score=round(score, 1))


def match_block(
    text: str,
    breweries: dict[str, str],
    styles: dict[str, str],
    beers: dict[str, dict],
) -> tuple[MatchedEntity | None, MatchedEntity | None, MatchedEntity | None, str | None]:
    """Matching de un bloque completo: primero contra el catálogo `beers`
    (una ficha resuelve cervecera+estilo+nombre de golpe; según crece el
    catálogo, menos bloques necesitan refuerzo de Vision), y si no, contra
    cerveceras/estilos sueltos como siempre.

    Devuelve (brewery, style, beer, beer_name).
    """
    if beers:
        hit = _best_match(text, {name: rec["id"] for name, rec in beers.items()})
        if hit and hit.name:
            rec = beers[hit.name]
            brewery = (
                MatchedEntity(id=rec["brewery_id"], name=rec["brewery_name"], raw=text, score=hit.score)
                if rec.get("brewery_id") else None
            )
            style = (
                MatchedEntity(id=rec["style_id"], name=rec["style_name"], raw=text, score=hit.score)
                if rec.get("style_id") else None
            )
            return brewery, style, hit, hit.name

    brewery, style, beer_name = match_line(text, breweries, styles)
    return brewery, style, None, beer_name


def match_line(
    line: str,
    breweries: dict[str, str],
    styles: dict[str, str],
) -> tuple[MatchedEntity | None, MatchedEntity | None, str | None]:
    brewery = _best_match(line, breweries)
    style = _best_match(line, styles)

    # Nombre de la cerveza: quitamos las palabras ya explicadas por los matches
    remaining = line
    for ent in (brewery, style):
        if ent and ent.name:
            for token in ent.name.split():
                # eliminación tolerante token a token
                candidates = remaining.split()
                best = process.extractOne(
                    token, candidates, scorer=fuzz.ratio,
                    processor=utils.default_process, score_cutoff=80,
                )
                if best:
                    candidates.remove(best[0])
                    remaining = " ".join(candidates)
    beer_name = remaining.strip(" -–·|") or None
    return brewery, style, beer_name
