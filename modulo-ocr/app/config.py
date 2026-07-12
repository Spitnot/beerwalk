import os

POCKETBASE_URL = os.getenv("POCKETBASE_URL", "http://localhost:8090")
OCR_LANG = os.getenv("OCR_LANG", "es")
# Umbral rapidfuzz (0-100) por debajo del cual un match se descarta
MATCH_THRESHOLD = int(os.getenv("MATCH_THRESHOLD", "78"))
# Fallback local si PocketBase no responde (útil para tests aislados)
LOCAL_DICT_PATH = os.getenv(
    "LOCAL_DICT_PATH", os.path.join(os.path.dirname(__file__), "..", "tests", "fixtures")
)

# ── Enriquecimiento automático (búsqueda web + LLM) ─────────────────────
# Credenciales de superusuario de PocketBase: el servicio crea breweries/beers.
PB_SERVICE_EMAIL = os.getenv("PB_SERVICE_EMAIL", "")
PB_SERVICE_PASSWORD = os.getenv("PB_SERVICE_PASSWORD", "")
# Instancia SearxNG propia (self-hosted, sin API key). En docker-compose es
# http://searxng:8080; desde el host, http://localhost:8888.
SEARXNG_URL = os.getenv("SEARXNG_URL", "http://localhost:8888")
# Google AI Studio (tier gratuito) — extracción/corroboración/parafraseo.
# OJO x2: (1) los modelos con versión fija (ej. gemini-2.5-flash) dejan de
# aceptar usuarios nuevos — usar alias -latest; (2) la cuota gratuita diaria
# es POR MODELO (20/día en flash): el texto va en flash-lite (bucket propio,
# límite diario mayor) y solo Vision usa flash.
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest")
# Confianza OCR mínima (0-1) para lanzar enriquecimiento de una línea.
# Con fotos reales de pizarra 0.85 puede ser exigente: ajustar según resultados.
ENRICH_MIN_CONFIDENCE = float(os.getenv("ENRICH_MIN_CONFIDENCE", "0.85"))
# Tope de tareas de enriquecimiento por escaneo (control de coste/abuso)
ENRICH_MAX_ITEMS_PER_SCAN = int(os.getenv("ENRICH_MAX_ITEMS_PER_SCAN", "5"))
# Interruptor global; además se auto-desactiva si faltan las API keys
ENRICH_ENABLED = os.getenv("ENRICH_ENABLED", "1") == "1"

# ── Refuerzo Gemini Vision (pipeline híbrido) ───────────────────────────
# PaddleOCR es siempre la primera pasada (gratis, local). Vision solo entra
# si el resultado es malo según estos umbrales.
VISION_ENABLED = os.getenv("VISION_ENABLED", "1") == "1"
GEMINI_VISION_MODEL = os.getenv("GEMINI_VISION_MODEL", os.getenv("GEMINI_MODEL", "gemini-2.5-flash"))
# Dispara Vision si más de esta fracción de bloques queda sin reconocer...
VISION_UNMATCHED_RATIO = float(os.getenv("VISION_UNMATCHED_RATIO", "0.4"))
# ...o si la confianza media de PaddleOCR cae por debajo de esto
VISION_MIN_AVG_CONFIDENCE = float(os.getenv("VISION_MIN_AVG_CONFIDENCE", "0.75"))
# Confianza nominal asignada a los bloques que aporta Vision
VISION_ITEM_CONFIDENCE = float(os.getenv("VISION_ITEM_CONFIDENCE", "0.9"))
