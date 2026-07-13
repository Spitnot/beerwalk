import { useEffect, useState } from "react";
import { Pressable, ScrollView, Text, TextInput, View } from "react-native";
import { Screen } from "@/components/Screen";
import { palette, radius, spacing, type } from "@/theme";
import { pb } from "@/lib/pocketbase";
import { relativeEs } from "@/lib/time";
import { useClaimable, type ClaimableRecord } from "@/lib/useClaimable";

interface BarRecord extends ClaimableRecord {
  address: string;
}

interface ScanRow {
  id: string;
  created: string;
}

/** Panel rol "bar": reclamar/verificar el local y consultar su histórico */
export default function PanelBar() {
  const { mine, query, setQuery, results, claim, error } = useClaimable<BarRecord>("bars");
  const [history, setHistory] = useState<ScanRow[] | null>(null);

  useEffect(() => {
    if (!mine) {
      setHistory(null);
      return;
    }
    // Histórico del LOCAL: es un registro que hay que poder repasar
    // entero para auditar qué se ha escaneado — lista vertical, nunca
    // carrusel (nada debe quedar oculto por diseño).
    pb.collection("scans")
      .getFullList<ScanRow>({ filter: `bar = "${mine.id}"`, sort: "-created", requestKey: null })
      .then(setHistory)
      .catch(() => setHistory([]));
  }, [mine]);

  if (mine === undefined) {
    return (
      <Screen title="Tu local">
        <Text style={type.soft}>Cargando…</Text>
      </Screen>
    );
  }

  if (!mine) {
    return (
      <Screen title="Tu local">
        <ScrollView contentContainerStyle={{ gap: spacing(3) }}>
          <Text style={type.body}>1. Busca tu bar en el mapa y reclámalo.</Text>
          <Text style={type.body}>2. Verificación por el equipo (rol admin).</Text>
          <Text style={type.body}>3. Consulta el histórico de pizarras escaneadas de tu local.</Text>
          <TextInput
            value={query}
            onChangeText={setQuery}
            placeholder="Busca tu bar por nombre…"
            style={{ borderWidth: 1, borderColor: palette.line, borderRadius: radius.md, padding: spacing(3) }}
          />
          {error && <Text style={{ color: palette.danger }}>{error}</Text>}
          {results.map((b) => (
            <View key={b.id} style={{ borderWidth: 1, borderColor: palette.line, borderRadius: radius.md, padding: spacing(3), gap: 4 }}>
              <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
                <Text style={{ ...type.body, fontWeight: "800" }}>{b.name}</Text>
                <Pressable onPress={() => claim(b.id)} style={{ borderWidth: 1, borderColor: palette.brandDark, borderRadius: radius.pill, paddingHorizontal: spacing(3), paddingVertical: 4 }}>
                  <Text style={{ fontWeight: "800", fontSize: 12, color: palette.brandDark }}>Reclamar</Text>
                </Pressable>
              </View>
              <Text style={type.soft}>{b.address}</Text>
            </View>
          ))}
        </ScrollView>
      </Screen>
    );
  }

  return (
    <Screen title="Tu local">
      <ScrollView contentContainerStyle={{ gap: spacing(3) }}>
        <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
          <Text style={{ ...type.body, fontWeight: "800" }}>{mine.name}</Text>
          <View
            style={{
              borderWidth: 1, borderColor: palette.line, borderRadius: radius.pill,
              paddingHorizontal: spacing(3), paddingVertical: 4,
              backgroundColor: mine.verified ? palette.brand : palette.surface,
            }}
          >
            <Text style={{ fontWeight: "800", fontSize: 12, color: mine.verified ? palette.onBrand : palette.inkSoft }}>
              {mine.verified ? "Verificado" : "Pendiente de verificación"}
            </Text>
          </View>
        </View>
        {!mine.verified && (
          <Text style={type.soft}>El equipo revisará tu solicitud pronto (rol admin).</Text>
        )}

        <Text style={type.h2}>Histórico de pizarras</Text>
        {history === null ? (
          <Text style={type.soft}>Cargando…</Text>
        ) : history.length === 0 ? (
          <Text style={type.soft}>Todavía no hay pizarras escaneadas en este local.</Text>
        ) : (
          history.map((s) => (
            <View key={s.id} style={{ flexDirection: "row", justifyContent: "space-between", borderBottomWidth: 1, borderBottomColor: palette.line, paddingVertical: spacing(2) }}>
              <Text style={type.body}>Pizarra escaneada</Text>
              <Text style={type.soft}>{relativeEs(s.created)}</Text>
            </View>
          ))
        )}
      </ScrollView>
    </Screen>
  );
}
