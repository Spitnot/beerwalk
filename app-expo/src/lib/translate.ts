import { TRANSLATE_URL } from "./config";
import { pb } from "./pocketbase";

/**
 * Traducción dinámica con cache en PocketBase:
 * 1. mira la collection `translations`
 * 2. si no existe, llama a LibreTranslate y guarda el resultado
 * Nunca se traduce el mismo contenido+idioma dos veces.
 */
export async function translateCached(
  contentType: string,
  contentId: string,
  text: string,
  targetLang: string,
  sourceLang = "auto"
): Promise<string> {
  const filter = `content_type="${contentType}" && content_id="${contentId}" && lang="${targetLang}"`;
  try {
    const hit = await pb.collection("translations").getFirstListItem(filter);
    return hit.text as string;
  } catch {
    /* cache miss */
  }
  const res = await fetch(`${TRANSLATE_URL}/translate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ q: text, source: sourceLang, target: targetLang, format: "text" }),
  });
  if (!res.ok) return text; // degradación elegante: mostramos el original
  const { translatedText } = await res.json();
  pb.collection("translations")
    .create({ content_type: contentType, content_id: contentId, lang: targetLang, text: translatedText })
    .catch(() => {});
  return translatedText;
}
