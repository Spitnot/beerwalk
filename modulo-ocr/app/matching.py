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


def beer_candidates(beers: dict[str, list[dict]], brewery_id: str | None = None) -> dict[str, dict]:
    """Candidatas del catálogo `beers` como {nombre: ficha}.

    - Con brewery_id (Fase 0 del desempate): SOLO las cervezas de esa
      cervecera — "Blat" es ambiguo, "Blat de Ayinger" no.
    - Sin brewery_id: solo nombres inequívocos (una única ficha con ese
      nombre en todo el catálogo). Ante un nombre genérico repetido entre
      cerveceras NO se adivina: mejor caer a enriquecimiento que asignar
      una identidad falsa (las fases futuras del desempate afinarán esto).
    """
    if brewery_id:
        out = {}
        for name, recs in beers.items():
            mine = [r for r in recs if r.get("brewery_id") == brewery_id]
            if mine:
                out[name] = mine[0]
        return out
    return {name: recs[0] for name, recs in beers.items() if len(recs) == 1}


def match_block(
    text: str,
    breweries: dict[str, str],
    styles: dict[str, str],
    beers: dict[str, list[dict]],
) -> tuple[MatchedEntity | None, MatchedEntity | None, MatchedEntity | None, str | None]:
    """Matching de un bloque completo, en cascada:

    1. Cervecera del bloque (fuzzy contra `breweries`).
    2. Catálogo `beers` ACOTADO a esa cervecera si matcheó (Fase 0 del
       desempate: elimina la ambigüedad de nombres genéricos y evita
       identidades cruzadas entre cerveceras); sin cervecera, catálogo
       completo pero solo nombres inequívocos.
    3. Fallback: cervecera/estilo sueltos como siempre (match_line).

    Devuelve (brewery, style, beer, beer_name).
    """
    brewery_hit = _best_match(text, breweries)

    if beers:
        candidates = beer_candidates(beers, brewery_hit.id if brewery_hit else None)
        hit = _best_match(text, {n: r["id"] for n, r in candidates.items()}) if candidates else None
        if hit and hit.name:
            rec = candidates[hit.name]
            brewery = brewery_hit or (
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
