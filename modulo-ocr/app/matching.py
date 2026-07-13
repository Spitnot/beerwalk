"""
Matching fuzzy de líneas OCR contra el diccionario maestro
(cerveceras y estilos) usando rapidfuzz.

Estrategia MVP, deliberadamente simple:
1. Se busca la cervecera con partial_ratio contra la línea completa.
2. Se busca el estilo igual.
3. Lo que no es ni cervecera ni estilo se considera nombre de la cerveza.
"""
from rapidfuzz import fuzz, process, utils

from .abv import extract_abv
from .config import ABV_TOLERANCE, MATCH_THRESHOLD
from .schemas import MatchedEntity


def _best_match(
    line: str,
    dictionary: dict[str, str],
    abv_lookup: dict[str, float | None] | None = None,
    block_abv: float | None = None,
) -> MatchedEntity | None:
    """dictionary: {nombre_canonico: id_pocketbase}

    `abv_lookup`/`block_abv`: Fase 1 del desempate (solo la usa `match_block`
    para las candidatas de `beers` — breweries/estilos no llevan ABV)."""
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

    # Fase 1 del desempate: entre nombres EMPATADOS a la misma puntuación
    # (donde el criterio de siempre -nombre más largo- es un desempate
    # arbitrario), preferir el que su ABV de catálogo confirme el ABV leído
    # en el bloque. Fallo seguro bidireccional: sin ABV limpio en el bloque,
    # sin ninguna candidata empatada con `abv` registrado, o sin ninguna
    # dentro de tolerancia, no se descarta nada — sigue el criterio de
    # siempre sobre el conjunto sin tocar.
    if abv_lookup and block_abv is not None:
        top_score = max(r[1] for r in results)
        tied = [r for r in results if r[1] == top_score]
        if len(tied) > 1:
            confirmed = [
                r for r in tied
                if abv_lookup.get(r[0]) is not None
                and abs(abv_lookup[r[0]] - block_abv) <= ABV_TOLERANCE
            ]
            if confirmed:
                results = confirmed

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
       Dentro de este paso, Fase 1 del desempate: si dos candidatas
       empatan en score, el ABV leído en el bloque (si hay uno limpio)
       desempata hacia la que confirme el ABV de catálogo.
    3. Fallback: cervecera/estilo sueltos como siempre (match_line).
       (Fase 3 del desempate —historial de bar— se aplicará aparte,
       después de este resultado, con el `bar_id` de la petición.)

    Devuelve (brewery, style, beer, beer_name).
    """
    brewery_hit = _best_match(text, breweries)
    block_abv = extract_abv(text)

    if beers:
        candidates = beer_candidates(beers, brewery_hit.id if brewery_hit else None)
        abv_lookup = {name: rec.get("abv") for name, rec in candidates.items()}
        hit = (
            _best_match(text, {n: r["id"] for n, r in candidates.items()},
                        abv_lookup=abv_lookup, block_abv=block_abv)
            if candidates else None
        )
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
