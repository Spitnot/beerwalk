"""
Matching fuzzy de líneas OCR contra el diccionario maestro
(cerveceras y estilos) usando rapidfuzz.

Estrategia MVP, deliberadamente simple:
1. Se busca la cervecera con partial_ratio contra la línea completa.
2. Se busca el estilo igual.
3. Lo que no es ni cervecera ni estilo se considera nombre de la cerveza.
"""
from rapidfuzz import fuzz, process

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
        score_cutoff=MATCH_THRESHOLD,
        limit=5,
    )
    if not results:
        return None
    # Con partial_ratio, "IPA" y "Hazy IPA" pueden empatar a 100:
    # ante empate de score, gana el nombre más largo (más específico).
    name, score, _ = max(results, key=lambda r: (r[1], len(r[0])))
    return MatchedEntity(id=dictionary[name], name=name, raw=line, score=round(score, 1))


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
                best = process.extractOne(token, candidates, scorer=fuzz.ratio, score_cutoff=80)
                if best:
                    candidates.remove(best[0])
                    remaining = " ".join(candidates)
    beer_name = remaining.strip(" -–·|") or None
    return brewery, style, beer_name
