import { OCR_URL } from "./config";

export interface MatchedEntity {
  id: string | null;
  name: string | null;
  raw: string;
  score: number;
}
export interface ScanItem {
  line: string;
  brewery: MatchedEntity | null;
  style: MatchedEntity | null;
  /** Cerveza del catálogo `beers` si el bloque matcheó una ficha completa */
  beer?: MatchedEntity | null;
  beer_name: string | null;
  /** Precio leído en la pizarra (solo lo extrae el refuerzo Gemini Vision) */
  price?: string | null;
  confidence: number;
  /** Quién leyó este bloque: "paddle" (por defecto) o "vision" (refuerzo) */
  source?: string;
  /** UUID si la línea disparó enriquecimiento web en background (ver collection `enrichments`) */
  enrichment_id?: string | null;
}

/**
 * Sube la foto de la pizarra al microservicio OCR.
 * `barId` (opcional): solo cuando la detección por proximidad fue CLARO —
 * habilita el desempate por historial de bar (Fase 3) en el matching.
 */
export async function scanBoard(
  imageUri: string,
  barId?: string | null
): Promise<{ items: ScanItem[]; raw: unknown[] }> {
  const form = new FormData();
  // @ts-expect-error — React Native FormData file
  form.append("image", { uri: imageUri, name: "board.jpg", type: "image/jpeg" });
  if (barId) form.append("bar_id", barId);
  const res = await fetch(`${OCR_URL}/ocr`, { method: "POST", body: form });
  if (!res.ok) throw new Error(`OCR ${res.status}`);
  return res.json();
}
