"""
módulo-datos — catálogo de estilos ampliado con la guía BJCP 2023 como
referencia técnica.

Uso (con el docker compose local levantado):
  pip install httpx
  python seed_bjcp_styles.py --url http://localhost:8090 \
      --email admin@beerwalk.local --password cambiame-por-favor-1234

Idempotente en las dos direcciones:
  - Si el estilo no existe (por nombre exacto), lo crea completo.
  - Si ya existe, SOLO rellena los campos que estén vacíos (enriquece sin
    pisar ediciones manuales del admin).

Es un catálogo cerrado, importado una sola vez — no forma parte del
enriquecimiento en vivo. Escribe como superusuario, igual que los demás
seeds (las reglas de `styles` son admin-only para escritura).

NOTA DE DERECHOS: los textos descriptivos de seed/bjcp_styles.json están
redactados por nosotros a partir de la guía BJCP (bjcp.org) — NO son una
reproducción del texto oficial, que tiene copyright. Los rangos numéricos
(ABV/IBU/SRM), los códigos de categoría y los ejemplos comerciales son
datos factuales.
"""
import argparse
import json
import pathlib
import sys

import httpx

HERE = pathlib.Path(__file__).parent

# Campos que este seed gestiona (solo estos se rellenan al enriquecer)
FIELDS = [
    "category", "description", "bjcp_category", "overall_impression",
    "aroma_profile", "appearance_profile", "flavor_profile",
    "mouthfeel_profile", "abv_min", "abv_max", "ibu_min", "ibu_max",
    "srm_min", "srm_max", "commercial_examples", "family",
    "family_order", "style_order",
]


def auth(client: httpx.Client, url: str, email: str, password: str) -> str:
    r = client.post(
        f"{url}/api/collections/_superusers/auth-with-password",
        json={"identity": email, "password": password},
    )
    r.raise_for_status()
    return r.json()["token"]


def existing_styles(client: httpx.Client, url: str, token: str) -> dict[str, dict]:
    out, page = {}, 1
    while True:
        r = client.get(
            f"{url}/api/collections/styles/records",
            params={"page": page, "perPage": 200},
            headers={"Authorization": token},
        )
        r.raise_for_status()
        data = r.json()
        for item in data["items"]:
            out[item["name"]] = item
        if page >= data["totalPages"]:
            return out
        page += 1


def is_empty(value) -> bool:
    return value in (None, "", 0)


def seed_styles(client: httpx.Client, url: str, token: str) -> None:
    items = json.loads((HERE / "seed" / "bjcp_styles.json").read_text(encoding="utf-8"))
    have = existing_styles(client, url, token)
    headers = {"Authorization": token}
    created = enriched = untouched = 0

    for item in items:
        # description: la UI antigua la usa; si el catálogo no la trae, se
        # deriva de la impresión general para no dejarla vacía
        item.setdefault("description", item.get("overall_impression", ""))

        current = have.get(item["name"])
        if current is None:
            r = client.post(f"{url}/api/collections/styles/records", json=item, headers=headers)
            r.raise_for_status()
            created += 1
            continue

        # Enriquecer: solo campos vacíos (no pisar ediciones del admin).
        # Excepción deliberada: family/family_order/style_order son el orden
        # editorial de ESTE catálogo y se aplican siempre para mantener la
        # coherencia del listado.
        patch = {
            k: v for k, v in item.items()
            if k in FIELDS and (
                k in ("family", "family_order", "style_order") or is_empty(current.get(k))
            ) and current.get(k) != v
        }
        if patch:
            r = client.patch(
                f"{url}/api/collections/styles/records/{current['id']}",
                json=patch, headers=headers,
            )
            r.raise_for_status()
            enriched += 1
        else:
            untouched += 1

    print(f"styles BJCP: {created} creados, {enriched} enriquecidos, {untouched} ya completos "
          f"({len(items)} en el catálogo del seed)")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="http://localhost:8090")
    p.add_argument("--email", required=True)
    p.add_argument("--password", required=True)
    args = p.parse_args()

    with httpx.Client(timeout=15) as client:
        try:
            token = auth(client, args.url, args.email, args.password)
        except Exception as e:
            sys.exit(f"No se pudo autenticar contra PocketBase: {e}")
        seed_styles(client, args.url, token)
