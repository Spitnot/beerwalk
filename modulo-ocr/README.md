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

## Notas

- La primera petición a `/ocr` tarda ~10-30s: PaddleOCR descarga y carga el
  modelo. En Docker los modelos se cachean en el volumen `ocr_models`.
- `MATCH_THRESHOLD` (env, por defecto 78) controla lo estricto del fuzzy match.
  Bájalo si las pizarras manuscritas dan pocos matches; súbelo si hay falsos
  positivos.
- Añade fotos reales de pizarras a `tests/fixtures/` a medida que las tengas:
  son oro para calibrar el umbral.
