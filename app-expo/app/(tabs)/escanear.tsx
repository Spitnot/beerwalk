import { useState } from "react";
import { Pressable, Text, View } from "react-native";
import { useRouter } from "expo-router";
import * as ImagePicker from "expo-image-picker";
import { Screen } from "@/components/Screen";
import { ScanningBoard } from "@/components/EnrichmentPulse";
import { palette, radius, spacing, type } from "@/theme";
import { scanBoard } from "@/lib/ocr";
import { detectNearbyBar, type BarGeo, type ProximityResult } from "@/lib/geo";
import { pb } from "@/lib/pocketbase";
import { t } from "@/i18n";

export default function Escanear() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastUri, setLastUri] = useState<string | null>(null);

  // Detección de bar por proximidad, con fallo seguro: cualquier problema
  // (sin permiso, sin GPS, PocketBase caído) degrada a SIN_COINCIDENCIA y el
  // escaneo continúa exactamente igual que siempre, sin bar_id.
  async function detectBar(): Promise<ProximityResult> {
    try {
      const bars = await pb
        .collection("bars")
        .getFullList<BarGeo>({ fields: "id,name,lat,lng", requestKey: null });
      return await detectNearbyBar(bars);
    } catch {
      return { kind: "SIN_COINCIDENCIA", bar: null };
    }
  }

  // Si el OCR falla NO se navega ni se muestra nada de ejemplo: un fallo aquí
  // nunca debe poder acabar guardado en PocketBase como si fuera un scan real.
  async function analyze(uri: string) {
    setBusy(true);
    setError(null);
    try {
      const proximity = await detectBar();
      // Solo el caso CLARO viaja al servicio OCR (desempate de Fase 3);
      // AMBIGUO y SIN_COINCIDENCIA escanean como hasta ahora, sin bar_id.
      const clearBarId = proximity.kind === "CLARO" ? proximity.bar!.id : null;
      const data = await scanBoard(uri, clearBarId);
      setLastUri(null);
      router.push({
        pathname: "/scan-resultado",
        params: {
          payload: JSON.stringify(data.items),
          imageUri: uri,
          // Preselección del bar en la pantalla de guardado (el usuario
          // puede cambiarlo: la detección propone, no impone)
          ...(clearBarId ? { barId: clearBarId } : {}),
        },
      });
    } catch (e: any) {
      setLastUri(uri);
      setError(`No se pudo analizar la pizarra: ${e?.message ?? String(e)}`);
    } finally {
      setBusy(false);
    }
  }

  async function pickAndScan(fromCamera: boolean) {
    setError(null);
    const fn = fromCamera ? ImagePicker.launchCameraAsync : ImagePicker.launchImageLibraryAsync;
    const result = await fn({ quality: 0.8 });
    if (result.canceled) return;
    await analyze(result.assets[0].uri);
  }

  return (
    <Screen title={t("scan_board")}>
      <Text style={{ ...type.soft, marginBottom: spacing(4) }}>
        Apunta a la pizarra de grifos. Detectamos cerveceras y estilos y te dejamos corregir antes de guardar.
      </Text>
      {busy ? (
        <ScanningBoard />
      ) : (
        <View style={{ gap: spacing(3) }}>
          <Pressable
            onPress={() => pickAndScan(true)}
            style={{ backgroundColor: palette.brand, borderRadius: radius.lg, padding: spacing(5), alignItems: "center" }}
          >
            <Text style={{ fontWeight: "800", fontSize: 17, color: "#3D2A08" }}>📷 Abrir cámara</Text>
          </Pressable>
          <Pressable
            onPress={() => pickAndScan(false)}
            style={{ borderWidth: 1, borderColor: palette.line, backgroundColor: palette.surface, borderRadius: radius.lg, padding: spacing(5), alignItems: "center" }}
          >
            <Text style={{ fontWeight: "800", fontSize: 15, color: palette.ink }}>Elegir de la galería</Text>
          </Pressable>
        </View>
      )}
      {error && (
        <View style={{ marginTop: spacing(3), gap: spacing(2) }}>
          <Text style={{ ...type.soft, color: palette.danger }}>{error}</Text>
          {lastUri && !busy && (
            <Pressable
              onPress={() => analyze(lastUri)}
              style={{ borderWidth: 1, borderColor: palette.danger, borderRadius: radius.lg, padding: spacing(3), alignItems: "center" }}
            >
              <Text style={{ fontWeight: "800", color: palette.danger }}>Reintentar con la misma foto</Text>
            </Pressable>
          )}
        </View>
      )}
    </Screen>
  );
}
