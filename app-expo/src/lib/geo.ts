/** Distancia Haversine en km — sin PostGIS, suficiente para "bares cerca" */
export function haversineKm(
  a: { lat: number; lng: number },
  b: { lat: number; lng: number }
): number {
  const R = 6371;
  const dLat = ((b.lat - a.lat) * Math.PI) / 180;
  const dLng = ((b.lng - a.lng) * Math.PI) / 180;
  const s =
    Math.sin(dLat / 2) ** 2 +
    Math.cos((a.lat * Math.PI) / 180) *
      Math.cos((b.lat * Math.PI) / 180) *
      Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(s));
}

// ── Detección de bar por proximidad al escanear ──────────────────────────
//
// Tres casos:
//   CLARO            → un bar inequívocamente cerca: su id viaja a POST /ocr
//                      (desbloquea la Fase 3 del desempate) y se preselecciona.
//   AMBIGUO          → varios bares plausibles: el usuario decide, /ocr va sin bar_id.
//   SIN_COINCIDENCIA → nada cerca (o sin GPS/permiso): /ocr va sin bar_id.
// Fallo seguro: cualquier error de GPS/permiso degrada a SIN_COINCIDENCIA;
// la detección NUNCA bloquea ni rompe el escaneo.

const MATCH_RADIUS_KM = 0.25; // radio para considerar un bar candidato
const CLEAR_MAX_KM = 0.12; // CLARO: el más cercano a menos de 120 m...
const CLEAR_GAP_KM = 0.1; // ...y sacándole más de 100 m al segundo
const GPS_TIMEOUT_MS = 4000; // más que esto y escaneamos sin bar

export interface BarGeo {
  id: string;
  name: string;
  lat: number;
  lng: number;
}

export interface ProximityResult {
  kind: "CLARO" | "AMBIGUO" | "SIN_COINCIDENCIA";
  /** Solo en CLARO: el bar detectado */
  bar: (BarGeo & { distanceKm: number }) | null;
}

/** Clasificación pura (testeable sin GPS): posición + bares → caso */
export function classifyProximity(
  pos: { lat: number; lng: number },
  bars: BarGeo[]
): ProximityResult {
  const candidates = bars
    .map((b) => ({ ...b, distanceKm: haversineKm(pos, b) }))
    .filter((b) => b.distanceKm <= MATCH_RADIUS_KM)
    .sort((a, b) => a.distanceKm - b.distanceKm);

  if (candidates.length === 0) return { kind: "SIN_COINCIDENCIA", bar: null };

  const [first, second] = candidates;
  const isClear =
    first.distanceKm <= CLEAR_MAX_KM &&
    (!second || second.distanceKm - first.distanceKm > CLEAR_GAP_KM);

  return isClear ? { kind: "CLARO", bar: first } : { kind: "AMBIGUO", bar: null };
}

/**
 * Detección completa con GPS (expo-location), con fallo seguro y timeout.
 * Usa la última posición conocida si existe (instantánea) y solo pide una
 * lectura fresca como fallback.
 */
export async function detectNearbyBar(bars: BarGeo[]): Promise<ProximityResult> {
  const none: ProximityResult = { kind: "SIN_COINCIDENCIA", bar: null };
  if (bars.length === 0) return none;
  try {
    const Location = await import("expo-location");
    const { status } = await Location.requestForegroundPermissionsAsync();
    if (status !== "granted") return none;

    const withTimeout = <T,>(p: Promise<T>): Promise<T | null> =>
      Promise.race([p, new Promise<null>((r) => setTimeout(() => r(null), GPS_TIMEOUT_MS))]);

    let pos = await Location.getLastKnownPositionAsync();
    if (!pos) {
      pos = await withTimeout(
        Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced })
      );
    }
    if (!pos) return none;
    return classifyProximity(
      { lat: pos.coords.latitude, lng: pos.coords.longitude },
      bars
    );
  } catch {
    return none; // sin GPS no hay bar_id, pero el escaneo sigue igual
  }
}
