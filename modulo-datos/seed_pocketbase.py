"""
módulo-datos — seed inicial de cerveceras y estilos en PocketBase.

Uso (con el docker compose local levantado):
  pip install httpx
  python seed_pocketbase.py --url http://localhost:8090 \
      --email admin@beerwalk.local --password cambiame-por-favor-1234

Es idempotente: si un registro con el mismo `name` ya existe, lo salta.
"""
import argparse
import json
import pathlib
import sys

import httpx

HERE = pathlib.Path(__file__).parent


def auth(client: httpx.Client, url: str, email: str, password: str) -> str:
    r = client.post(
        f"{url}/api/collections/_superusers/auth-with-password",
        json={"identity": email, "password": password},
    )
    r.raise_for_status()
    return r.json()["token"]


def existing_names(client: httpx.Client, url: str, collection: str, token: str) -> set[str]:
    names, page = set(), 1
    while True:
        r = client.get(
            f"{url}/api/collections/{collection}/records",
            params={"page": page, "perPage": 200, "fields": "name"},
            headers={"Authorization": token},
        )
        r.raise_for_status()
        data = r.json()
        names |= {i["name"] for i in data["items"]}
        if page >= data["totalPages"]:
            return names
        page += 1


def seed(client, url, collection, filename, token):
    items = json.loads((HERE / "seed" / filename).read_text(encoding="utf-8"))
    have = existing_names(client, url, collection, token)
    created = 0
    for item in items:
        if item["name"] in have:
            continue
        r = client.post(
            f"{url}/api/collections/{collection}/records",
            json=item,
            headers={"Authorization": token},
        )
        r.raise_for_status()
        created += 1
    print(f"{collection}: {created} creados, {len(items) - created} ya existían")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="http://localhost:8090")
    p.add_argument("--email", required=True)
    p.add_argument("--password", required=True)
    args = p.parse_args()

    with httpx.Client(timeout=10) as client:
        try:
            token = auth(client, args.url, args.email, args.password)
        except Exception as e:
            sys.exit(f"No se pudo autenticar contra PocketBase: {e}")
        seed(client, args.url, "breweries", "breweries_es.json", token)
        seed(client, args.url, "styles", "styles.json", token)
        seed(client, args.url, "bars", "bars_demo.json", token)
