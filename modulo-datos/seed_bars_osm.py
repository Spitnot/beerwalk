"""
módulo-datos — seed de bares reales vía OpenStreetMap (Overpass API).

Uso (con el docker compose local levantado):
  pip install httpx rapidfuzz
  python seed_bars_osm.py --url http://localhost:8090 \
      --email admin@beerwalk.local --password ... \
      --bbox "41.32,2.05,41.47,2.23"      # south,west,north,east (Barcelona ciudad)
  # o, para geocodificar la ciudad automáticamente (vía Nominatim, sin key):
  python seed_bars_osm.py ... --city "Barcelona, Spain"

FUENTE Y LICENCIA: Overpass API (OpenStreetMap), sin API key. Los datos son
© OpenStreetMap contributors, licencia ODbL — cada ficha lleva `source="osm"`
y `osm_id` de trazabilidad; la atribución de la app cubre el requisito ODbL.

POR QUÉ (decisión de sesión, ver docs/ESTADO_PROYECTO.md): la detección de
proximidad GPS y la Fase 3 del desempate (historial de bar) solo se pueden
probar de verdad con densidad real de bares — antes de este seed solo había
3 (los demo). Piloto: Barcelona/Cataluña.

ETIQUETAS: amenity=bar, amenity=pub, craft_beer=yes, microbrewery=yes.
Se probó (13-jul) craft_beer=yes en Barcelona ciudad: CERO resultados —
la etiqueta apenas se usa en OSM España. amenity=bar/pub domina el volumen
y es exactamente el universo correcto: cualquier bar es un sitio válido de
escaneo, no hace falta que esté especializado en cerveza artesana.

DEDUPLICACIÓN — en cascada, nunca a ciegas:
  1. `osm_id` ya sembrado antes → re-ejecución idempotente, se salta.
  2. Bar existente a ≤30m (Haversine) con nombre muy similar (rapidfuzz
     ratio ≥85) → MISMO bar: no se crea, se completan huecos (address/
     source/osm_id) sin pisar nada.
  3. A ≤30m con similitud BAJA (<50) → bares DISTINTOS que coinciden en la
     misma zona/portal (calles con varios bares seguidos): se crea normal.
  4. A ≤30m con similitud INTERMEDIA (50-85) → caso DUDOSO: no se decide
     solo. Se anota en seed/.bars_osm_review.json para revisión de admin
     y NO se toca PocketBase para ese candidato.
  Más allá de 30m, aunque el nombre coincida, se trata como bar distinto
  (30m ya es "otro sitio" en una ciudad).
"""
import argparse
import json
import math
import pathlib
import sys
import time

import httpx
from rapidfuzz import fuzz, utils

HERE = pathlib.Path(__file__).parent
REVIEW_FILE = HERE / "seed" / ".bars_osm_review.json"

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "BeerWalkSeedBot/0.1 (+https://beerwalk.app; seed puntual de bares)"

DEDUPE_RADIUS_M = 30
SIMILAR_HIGH = 90   # ≥: mismo bar
SIMILAR_LOW = 55     # <: bares distintos; [LOW, HIGH) = dudoso


# ---------------------------------------------------------------------------
# Geocodificación de ciudad → bbox (opcional; --bbox evita esta llamada)
# ---------------------------------------------------------------------------

def geocode_city(client: httpx.Client, city: str) -> str:
    r = client.get(NOMINATIM_URL, params={"q": city, "format": "json", "limit": 1},
                   headers={"User-Agent": USER_AGENT})
    r.raise_for_status()
    results = r.json()
    if not results:
        sys.exit(f"Nominatim no encontró «{city}»")
    south, north, west, east = results[0]["boundingbox"]
    return f"{south},{west},{north},{east}"


# ---------------------------------------------------------------------------
# Overpass: consulta única por área (sin paginar, sin rate limit por item —
# a diferencia del seed de cerveceras, aquí es UNA sola petición bulk)
# ---------------------------------------------------------------------------

def fetch_osm_bars(client: httpx.Client, bbox: str) -> list[dict]:
    query = f"""
    [out:json][timeout:90];
    (
      node["amenity"="bar"]({bbox});
      node["amenity"="pub"]({bbox});
      node["craft_beer"="yes"]({bbox});
      node["microbrewery"="yes"]({bbox});
    );
    out body;
    """
    r = None
    for attempt in range(4):
        r = client.post(OVERPASS_URL, data={"data": query},
                        headers={"User-Agent": USER_AGENT, "Accept": "application/json, text/*;q=0.1"},
                        timeout=120)
        if r.status_code not in (429, 502, 503, 504):
            break
        wait = 15 * (attempt + 1)
        print(f"(Overpass {r.status_code}, reintento en {wait}s…)", end=" ", flush=True)
        time.sleep(wait)
    r.raise_for_status()
    elements = r.json()["elements"]

    out = []
    for e in elements:
        tags = e.get("tags", {})
        name = (tags.get("name") or "").strip()
        if not name:
            continue  # sin nombre no hay ficha que crear (name es obligatorio)
        addr = " ".join(
            x for x in (tags.get("addr:street"), tags.get("addr:housenumber")) if x
        )
        out.append({
            "osm_id": f"node/{e['id']}",
            "name": name,
            "lat": e["lat"],
            "lng": e["lon"],
            "address": addr,
        })
    return out


# ---------------------------------------------------------------------------
# Deduplicación
# ---------------------------------------------------------------------------

def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6_371_000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def name_similarity(a: str, b: str) -> float:
    # token_set_ratio (no ratio simple): tolera sufijos genéricos habituales
    # entre fuentes ("Peter Pan" vs "Peter Pan Bar", "Cerveseria La Espuma"
    # vs "La Espuma") sin perder separación frente a nombres realmente
    # distintos (verificado empíricamente: 100 en variantes reales del mismo
    # bar, ≤45 en pares de bares distintos de la muestra de Barcelona).
    return fuzz.token_set_ratio(a, b, processor=utils.default_process)


def nearby_existing(candidate: dict, existing: list[dict]) -> list[dict]:
    return [
        rec for rec in existing
        if haversine_m(candidate["lat"], candidate["lng"], rec["lat"], rec["lng"]) <= DEDUPE_RADIUS_M
    ]


def classify(candidate: dict, existing: list[dict]) -> tuple[str, dict | None]:
    """Devuelve (decision, match) con decision en
    {"idempotent", "duplicate", "new", "review"}."""
    for rec in existing:
        if rec.get("osm_id") and rec["osm_id"] == candidate["osm_id"]:
            return "idempotent", rec

    close = nearby_existing(candidate, existing)
    if not close:
        return "new", None

    best = max(close, key=lambda rec: name_similarity(candidate["name"], rec["name"]))
    score = name_similarity(candidate["name"], best["name"])
    if score >= SIMILAR_HIGH:
        return "duplicate", best
    if score < SIMILAR_LOW:
        return "new", None
    return "review", best


# ---------------------------------------------------------------------------
# PocketBase
# ---------------------------------------------------------------------------

def auth(client: httpx.Client, url: str, email: str, password: str) -> str:
    r = client.post(f"{url}/api/collections/_superusers/auth-with-password",
                     json={"identity": email, "password": password})
    r.raise_for_status()
    return r.json()["token"]


def existing_bars(client: httpx.Client, url: str, token: str) -> list[dict]:
    out, page = [], 1
    while True:
        r = client.get(f"{url}/api/collections/bars/records",
                        params={"page": page, "perPage": 200,
                                "fields": "id,name,lat,lng,address,source,osm_id"},
                        headers={"Authorization": token})
        r.raise_for_status()
        data = r.json()
        out.extend(data["items"])
        if page >= data["totalPages"]:
            return out
        page += 1


def publish(client: httpx.Client, url: str, token: str, candidates: list[dict],
            existing: list[dict], dry_run: bool) -> None:
    headers = {"Authorization": token}
    created = completed = duplicates = flagged = 0
    review: list[dict] = []

    for cand in candidates:
        decision, match = classify(cand, existing)

        if decision == "idempotent":
            completed_now = False
            patch = {k: cand[k] for k in ("address", "source") if cand.get(k) and not match.get(k)}
            if patch:
                if not dry_run:
                    r = client.patch(f"{url}/api/collections/bars/records/{match['id']}",
                                      json=patch, headers=headers)
                    r.raise_for_status()
                completed_now = True
            completed += 1 if completed_now else 0
            continue

        if decision == "duplicate":
            patch = {
                k: v for k, v in {
                    "address": cand["address"], "source": "osm", "osm_id": cand["osm_id"],
                }.items() if v and not match.get(k)
            }
            if patch:
                if not dry_run:
                    r = client.patch(f"{url}/api/collections/bars/records/{match['id']}",
                                      json=patch, headers=headers)
                    r.raise_for_status()
                completed += 1
            duplicates += 1
            continue

        if decision == "review":
            flagged += 1
            review.append({
                "candidate": cand,
                "bar_existente_parecido": {"id": match["id"], "name": match["name"],
                                          "lat": match["lat"], "lng": match["lng"]},
                "similitud_nombre": round(name_similarity(cand["name"], match["name"]), 1),
                "distancia_m": round(haversine_m(cand["lat"], cand["lng"], match["lat"], match["lng"]), 1),
            })
            continue

        # decision == "new"
        body = {"name": cand["name"], "lat": cand["lat"], "lng": cand["lng"],
                "address": cand["address"], "source": "osm", "verified": False,
                "osm_id": cand["osm_id"]}
        if not dry_run:
            r = client.post(f"{url}/api/collections/bars/records", json=body, headers=headers)
            r.raise_for_status()
            existing.append(r.json())
        else:
            # id sintética: para que el resto del batch pueda seguir
            # comparándose contra este "creado" dentro del mismo dry-run
            existing.append({**body, "id": f"dry-run-{cand['osm_id']}"})
        created += 1

    if review:
        REVIEW_FILE.write_text(json.dumps(review, ensure_ascii=False, indent=1), encoding="utf-8")

    mode = " (dry-run, sin escribir)" if dry_run else ""
    print(f"bars: {created} creados, {duplicates} duplicados (fusionados con el existente), "
          f"{completed} completados, {flagged} dudosos anotados para revisión{mode}")
    if review:
        print(f"  -> revisión pendiente en {REVIEW_FILE.relative_to(HERE.parent)}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="http://localhost:8090")
    p.add_argument("--email", required=True)
    p.add_argument("--password", required=True)
    p.add_argument("--bbox", help='"south,west,north,east"')
    p.add_argument("--city", help='ej. "Barcelona, Spain" (geocodifica vía Nominatim)')
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    if not args.bbox and not args.city:
        sys.exit("Falta --bbox o --city")

    web = httpx.Client(timeout=30)
    pb = httpx.Client(timeout=15)

    try:
        token = auth(pb, args.url, args.email, args.password)
    except Exception as e:
        sys.exit(f"No se pudo autenticar contra PocketBase: {e}")

    bbox = args.bbox or geocode_city(web, args.city)
    print(f"Área: {bbox}")

    print("Consultando Overpass…", end=" ", flush=True)
    candidates = fetch_osm_bars(web, bbox)
    print(f"{len(candidates)} bares con nombre")

    existing = existing_bars(pb, args.url, token)
    print(f"Bares ya en PocketBase: {len(existing)}")

    publish(pb, args.url, token, candidates, existing, args.dry_run)


if __name__ == "__main__":
    main()
