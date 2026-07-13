import { useEffect, useState } from "react";
import { Pressable, ScrollView, Text, View } from "react-native";
import { Screen } from "@/components/Screen";
import { palette, radius, spacing, type } from "@/theme";
import { pb } from "@/lib/pocketbase";
import { OCR_URL } from "@/lib/config";

interface PendingRecord {
  id: string;
  name: string;
  claimed_by: string;
}

/** Moderación: fichas reclamadas pendientes de verificar y diccionario maestro */
export default function PanelAdmin() {
  const [pendingBars, setPendingBars] = useState<PendingRecord[] | null>(null);
  const [pendingBreweries, setPendingBreweries] = useState<PendingRecord[] | null>(null);
  const [refreshResult, setRefreshResult] = useState<string | null>(null);

  function load() {
    pb.collection("bars")
      .getFullList<PendingRecord>({ filter: 'claimed_by != "" && verified = false', sort: "-created", requestKey: null })
      .then(setPendingBars)
      .catch(() => setPendingBars([]));
    pb.collection("breweries")
      .getFullList<PendingRecord>({ filter: 'claimed_by != "" && verified = false', sort: "-created", requestKey: null })
      .then(setPendingBreweries)
      .catch(() => setPendingBreweries([]));
  }
  useEffect(load, []);

  async function verify(collection: "bars" | "breweries", id: string) {
    try {
      await pb.collection(collection).update(id, { verified: true });
      load();
    } catch {
      // sin permiso de admin: el propio schema lo bloquea, no hay nada que hacer aquí
    }
  }

  async function refreshDictionary() {
    setRefreshResult(null);
    try {
      const r = await fetch(`${OCR_URL}/dictionary/refresh`, { method: "POST" });
      const data = await r.json();
      setRefreshResult(`breweries: ${data.breweries} · styles: ${data.styles} · beers: ${data.beers}`);
    } catch {
      setRefreshResult("No se pudo contactar con el servicio OCR.");
    }
  }

  return (
    <Screen title="Moderación">
      <ScrollView contentContainerStyle={{ gap: spacing(4) }}>
        <View style={{ gap: spacing(2) }}>
          <Text style={{ ...type.soft, fontWeight: "800" }}>DUPLICADOS PENDIENTES DE FUSIÓN (BARES Y CERVECERAS)</Text>
          <Text style={type.soft}>
            Sin mecanismo de detección automática todavía — pendiente (el seed OSM genera una lista local de
            candidatos dudosos, pero no está conectada a esta pantalla).
          </Text>
        </View>

        <View style={{ gap: spacing(2) }}>
          <Text style={{ ...type.soft, fontWeight: "800" }}>CUENTAS BAR/CERVECERA PENDIENTES DE VERIFICAR</Text>
          {pendingBars === null || pendingBreweries === null ? (
            <Text style={type.soft}>Cargando…</Text>
          ) : pendingBars.length === 0 && pendingBreweries.length === 0 ? (
            <Text style={type.soft}>No hay ninguna reclamación pendiente ahora mismo.</Text>
          ) : (
            <>
              {pendingBars.map((b) => (
                <View key={b.id} style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center", borderBottomWidth: 1, borderBottomColor: palette.line, paddingVertical: spacing(2) }}>
                  <Text style={type.body}>🏪 {b.name}</Text>
                  <Pressable onPress={() => verify("bars", b.id)} style={{ borderWidth: 1, borderColor: palette.brandDark, borderRadius: radius.pill, paddingHorizontal: spacing(3), paddingVertical: 4 }}>
                    <Text style={{ fontWeight: "800", fontSize: 12, color: palette.brandDark }}>Verificar</Text>
                  </Pressable>
                </View>
              ))}
              {pendingBreweries.map((b) => (
                <View key={b.id} style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center", borderBottomWidth: 1, borderBottomColor: palette.line, paddingVertical: spacing(2) }}>
                  <Text style={type.body}>🏭 {b.name}</Text>
                  <Pressable onPress={() => verify("breweries", b.id)} style={{ borderWidth: 1, borderColor: palette.brandDark, borderRadius: radius.pill, paddingHorizontal: spacing(3), paddingVertical: 4 }}>
                    <Text style={{ fontWeight: "800", fontSize: 12, color: palette.brandDark }}>Verificar</Text>
                  </Pressable>
                </View>
              ))}
            </>
          )}
        </View>

        <View style={{ gap: spacing(2) }}>
          <Text style={{ ...type.soft, fontWeight: "800" }}>DICCIONARIO MAESTRO</Text>
          <Text style={type.soft}>Tras editar breweries/styles a mano, refresca la caché en memoria del servicio OCR.</Text>
          <Pressable onPress={refreshDictionary} style={{ borderWidth: 1, borderColor: palette.line, borderRadius: radius.lg, padding: spacing(3), alignItems: "center" }}>
            <Text style={{ fontWeight: "800", color: palette.ink }}>POST /dictionary/refresh</Text>
          </Pressable>
          {refreshResult && <Text style={type.soft}>{refreshResult}</Text>}
        </View>
      </ScrollView>
    </Screen>
  );
}
