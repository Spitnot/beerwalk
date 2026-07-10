/**
 * i18n estático de interfaz (ca/es/en). El contenido dinámico se traduce
 * aparte vía LibreTranslate (src/lib/translate.ts).
 * MVP sin dependencias: un diccionario plano + hook.
 */
import { useState } from "react";

export type Lang = "ca" | "es" | "en";

const dict: Record<Lang, Record<string, string>> = {
  ca: {
    scan: "Escanejar",
    map: "Mapa",
    home: "Inici",
    search: "Cercar",
    profile: "Perfil",
    scan_board: "Escaneja la pissarra",
    confirm: "Confirmar",
    nearby_bars: "Bars a prop",
  },
  es: {
    scan: "Escanear",
    map: "Mapa",
    home: "Inicio",
    search: "Buscar",
    profile: "Perfil",
    scan_board: "Escanea la pizarra",
    confirm: "Confirmar",
    nearby_bars: "Bares cerca",
  },
  en: {
    scan: "Scan",
    map: "Map",
    home: "Home",
    search: "Search",
    profile: "Profile",
    scan_board: "Scan the board",
    confirm: "Confirm",
    nearby_bars: "Bars nearby",
  },
};

let current: Lang = "es";
export const setLang = (l: Lang) => (current = l);
export const t = (key: string) => dict[current][key] ?? key;
export const useLang = () => useState<Lang>(current);
