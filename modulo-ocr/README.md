# módulo-ocr

Microservicio standalone (FastAPI + PaddleOCR + rapidfuzz) que convierte una
foto de pizarra en una lista de `{cervecera, estilo, nombre, confianza}`.

## Contrato de API

| Método | Ruta                  | Entrada                    | Salida |
|--------|-----------------------|----------------------------|--------|
| POST   | `/ocr`                | multipart `image` (jpg/png/webp, máx 10MB) | `OcrResponse` (ver `app/schemas.py`) |
| POST   | `/dictionary/refresh` | —                          | recarga el diccionario desde PocketBase |
| GET    | `/health`             | —                          | `{"status":"ok"}` |

El campo `raw` de la respuesta se guarda tal cual en `scans.raw_ocr_json`.

## Desarrollo aislado (sin Docker ni PocketBase)

```bash
cd modulo-ocr
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt   # paddlepaddle tarda un poco, es normal

# tests de matching (no cargan PaddleOCR, son instantáneos)
pip install pytest && pytest

# prueba end-to-end con imagen sintética
python tests/fixtures/generar_pizarra_prueba.py
uvicorn app.main:app --reload
curl -F "image=@tests/fixtures/pizarra_prueba.png" http://localhost:8000/ocr | python -m json.tool
```

Si PocketBase no está levantado, el servicio usa automáticamente los
diccionarios de `tests/fixtures/*_local.json` como fallback.

## Pipeline híbrido de lectura (PaddleOCR + refuerzo Gemini Vision)

1. **PaddleOCR** (gratis, local) lee la imagen; las líneas se agrupan en
   bloques por proximidad espacial (`app/blocks.py`, umbrales calibrados con
   `tests/fixtures/pizarra_rejilla_real.jpeg`, una rejilla real de 10 paneles).
2. Cada bloque se matchea contra el **catálogo `beers` primero** (una ficha
   resuelve cervecera+estilo+nombre de golpe) y si no, contra
   cerveceras/estilos sueltos (case-insensitive).
3. Si >`VISION_UNMATCHED_RATIO` (40%) de los bloques quedan sin reconocer, o
   la confianza media < `VISION_MIN_AVG_CONFIDENCE` (0.75), se lanza UNA
   llamada a **Gemini Vision** con la imagen completa (`app/vision.py`) y se
   fusiona: Vision manda en los bloques que Paddle falló; los que Paddle
   resolvió bien se conservan (solo se rellenan precio/estilo).
4. Cada escaneo deja una fila en la collection `ocr_metrics` (tokens reales
   incluidos) y `GET /stats` agrega el **% semanal de escaneos con refuerzo
   Vision**: según el catálogo crece con el enriquecimiento, ese % debe BAJAR
   — es la señal de que el diseño funciona (matching beers-first → menos
   Vision). Si `ocr_metrics` no existe, queda al menos el log.

## Enriquecimiento web automático

Cuando una línea con confianza OCR alta (`ENRICH_MIN_CONFIDENCE`, por defecto
0.85) no matchea ninguna cervecera del diccionario, se lanza una background
task (no bloquea la respuesta) que:

1. Busca la línea con la instancia **SearxNG propia** (self-hosted, servicio
   `searxng` del docker-compose, sin API key — misma filosofía que
   LibreTranslate). Su `searxng/settings.yml` habilita la API JSON.
2. Le pasa resultados + extractos de páginas a **Gemini** (tier gratuito de
   AI Studio) para extraer/corroborar datos y **parafrasear** la descripción
   (nunca se copia texto literal de las fuentes; `source_url` da trazabilidad).
3. Si hay coincidencia clara corroborada: crea `brewery` (si falta) y `beer`
   en PocketBase con `source="auto-web"` y las publica directamente. Los
   estilos **nunca** se auto-crean, solo se enlazan por fuzzy a los existentes.
4. Si no es concluyente: no publica nada; el item queda "sin detectar".

El resultado se escribe en la collection `enrichments` (clave: `enrichment_id`,
un UUID que también viaja en la respuesta de `/ocr`); la app lo usa para
enlazar el `scan_item` con la `beer` creada, guarde antes o después de que
termine la tarea. No se usa Untappd (contra sus ToS; si algún día hay acceso
a su API oficial, añadirla como fuente en `app/enrichment.py`).

Env vars: `PB_SERVICE_EMAIL`/`PB_SERVICE_PASSWORD` (superusuario PocketBase),
`SEARXNG_URL` (por defecto `http://localhost:8888`), `GEMINI_API_KEY`,
`GEMINI_MODEL`, `ENRICH_ENABLED`, `ENRICH_MIN_CONFIDENCE`,
`ENRICH_MAX_ITEMS_PER_SCAN` (tope por escaneo). Sin `GEMINI_API_KEY`,
la feature se desactiva sola.

> ⚠️ **Limitación MVP**: son BackgroundTasks de FastAPI, sin cola. Si el
> proceso se reinicia a mitad de una búsqueda, la tarea se pierde sin
> reintento. Si el volumen de escaneos crece, migrar a una cola real
> (ver docstring de `app/enrichment.py`).

## Notas

- La primera petición a `/ocr` tarda ~10-30s: PaddleOCR descarga y carga el
  modelo. En Docker los modelos se cachean en el volumen `ocr_models`.
- `MATCH_THRESHOLD` (env, por defecto 78) controla lo estricto del fuzzy match.
  Bájalo si las pizarras manuscritas dan pocos matches; súbelo si hay falsos
  positivos.
- Añade fotos reales de pizarras a `tests/fixtures/` a medida que las tengas:
  son oro para calibrar el umbral.
