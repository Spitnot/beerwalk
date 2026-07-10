# 01 — Entorno de desarrollo local

Objetivo: levantar PocketBase + OCR + LibreTranslate con UN comando y dejar
todo listo para conectar la app Expo.

## Requisitos

- Docker Desktop (o Docker Engine + plugin compose). Comprueba: `docker compose version`
- Python 3.11+ (solo para el script de seed)
- Node 20+ (para la app Expo)

## Paso 1 — Configuración

```bash
cd beerwalk
cp .env.example .env
```

Edita `.env`:
- `PB_ADMIN_PASSWORD`: pon una contraseña tuya (mínimo 10 caracteres).
- `EXPO_PUBLIC_*`: pon la IP local de tu ordenador (paso 5).

## Paso 2 — Levantar los servicios

```bash
docker compose -f docker-compose.local.yml up --build
```

La primera vez tarda: la imagen del OCR instala PaddlePaddle (~1,5 GB) y
LibreTranslate descarga los modelos es/ca/en. Las siguientes veces es
cuestión de segundos gracias a la cache y los volúmenes.

Sabrás que está todo arriba cuando puedas abrir:
- PocketBase Admin: http://localhost:8090/_/  (entra con PB_ADMIN_EMAIL/PASSWORD)
- OCR health:       http://localhost:8000/health  → `{"status":"ok"}`
- LibreTranslate:   http://localhost:5000  (UI web de prueba)

## Paso 3 — Importar el schema de PocketBase

1. Abre http://localhost:8090/_/ y entra como superusuario.
2. Ve a **Settings → Import collections**.
3. Pega el contenido de `pocketbase/pb_schema.json` y confirma.
4. Verifica que aparecen: users, breweries, styles, bars, scans, scan_items,
   ratings, follows, translations.

> Si tu versión de PocketBase rechaza el import (el formato cambia entre
> versiones), crea las collections a mano con los campos del JSON: son pocas
> y el JSON sirve de referencia exacta de nombres, tipos y reglas.

## Paso 4 — Seed del diccionario maestro

```bash
pip install httpx
python modulo-datos/seed_pocketbase.py \
  --email admin@beerwalk.local --password TU_PASSWORD
curl -X POST http://localhost:8000/dictionary/refresh
```

## Paso 5 — Probar el OCR sin app

```bash
cd modulo-ocr
python tests/fixtures/generar_pizarra_prueba.py   # crea una pizarra sintética
curl -F "image=@tests/fixtures/pizarra_prueba.png" http://localhost:8000/ocr | python -m json.tool
```

Deberías ver items con cervecera/estilo matcheados y su confianza.
La primera llamada tarda 10-30s (carga del modelo); las siguientes ~1-3s.

## Paso 6 — La app en tu móvil

Sigue `docs/02-app-expo-movil.md`.

## Comandos útiles

```bash
docker compose -f docker-compose.local.yml logs -f ocr   # logs de un servicio
docker compose -f docker-compose.local.yml down          # parar todo
docker compose -f docker-compose.local.yml down -v       # ⚠️ borra también los datos
```
