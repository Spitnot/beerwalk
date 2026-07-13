"""
módulo-datos — seed de cerveceras españolas (Bloque 3).

Uso (con el docker compose local levantado):
  pip install httpx
  python seed_breweries_es.py --url http://localhost:8090 \
      --email admin@beerwalk.local --password ... [--dry-run] [--limit N]

FUENTES Y MARCO LEGAL (verificado 2026-07-12, ver docs/ESTADO_PROYECTO.md):
  - Birrapedia y tiendas online: DESCARTADAS. Sus condiciones de uso prohíben
    el acceso fuera de su interfaz y reservan los derechos de base de datos.
  - AECAI (aecai.es/asociados/): robots.txt permite todo. Se usa SOLO como
    índice de webs oficiales (URL + pista de nombre del logo). Secciones de
    cerveceras (compromisarios y nómadas); colaboradores/distribuidores/
    tiendas se excluyen.
  - Wikidata (CC0): semilla complementaria vía SPARQL (nombre, web oficial,
    municipio).
  - La ficha se completa contra la WEB OFICIAL de cada cervecera (nombre
    canónico vía og:site_name/<title>), respetando el robots.txt de CADA
    dominio y con rate limit global entre peticiones externas.
  - `description` se deja SIEMPRE vacía a propósito: el texto de marketing de
    cada web tiene copyright. La rellenará el enriquecimiento con paráfrasis
    (misma política que los textos BJCP).

Cada ficha creada lleva source="seed", verified=false y source_url (la web
oficial confirmada o, si la web no responde, la página del índice AECAI).

Idempotente en las dos direcciones (patrón del seed BJCP):
  - Nombre nuevo (comparación normalizada, con variantes sin prefijos tipo
    "Cervezas ...") → se crea la ficha completa.
  - Nombre ya existente → SOLO se rellenan origin/source_url si están vacíos.
    Nunca se tocan verified, source ni description de fichas existentes.

Checkpoint incremental en seed/.breweries_es_checkpoint.json: cada web
consultada se apunta al momento; re-ejecutar no repite peticiones externas.
"""
import argparse
import json
import pathlib
import re
import sys
import time
import unicodedata
import urllib.robotparser
from html import unescape
from urllib.parse import urlparse

import httpx

HERE = pathlib.Path(__file__).parent
CHECKPOINT = HERE / "seed" / ".breweries_es_checkpoint.json"

AECAI_URL = "https://aecai.es/asociados/"
WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"
USER_AGENT = "Mozilla/5.0 (compatible; BeerWalkSeedBot/0.1; seed puntual de catalogo; respeta robots.txt)"
RATE_SECONDS = 1.5  # pausa mínima entre peticiones a webs externas

# Secciones de aecai.es/asociados que son cerveceras. El resto (colectivos,
# colaboradores, distribuidores, tiendas, simpatizantes) no se importa.
AECAI_SECTIONS = ("SOCIOS COMPROMISARIOS", "Socios nómadas")

SOCIAL_HOSTS = ("facebook.com", "instagram.com", "twitter.com", "x.com",
                "youtube.com", "linkedin.com", "wa.me")

# Consulta CC0: cerveceras (subclases incluidas) con país España.
SPARQL_QUERY = """
SELECT ?item ?itemLabel ?web ?lugarLabel WHERE {
  ?item wdt:P31/wdt:P279* wd:Q131734 ;
        wdt:P17 wd:Q29 .
  OPTIONAL { ?item wdt:P856 ?web . }
  OPTIONAL { ?item wdt:P131 ?lugar . }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "es,ca,eu,gl,en". }
}
"""

_last_external_call = 0.0


def throttle() -> None:
    global _last_external_call
    wait = _last_external_call + RATE_SECONDS - time.monotonic()
    if wait > 0:
        time.sleep(wait)
    _last_external_call = time.monotonic()


def domain_of(url: str) -> str:
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def normalize(name: str) -> str:
    s = unicodedata.normalize("NFKD", name.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", s).split())


def name_variants(name: str) -> set[str]:
    """Variantes conservadoras para detectar duplicados (un falso positivo
    solo significa no crear la ficha, nunca pisar una existente)."""
    base = normalize(name)
    variants = {base}
    stripped = re.sub(
        r"^(cervezas? |cervesa |cerveses |cerveceria |cervecera |cervezas artesanas |birra )+",
        "", base)
    if len(stripped) > 3:
        variants.add(stripped)
    for v in list(variants):
        no_stop = " ".join(w for w in v.split()
                           if w not in ("de", "del", "la", "el", "los", "las", "y"))
        if len(no_stop) > 3:
            variants.add(no_stop)
    return variants


# ---------------------------------------------------------------------------
# Fase 1 — índice de candidatas (AECAI + Wikidata)
# ---------------------------------------------------------------------------

def hint_from_logo(src: str) -> str:
    stem = pathlib.Path(urlparse(src).path).stem
    stem = re.sub(r"(-?logo|-?\d+)+$", "", stem, flags=re.I)
    stem = re.sub(r"^logo[-_ ]+", "", stem, flags=re.I)
    words = [w for w in re.split(r"[-_\s]+", stem) if w]
    if not words or not any(w.isalpha() for w in words):
        return ""
    return " ".join(w.capitalize() for w in words)


def fetch_aecai(client: httpx.Client) -> list[dict]:
    throttle()
    r = client.get(AECAI_URL)
    r.raise_for_status()
    raw = r.text

    headings = [(m.start(), re.sub(r"<[^>]+>", "", m.group(2)).strip())
                for m in re.finditer(r"<h([1-4])[^>]*>(.*?)</h\1>", raw, re.S)]
    out, seen = [], set()
    for i, (pos, title) in enumerate(headings):
        if title not in AECAI_SECTIONS:
            continue
        end = headings[i + 1][0] if i + 1 < len(headings) else len(raw)
        section = raw[pos:end]
        for m in re.finditer(
                r'<a[^>]+href="(https?://[^"]+)"[^>]*>(.*?)</a>',
                section, re.S):
            url = m.group(1)
            img = re.search(r'<img[^>]+src="([^"]+)"', m.group(2))
            if not img:
                continue
            logo = img.group(1)
            host = domain_of(url)
            if host.endswith("aecai.es") or any(s in host for s in SOCIAL_HOSTS):
                continue
            if host in seen:
                continue
            seen.add(host)
            out.append({"website": url, "hint": hint_from_logo(logo),
                        "origin": "", "index": "aecai"})
    return out


def fetch_wikidata(client: httpx.Client) -> list[dict]:
    # El endpoint SPARQL a veces limita agresivamente (429 con Retry-After);
    # es una fuente complementaria: si no responde, se sigue sin ella.
    r = None
    for attempt in range(3):
        throttle()
        r = client.get(WIKIDATA_SPARQL, params={"query": SPARQL_QUERY},
                       headers={"Accept": "application/sparql-results+json"})
        if r.status_code != 429:
            break
        wait = min(int(r.headers.get("Retry-After", 65) or 65), 120)
        print(f"(429 de Wikidata, reintento en {wait}s…)", end=" ", flush=True)
        time.sleep(wait)
    if r is None or r.status_code == 429:
        print("Wikidata sigue rate-limitado; se continúa solo con AECAI.")
        return []
    r.raise_for_status()
    out, seen = [], set()
    for b in r.json()["results"]["bindings"]:
        name = b.get("itemLabel", {}).get("value", "")
        web = b.get("web", {}).get("value", "")
        if not web or not name or re.fullmatch(r"Q\d+", name):
            continue  # sin web oficial no hay fuente que verificar
        host = domain_of(web)
        if host in seen:
            continue
        seen.add(host)
        out.append({"website": web, "hint": name,
                    "origin": b.get("lugarLabel", {}).get("value", ""),
                    "index": "wikidata"})
    return out


# ---------------------------------------------------------------------------
# Fase 2 — verificación contra la web oficial (robots.txt propio + rate limit)
# ---------------------------------------------------------------------------

def robots_allows(client: httpx.Client, url: str) -> bool:
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    rp = urllib.robotparser.RobotFileParser()
    try:
        throttle()
        r = client.get(robots_url)
    except httpx.HTTPError:
        return True  # sin robots alcanzable: el fetch posterior decide
    if r.status_code >= 400:
        return True  # sin robots.txt publicado = acceso permitido (estándar)
    rp.parse(r.text.splitlines())
    return rp.can_fetch(USER_AGENT, url)


GENERIC_TITLE_PARTS = {"inicio", "home", "bienvenido", "bienvenidos", "web oficial"}


def first_name_part(text: str) -> str:
    """Primer segmento no genérico de un título/site_name ('Marca | tagline',
    'Marca. Cerveza artesana de…' → 'Marca')."""
    for part in re.split(r"\s*[|–—·:]\s*|\s+-\s+|\.\s+", text):
        part = part.strip(" *.").strip()
        if part and normalize(part) not in GENERIC_TITLE_PARTS:
            return part
    return ""


def canonical_name(html: str, fallback: str) -> str:
    m = re.search(r'property=["\']og:site_name["\'][^>]+content=["\']([^"\']+)', html) \
        or re.search(r'content=["\']([^"\']+)["\'][^>]+property=["\']og:site_name', html)
    candidate = first_name_part(unescape(m.group(1))) if m else ""
    if not candidate:
        m = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
        if m:
            candidate = first_name_part(
                unescape(re.sub(r"\s+", " ", m.group(1))).strip())
    if not candidate or len(candidate) > 60 or looks_foreign(candidate):
        candidate = fallback
    return candidate.strip()


def looks_foreign(name: str) -> bool:
    """Dominios expirados acaban en manos de casinos/parkings con otro
    alfabeto (caso real: la web de una asociada servía contenido en chino)."""
    return bool(re.search(r"[Ѐ-ӿ؀-ۿ一-鿿]", name))


def check_site(client: httpx.Client, entry: dict, cache: dict) -> dict:
    """Devuelve {status, name, source_url} y lo apunta en el checkpoint."""
    host = domain_of(entry["website"])
    if host in cache:
        return cache[host]

    result = {"status": "", "name": entry["hint"], "source_url": entry["website"]}
    if not robots_allows(client, entry["website"]):
        result["status"] = "robots_disallowed"
    else:
        try:
            throttle()
            r = client.get(entry["website"])
            title = re.search(r"<title[^>]*>(.*?)</title>", r.text, re.S | re.I)
            if r.status_code < 400 and domain_of(str(r.url)) not in SOCIAL_HOSTS \
                    and not looks_foreign(title.group(1) if title else ""):
                result["status"] = "ok"
                result["name"] = canonical_name(r.text, entry["hint"])
                result["source_url"] = str(r.url)
            else:
                result["status"] = f"http_{r.status_code}"
        except httpx.HTTPError as e:
            result["status"] = f"error_{type(e).__name__}"

    result["checked_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    cache[host] = result
    CHECKPOINT.write_text(json.dumps(cache, ensure_ascii=False, indent=1),
                          encoding="utf-8")
    return result


# ---------------------------------------------------------------------------
# Fase 3 — publicación idempotente en PocketBase
# ---------------------------------------------------------------------------

def auth(client: httpx.Client, url: str, email: str, password: str) -> str:
    r = client.post(
        f"{url}/api/collections/_superusers/auth-with-password",
        json={"identity": email, "password": password},
    )
    r.raise_for_status()
    return r.json()["token"]


def existing_breweries(client: httpx.Client, url: str, token: str) -> list[dict]:
    out, page = [], 1
    while True:
        r = client.get(
            f"{url}/api/collections/breweries/records",
            params={"page": page, "perPage": 200},
            headers={"Authorization": token},
        )
        r.raise_for_status()
        data = r.json()
        out.extend(data["items"])
        if page >= data["totalPages"]:
            return out
        page += 1


def find_existing(ficha: dict, records: list[dict]) -> dict | None:
    """Duplicado si coincide el nombre (normalizado, con variantes) O el
    dominio de la web oficial — así los renombrados manuales del admin no se
    duplican al re-ejecutar. El dominio del índice AECAI no cuenta (es el
    fallback compartido de las webs caídas)."""
    wanted = name_variants(ficha["name"])
    dom = domain_of(ficha.get("source_url") or "")
    if dom == domain_of(AECAI_URL):
        dom = ""
    for rec in records:
        if wanted & name_variants(rec["name"]):
            return rec
        if dom and dom == domain_of(rec.get("source_url") or ""):
            return rec
    return None


def publish(pb: httpx.Client, url: str, token: str, fichas: list[dict],
            dry_run: bool) -> None:
    records = existing_breweries(pb, url, token)
    headers = {"Authorization": token}
    created = completed = untouched = 0

    for ficha in fichas:
        current = find_existing(ficha, records)
        if current is None:
            if not dry_run:
                r = pb.post(f"{url}/api/collections/breweries/records",
                            json=ficha, headers=headers)
                r.raise_for_status()
                records.append(r.json())
            created += 1
            print(f"  + {ficha['name']}  ({ficha['source_url']})")
            continue

        # Existente: solo rellenar huecos, nunca pisar (ni verified/source).
        patch = {k: ficha[k] for k in ("origin", "source_url")
                 if ficha.get(k) and not current.get(k)}
        if patch:
            if not dry_run:
                r = pb.patch(
                    f"{url}/api/collections/breweries/records/{current['id']}",
                    json=patch, headers=headers)
                r.raise_for_status()
            completed += 1
            print(f"  ~ {current['name']}: completado {sorted(patch)}")
        else:
            untouched += 1

    mode = " (dry-run, sin escribir)" if dry_run else ""
    print(f"breweries: {created} creadas, {completed} completadas, "
          f"{untouched} ya al día{mode}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="http://localhost:8090")
    p.add_argument("--email", required=True)
    p.add_argument("--password", required=True)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--limit", type=int, default=0,
                   help="procesar solo N candidatas (para pruebas)")
    args = p.parse_args()

    cache = {}
    if CHECKPOINT.exists():
        cache = json.loads(CHECKPOINT.read_text(encoding="utf-8"))

    web = httpx.Client(timeout=20, follow_redirects=True,
                       headers={"User-Agent": USER_AGENT})
    pb = httpx.Client(timeout=15)

    try:
        token = auth(pb, args.url, args.email, args.password)
    except Exception as e:
        sys.exit(f"No se pudo autenticar contra PocketBase: {e}")

    print("Índice AECAI…", end=" ", flush=True)
    aecai = fetch_aecai(web)
    print(f"{len(aecai)} candidatas")
    print("Semilla Wikidata…", end=" ", flush=True)
    wikidata = fetch_wikidata(web)
    print(f"{len(wikidata)} candidatas con web oficial")

    candidates, seen = [], set()
    for entry in aecai + wikidata:  # AECAI primero: índice más curado
        host = domain_of(entry["website"])
        if host not in seen:
            seen.add(host)
            candidates.append(entry)
    if args.limit:
        candidates = candidates[:args.limit]

    fichas, skipped = [], {}
    for i, entry in enumerate(candidates, 1):
        result = check_site(web, entry, cache)
        status = result["status"]
        if status == "ok":
            name = result["name"]
            source_url = result["source_url"]
        elif entry["hint"] and len(entry["hint"]) > 2:
            # Web caída/bloqueada: el nombre del índice sigue siendo un hecho.
            name = entry["hint"]
            source_url = AECAI_URL if entry["index"] == "aecai" else entry["website"]
            skipped[status] = skipped.get(status, 0) + 1
        else:
            skipped[status] = skipped.get(status, 0) + 1
            continue
        fichas.append({
            "name": name,
            "origin": entry["origin"],
            "description": "",  # copyright: la rellena el enriquecimiento
            "source": "seed",
            "verified": False,
            "source_url": source_url,
        })
        print(f"[{i}/{len(candidates)}] {name} — {status or 'cache'}")

    if skipped:
        print(f"webs no accesibles (ficha mínima o descartada): {skipped}")

    publish(pb, args.url, token, fichas, args.dry_run)


if __name__ == "__main__":
    main()
