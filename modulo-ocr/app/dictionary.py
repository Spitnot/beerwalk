"""
Carga del diccionario maestro (cerveceras + estilos) desde PocketBase,
con fallback a los JSON de seed locales para poder testear el módulo
de forma totalmente aislada.
"""
import json
import os

import httpx

from .config import LOCAL_DICT_PATH, POCKETBASE_URL

_cache: dict[str, dict[str, str]] = {}


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


def _local_fallback(name: str) -> dict[str, str]:
    path = os.path.join(LOCAL_DICT_PATH, f"{name}_local.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        items = json.load(f)
    return {item["name"]: f"local-{i}" for i, item in enumerate(items)}


async def get_dictionaries(force_refresh: bool = False) -> tuple[dict, dict]:
    """(breweries, styles) como {nombre: id}. Cachea en memoria del proceso."""
    global _cache
    if _cache and not force_refresh:
        return _cache["breweries"], _cache["styles"]
    try:
        breweries = await _fetch_collection("breweries")
        styles = await _fetch_collection("styles")
    except Exception:
        breweries = _local_fallback("breweries")
        styles = _local_fallback("styles")
    _cache = {"breweries": breweries, "styles": styles}
    return breweries, styles
