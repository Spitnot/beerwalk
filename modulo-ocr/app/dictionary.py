"""
Carga del diccionario maestro (cerveceras + estilos + catálogo de cervezas)
desde PocketBase, con fallback a los JSON de seed locales para poder testear
el módulo de forma totalmente aislada.

El catálogo `beers` se matchea ANTES que cerveceras/estilos sueltos: una
cerveza ya fichada (manual o auto-web) resuelve el bloque entero de golpe.
Efecto esperado: según crece el catálogo con el enriquecimiento, cada vez
menos bloques necesitan refuerzo de Gemini Vision.
"""
import json
import os

import httpx

from .config import LOCAL_DICT_PATH, POCKETBASE_URL

_cache: dict[str, dict] = {}

# Sufijos societarios/genéricos que las pizarras nunca escriben
BRAND_SUFFIXES = {
    "privatbrauerei", "brauerei", "brewery", "brewing", "bryghus", "brewers",
    "cervecera", "cervesera", "cervesa", "cerveza", "brasserie", "co", "company",
}

# Alias de jerga de mostrador -> nombre canónico del catálogo de estilos.
# Curado a mano, deliberadamente conservador: solo términos donde la jerga
# designa SIEMPRE el mismo estilo real, nunca abreviaturas ambiguas que en
# la práctica pueden significar cosas distintas según el contexto (mejor no
# resolver que crear una identidad falsa, mismo criterio que el resto del
# desempate). Claves en minúscula: se comparan contra tokens ya normalizados
# (ver resolve_style_alias en matching.py).
STYLE_ALIASES = {
    "neipa": "Hazy IPA",
    "dipa": "Double IPA",
    "cda": "Black IPA",
    "apa": "Pale Ale",
    "esb": "Best Bitter",
    "ris": "Imperial Stout",
    "hefeweizen": "Wheat",
    "weizen": "Wheat",
    "weissbier": "Wheat",
    "blanche": "Witbier",
}


def brand_aliases(names: dict[str, str]) -> dict[str, str]:
    """Añade alias de marca corta ("Ayinger Privatbrauerei" → "Ayinger"):
    las pizarras escriben la marca, no la razón social, y el fuzzy contra el
    nombre canónico completo no llega al umbral. Sin estos alias, el acotado
    por cervecera (Fase 0 del desempate) no se activa en fichas creadas por
    el enriquecimiento, que usa nombres canónicos largos."""
    out = dict(names)
    for name, rec_id in names.items():
        tokens = [t for t in name.split() if t.lower().strip(".") not in BRAND_SUFFIXES]
        alias = " ".join(tokens)
        if alias and alias != name and alias not in out:
            out[alias] = rec_id
    return out


async def _fetch_collection(name: str) -> dict[str, str]:
    """Devuelve {nombre: id} de una collection de PocketBase (paginado simple)."""
    out: dict[str, str] = {}
    async with httpx.AsyncClient(timeout=5) as client:
        page = 1
        while True:
            r = await client.get(
                f"{POCKETBASE_URL}/api/collections/{name}/records",
                params={"page": page, "perPage": 200, "fields": "id,name"},
            )
            r.raise_for_status()
            data = r.json()
            for item in data["items"]:
                out[item["name"]] = item["id"]
            if page >= data["totalPages"]:
                break
            page += 1
    return out


async def _fetch_beers() -> dict[str, list[dict]]:
    """Catálogo de cervezas: {nombre: [fichas]}. Lista porque los nombres
    genéricos ("Blat", "IPA") se repiten entre cerveceras — un dict simple
    haría que una ficha pisara a la otra y el caso ambiguo ni existiría.
    Si la collection no existe aún, devuelve {} sin romper el diccionario."""
    out: dict[str, list[dict]] = {}
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            page = 1
            while True:
                r = await client.get(
                    f"{POCKETBASE_URL}/api/collections/beers/records",
                    params={
                        "page": page,
                        "perPage": 200,
                        "expand": "brewery,style",
                        "fields": "id,name,abv,expand.brewery.id,expand.brewery.name,"
                                  "expand.style.id,expand.style.name",
                    },
                )
                r.raise_for_status()
                data = r.json()
                for item in data["items"]:
                    exp = item.get("expand") or {}
                    brewery = exp.get("brewery") or {}
                    style = exp.get("style") or {}
                    out.setdefault(item["name"], []).append({
                        "id": item["id"],
                        "abv": item.get("abv"),
                        "brewery_id": brewery.get("id"),
                        "brewery_name": brewery.get("name"),
                        "style_id": style.get("id"),
                        "style_name": style.get("name"),
                    })
                if page >= data["totalPages"]:
                    break
                page += 1
    except Exception:
        return {}
    return out


def _pb_filter_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


async def get_bar_beer_history(bar_id: str) -> set[str]:
    """IDs de `beers` que ya constan en escaneos anteriores de este bar
    (Fase 3 del desempate: "¿esta candidata ya se ha visto/servido en este
    bar?"). Set membership simple sobre `scan_items` pasados vía la relación
    `scan.bar` — sin componente posicional (eso queda para una fase futura).

    Fallo seguro: cualquier fallo (bar sin escaneos, PocketBase caído) da
    historial vacío, que en el matching equivale a no tener nada que aportar
    — nunca rompe ni descarta candidatas por su ausencia."""
    out: set[str] = set()
    try:
        bar_id_esc = _pb_filter_escape(bar_id)
        async with httpx.AsyncClient(timeout=5) as client:
            page = 1
            while True:
                r = await client.get(
                    f"{POCKETBASE_URL}/api/collections/scan_items/records",
                    params={
                        "page": page,
                        "perPage": 200,
                        "filter": f'scan.bar = "{bar_id_esc}" && beer != ""',
                        "fields": "beer",
                    },
                )
                r.raise_for_status()
                data = r.json()
                out.update(item["beer"] for item in data["items"] if item.get("beer"))
                if page >= data["totalPages"]:
                    break
                page += 1
    except Exception:
        return set()
    return out


def _local_fallback(name: str) -> dict[str, str]:
    path = os.path.join(LOCAL_DICT_PATH, f"{name}_local.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        items = json.load(f)
    return {item["name"]: f"local-{i}" for i, item in enumerate(items)}


async def get_dictionaries(force_refresh: bool = False) -> tuple[dict, dict, dict]:
    """(breweries, styles, beers). Cachea en memoria del proceso."""
    global _cache
    if _cache and not force_refresh:
        return _cache["breweries"], _cache["styles"], _cache["beers"]
    try:
        breweries = await _fetch_collection("breweries")
        styles = await _fetch_collection("styles")
        beers = await _fetch_beers()
    except Exception:
        breweries = _local_fallback("breweries")
        styles = _local_fallback("styles")
        beers = {}
    breweries = brand_aliases(breweries)
    _cache = {"breweries": breweries, "styles": styles, "beers": beers}
    return breweries, styles, beers
