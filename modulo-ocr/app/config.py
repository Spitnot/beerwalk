import os

POCKETBASE_URL = os.getenv("POCKETBASE_URL", "http://localhost:8090")
OCR_LANG = os.getenv("OCR_LANG", "es")
# Umbral rapidfuzz (0-100) por debajo del cual un match se descarta
MATCH_THRESHOLD = int(os.getenv("MATCH_THRESHOLD", "78"))
# Fallback local si PocketBase no responde (útil para tests aislados)
LOCAL_DICT_PATH = os.getenv(
    "LOCAL_DICT_PATH", os.path.join(os.path.dirname(__file__), "..", "tests", "fixtures")
)
