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


async def _fetch_beers() -> dict[str, dict]:
    """Catálogo de cervezas: {nombre: {id, brewery_id, brewery_name, style_id,
    style_name}}. Si la collection no existe aún (esquema sin importar),
    devuelve {} sin romper el resto del diccionario."""
    out: dict[str, dict] = {}
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
                        "fields": "id,name,expand.brewery.id,expand.brewery.name,"
                                  "expand.style.id,expand.style.name",
                    },
                )
                r.raise_for_status()
                data = r.json()
                for item in data["items"]:
                    exp = item.get("expand") or {}
                    brewery = exp.get("brewery") or {}
                    style = exp.get("style") or {}
                    out[item["name"]] = {
                        "id": item["id"],
                        "brewery_id": brewery.get("id"),
                        "brewery_name": brewery.get("name"),
                        "style_id": style.get("id"),
                        "style_name": style.get("name"),
                    }
                if page >= data["totalPages"]:
                    break
                page += 1
    except Exception:
        return {}
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
    _cache = {"breweries": breweries, "styles": styles, "beers": beers}
    return breweries, styles, beers
