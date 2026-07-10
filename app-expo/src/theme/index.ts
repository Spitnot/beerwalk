/**
 * Sistema de diseño BeerWalk — app social viva tipo Untappd.
 * Paleta derivada de la propia cerveza: cada estilo tiene su color
 * (ámbar IPA, negro stout, dorado lager...) y ese color tiñe cards y badges.
 * Tipografía redondeada (Nunito vía expo-google-fonts cuando se integre;
 * de momento la fuente del sistema con pesos altos).
 */
export const palette = {
  // neutros cálidos, fondo tipo "papel de bar"
  bg: "#FBF7F0",
  surface: "#FFFFFF",
  ink: "#26201A",
  inkSoft: "#6E6257",
  line: "#EAE1D4",
  // marca
  brand: "#F2A33C",      // ámbar principal
  brandDark: "#C97E1B",
  danger: "#D94F35",
  success: "#3E9C5C",
};

/** Color protagonista por categoría de estilo (se aplica a badge + card) */
export const styleColors: Record<string, { bg: string; fg: string }> = {
  IPA:    { bg: "#F2A33C", fg: "#3D2A08" }, // ámbar
  Lager:  { bg: "#F6D66B", fg: "#4A3A05" }, // dorado
  Stout:  { bg: "#2E211C", fg: "#F5EDE3" }, // negro/marrón
  Sour:   { bg: "#E86FA4", fg: "#3D0A22" }, // rosa fruta
  Trigo:  { bg: "#F0E3B2", fg: "#4A3A05" },
  Belga:  { bg: "#C97E1B", fg: "#FFF6E8" },
  Ale:    { bg: "#D98E4A", fg: "#3D2408" },
  Fuerte: { bg: "#7A3B2E", fg: "#FBEDE5" },
  default:{ bg: "#EAE1D4", fg: "#26201A" },
};

export const radius = { sm: 10, md: 16, lg: 24, pill: 999 };

export const spacing = (n: number) => n * 4;

export const type = {
  h1: { fontSize: 28, fontWeight: "800" as const, color: palette.ink },
  h2: { fontSize: 20, fontWeight: "800" as const, color: palette.ink },
  body: { fontSize: 15, color: palette.ink },
  soft: { fontSize: 13, color: palette.inkSoft },
};
