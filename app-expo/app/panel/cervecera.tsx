import { useState } from "react";
import { Pressable, ScrollView, Text, TextInput, View } from "react-native";
import { Screen } from "@/components/Screen";
import { palette, radius, spacing, type } from "@/theme";
import { pb } from "@/lib/pocketbase";
import { useClaimable, type ClaimableRecord } from "@/lib/useClaimable";

interface BreweryRecord extends ClaimableRecord {
  origin: string;
  description: string;
  source_url: string;
}

const inputStyle = {
  borderWidth: 1, borderColor: palette.line, borderRadius: radius.md,
  padding: spacing(3), ...type.body,
} as const;

/** Panel rol "cervecera": reclamar la marca y editar su información básica */
export default function PanelCervecera() {
  const { mine, query, setQuery, results, claim, error, reload } = useClaimable<BreweryRecord>("breweries");
  const [origin, setOrigin] = useState("");
  const [description, setDescription] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [saved, setSaved] = useState(false);

  // Sincronizar el formulario cuando llega/cambia la ficha reclamada
  if (mine && origin === "" && description === "" && sourceUrl === "" && (mine.origin || mine.description || mine.source_url)) {
    setOrigin(mine.origin ?? "");
    setDescription(mine.description ?? "");
    setSourceUrl(mine.source_url ?? "");
  }

  async function save() {
    if (!mine) return;
    setSaved(false);
    try {
      // verified nunca viaja aquí: el schema lo bloquearía igualmente
      // (solo el equipo admin puede tocarlo), pero no hace falta pedirlo.
      await pb.collection("breweries").update(mine.id, { origin, description, source_url: sourceUrl });
      setSaved(true);
      reload();
    } catch {
      setSaved(false);
    }
  }

  if (mine === undefined) {
    return (
      <Screen title="Tu cervecera">
        <Text style={type.soft}>Cargando…</Text>
      </Screen>
    );
  }

  if (!mine) {
    return (
      <Screen title="Tu cervecera">
        <ScrollView contentContainerStyle={{ gap: spacing(3) }}>
          <Text style={type.body}>Reclama tu marca del diccionario maestro y edita su información básica.</Text>
          <TextInput
            value={query}
            onChangeText={setQuery}
            placeholder="Busca tu cervecera por nombre…"
            style={inputStyle}
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
            </View>
          ))}
        </ScrollView>
      </Screen>
    );
  }

  return (
    <Screen title="Tu cervecera">
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

        <Text style={type.soft}>Origen</Text>
        <TextInput value={origin} onChangeText={setOrigin} style={inputStyle} placeholder="Ciudad, país" />
        <Text style={type.soft}>Descripción</Text>
        <TextInput value={description} onChangeText={setDescription} style={[inputStyle, { minHeight: 80 }]} multiline placeholder="Información no disponible todavía" />
        <Text style={type.soft}>Web oficial</Text>
        <TextInput value={sourceUrl} onChangeText={setSourceUrl} style={inputStyle} placeholder="https://…" autoCapitalize="none" />

        <Pressable onPress={save} style={{ backgroundColor: palette.brand, borderRadius: radius.lg, padding: spacing(4), alignItems: "center" }}>
          <Text style={{ fontWeight: "800", color: palette.onBrand }}>Guardar cambios</Text>
        </Pressable>
        {saved && <Text style={{ color: palette.success }}>Guardado.</Text>}
      </ScrollView>
    </Screen>
  );
}
