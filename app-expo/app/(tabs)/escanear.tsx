import { useState } from "react";
import { ActivityIndicator, Pressable, Text, View } from "react-native";
import { useRouter } from "expo-router";
import * as ImagePicker from "expo-image-picker";
import { Screen } from "@/components/Screen";
import { palette, radius, spacing, type } from "@/theme";
import { scanBoard } from "@/lib/ocr";
import { t } from "@/i18n";

export default function Escanear() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function pickAndScan(fromCamera: boolean) {
    setError(null);
    const fn = fromCamera ? ImagePicker.launchCameraAsync : ImagePicker.launchImageLibraryAsync;
    const result = await fn({ quality: 0.8 });
    if (result.canceled) return;
    setBusy(true);
    try {
      const uri = result.assets[0].uri;
      const data = await scanBoard(uri);
      router.push({
        pathname: "/scan-resultado",
        params: { payload: JSON.stringify(data.items), imageUri: uri },
      });
    } catch (e) {
      // Si el backend no está levantado, seguimos con mocks para poder diseñar
      setError("No se pudo contactar con el OCR. Abriendo resultado de ejemplo…");
      setTimeout(() => router.push({ pathname: "/scan-resultado", params: { mock: "1" } }), 800);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Screen title={t("scan_board")}>
      <Text style={{ ...type.soft, marginBottom: spacing(4) }}>
        Apunta a la pizarra de grifos. Detectamos cerveceras y estilos y te dejamos corregir antes de guardar.
      </Text>
      {busy ? (
        <ActivityIndicator size="large" color={palette.brandDark} />
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
      {error && <Text style={{ ...type.soft, color: palette.danger, marginTop: spacing(3) }}>{error}</Text>}
    </Screen>
  );
}
