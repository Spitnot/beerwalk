# módulo-datos

Seed inicial del diccionario maestro (cerveceras españolas + estilos) y, más
adelante, scripts de scraping para ampliarlo.

## Uso

1. Levanta el entorno local (`docker compose -f docker-compose.local.yml up`)
2. Importa el schema (`pocketbase/pb_schema.json`) desde el Admin UI
3. Ejecuta:

```bash
pip install httpx
python seed_pocketbase.py --email admin@beerwalk.local --password TU_PASSWORD
```

Tras el seed, avisa al servicio OCR para que recargue su diccionario:

```bash
curl -X POST http://localhost:8000/dictionary/refresh
```

## Ampliar el diccionario

- Añade entradas a `seed/breweries_es.json` / `seed/styles.json` y vuelve a
  ejecutar el script (es idempotente por `name`).
- Los scripts de scraping futuros deberían escribir en el mismo formato JSON
  y marcar `source` con su origen para poder auditar/revertir importaciones.
