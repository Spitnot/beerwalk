# 🍺 BeerWalk

App móvil (React Native + Expo) para escanear pizarras de cerveza mediante OCR,
explorar un mapa de bares y una comunidad ligera de aficionados, bares y
cerveceras. 100% self-hosted: PocketBase + FastAPI/PaddleOCR + LibreTranslate,
todo dockerizado, con migración a Coolify cambiando solo variables de entorno.

## Estructura

```
beerwalk/
├── docker-compose.local.yml   # PocketBase + OCR + LibreTranslate en local
├── .env.example               # única fuente de configuración (local ↔ prod)
├── pocketbase/                # Dockerfile + schema de collections
│   └── pb_schema.json         # importar desde Admin UI → Settings → Import
├── modulo-ocr/                # microservicio FastAPI + PaddleOCR + rapidfuzz
├── modulo-datos/              # seed de cerveceras/estilos + futuros scrapers
├── app-expo/                  # app React Native (expo-router)
└── docs/
    ├── 01-desarrollo-local.md # levantar TODO en local paso a paso
    ├── 02-app-expo-movil.md   # correr la app en tu móvil físico
    └── 03-migracion-coolify.md# pasar a producción en tu VPS
```

## Arranque rápido

```bash
cp .env.example .env                                  # y edita contraseñas/IP
docker compose -f docker-compose.local.yml up --build # PocketBase + OCR + LT
# → importa pocketbase/pb_schema.json en http://localhost:8090/_/
python modulo-datos/seed_pocketbase.py --email ... --password ...
cd app-expo && npm install && cp .env.example .env && npx expo start
```

Guía detallada en `docs/01-desarrollo-local.md`.

## Contratos entre módulos

Cada módulo habla SOLO con PocketBase (REST) o expone su propia API HTTP:

| Módulo        | Depende de            | Expone                          |
|---------------|-----------------------|---------------------------------|
| modulo-datos  | PocketBase REST       | JSONs de seed                   |
| modulo-ocr    | PocketBase (dicc. con fallback local) | `POST /ocr`, `POST /dictionary/refresh` |
| app-expo      | PocketBase, OCR, LibreTranslate | —                     |

Así cada parte se desarrolla y testea de forma aislada (el OCR tiene sus
propios fixtures y funciona sin PocketBase).
