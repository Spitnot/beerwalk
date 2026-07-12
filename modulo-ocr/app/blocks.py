"""
Agrupamiento espacial de líneas OCR en bloques usando las coordenadas box.

Las pizarras reales suelen ser rejillas de paneles (una cerveza por panel).
PaddleOCR devuelve líneas sueltas; sin agrupar, "Basqueland" y "Pink
Flamingos" del mismo panel se matchean por separado y todo falla. Aquí se
unen por proximidad espacial (union-find): dos líneas comparten bloque si
están apiladas verticalmente con solape horizontal, o una al lado de la
otra a la misma altura (precios, ABV...).
"""
from statistics import median


def _bbox(line: dict) -> tuple[float, float, float, float]:
    xs = [p[0] for p in line["box"]]
    ys = [p[1] for p in line["box"]]
    return min(xs), min(ys), max(xs), max(ys)


def _same_block(a: dict, b: dict) -> bool:
    ha, hb = a["y1"] - a["y0"], b["y1"] - b["y0"]
    h = min(ha, hb) or 1.0

    # Solape horizontal (proporción sobre la línea más estrecha)
    overlap_x = min(a["x1"], b["x1"]) - max(a["x0"], b["x0"])
    narrow = min(a["x1"] - a["x0"], b["x1"] - b["x0"]) or 1.0

    # Caso 1: apiladas verticalmente (título / subtítulo del mismo panel).
    # 0.7·h calibrado con la rejilla real: los saltos dentro de un panel son
    # de 0-15px y el hueco entre filas de paneles de 30-64px; con 0.9·h la
    # letra grande (h~38-45) saltaba de una fila a la siguiente.
    gap_y = max(a["y0"], b["y0"]) - min(a["y1"], b["y1"])
    if overlap_x / narrow > 0.3 and gap_y < 0.7 * max(ha, hb):
        return True

    # Caso 2: lado a lado a la misma altura (precio junto al ABV, etc.).
    # Umbral calibrado con la pizarra en rejilla real: la separación entre
    # paneles adyacentes (35-59px, letra de h~15-47) debe quedar FUERA y los
    # fragmentos del mismo panel (10-25px) dentro; con letra grande 1.2·h se
    # comía el hueco entre paneles, 0.8·h los separa.
    overlap_y = min(a["y1"], b["y1"]) - max(a["y0"], b["y0"])
    gap_x = max(a["x0"], b["x0"]) - min(a["x1"], b["x1"])
    if overlap_y > 0.5 * h and gap_x < 0.8 * h:
        return True

    return False


def group_lines(lines: list[dict]) -> list[dict]:
    """[{text, confidence, box}] -> bloques [{text, confidence, lines, box}]
    en orden de lectura (por filas y, dentro de cada fila, de izq. a dcha.)."""
    if not lines:
        return []

    items = []
    for ln in lines:
        x0, y0, x1, y1 = _bbox(ln)
        items.append({**ln, "x0": x0, "y0": y0, "x1": x1, "y1": y1})

    # Union-find
    parent = list(range(len(items)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            if _same_block(items[i], items[j]):
                ri, rj = find(i), find(j)
                if ri != rj:
                    parent[rj] = ri

    clusters: dict[int, list[dict]] = {}
    for i, it in enumerate(items):
        clusters.setdefault(find(i), []).append(it)

    blocks = []
    for members in clusters.values():
        members.sort(key=lambda m: (m["y0"], m["x0"]))
        blocks.append(
            {
                "text": " ".join(m["text"].strip() for m in members if m["text"].strip()),
                "confidence": sum(m["confidence"] for m in members) / len(members),
                "lines": [m["text"] for m in members],
                "x0": min(m["x0"] for m in members),
                "y0": min(m["y0"] for m in members),
                "x1": max(m["x1"] for m in members),
                "y1": max(m["y1"] for m in members),
            }
        )

    # Orden de lectura: agrupar bloques en filas por su centro vertical
    blocks.sort(key=lambda b: (b["y0"] + b["y1"]) / 2)
    med_h = median(b["y1"] - b["y0"] for b in blocks) or 1.0
    rows: list[list[dict]] = []
    for b in blocks:
        yc = (b["y0"] + b["y1"]) / 2
        if rows and yc - (rows[-1][0]["y0"] + rows[-1][0]["y1"]) / 2 < 0.6 * med_h:
            rows[-1].append(b)
        else:
            rows.append([b])
    ordered = []
    for row in rows:
        ordered.extend(sorted(row, key=lambda b: b["x0"]))
    return ordered
