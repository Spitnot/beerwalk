/**
 * Utilidades del catálogo de estilos basado en la guía BJCP 2023.
 * Los textos del catálogo están redactados por nosotros (parafraseados);
 * los rangos ABV/IBU/SRM son datos factuales de la guía.
 */

export const BJCP_URL = "https://www.bjcp.org/style/2021/beer/";

export const BJCP_DISCLAIMER =
  "La clasificación de estilos utiliza como referencia la guía BJCP 2023 " +
  "(Beer Judge Certification Program), organización sin ánimo de lucro dedicada " +
  "a la formación de jueces de cerveza — como BeerWalk, sin fines comerciales. " +
  "Los textos descriptivos están redactados por nosotros a partir de esa guía, " +
  "no son una reproducción oficial. La guía completa y autorizada está en bjcp.org.";

/** Campos BJCP de un estilo (todos opcionales: catálogo en expansión) */
export interface StyleBjcp {
  bjcp_category?: string;
  overall_impression?: string;
  aroma_profile?: string;
  appearance_profile?: string;
  flavor_profile?: string;
  mouthfeel_profile?: string;
  abv_min?: number;
  abv_max?: number;
  ibu_min?: number;
  ibu_max?: number;
  srm_min?: number;
  srm_max?: number;
  commercial_examples?: string;
  family?: string;
  family_order?: number;
  style_order?: number;
}

/** Aproximación estándar del color SRM en hex (para el swatch de color) */
const SRM_HEX: [number, string][] = [
  [2, "#FFD878"], [3, "#FFCA5A"], [4, "#FFBF42"], [5, "#FBB123"],
  [6, "#F8A600"], [8, "#EA8F00"], [10, "#DE7C00"], [12, "#CF6900"],
  [14, "#C35900"], [17, "#B04500"], [20, "#9B3200"], [24, "#821E00"],
  [29, "#660D00"], [35, "#520907"], [40, "#470606"],
];

export function srmToHex(srm: number): string {
  let hex = SRM_HEX[0][1];
  for (const [value, color] of SRM_HEX) {
    if (srm >= value) hex = color;
  }
  return hex;
}

/** Punto medio del rango de color del estilo, para pintar un solo swatch */
export function styleColorHex(s: StyleBjcp): string | null {
  if (!s.srm_min && !s.srm_max) return null;
  return srmToHex(((s.srm_min ?? s.srm_max ?? 0) + (s.srm_max ?? s.srm_min ?? 0)) / 2);
}
