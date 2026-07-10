"""
Genera una imagen sintética de pizarra para probar el pipeline completo
sin necesidad de foto real:
  python tests/fixtures/generar_pizarra_prueba.py
  curl -F "image=@tests/fixtures/pizarra_prueba.png" http://localhost:8000/ocr
"""
from PIL import Image, ImageDraw, ImageFont

LINES = [
    "GRIFOS DE HOY",
    "Garage Beer Co - Soup - Hazy IPA",
    "Basqueland Imparable - West Coast IPA",
    "Espiga Garden - IPA",
    "La Pirata Black Block - Imperial Stout",
    "Cierzo Lager",
]

img = Image.new("RGB", (900, 620), "#1f2a24")  # verde pizarra
draw = ImageDraw.Draw(img)
try:
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 42)
except OSError:
    font = ImageFont.load_default()

y = 50
for line in LINES:
    draw.text((60, y), line, fill="#f5f0e6", font=font)
    y += 90

img.save("tests/fixtures/pizarra_prueba.png")
print("Guardada tests/fixtures/pizarra_prueba.png")
