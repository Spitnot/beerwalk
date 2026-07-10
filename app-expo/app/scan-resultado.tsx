import { useState } from "react";
import { Pressable, Text, TextInput, View } from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import { palette, radius, spacing, type } from "@/theme";
import { StyleBadge } from "@/components/StyleBadge";
import { mockScanItems } from "@/mocks";
import type { ScanItem } from "@/lib/ocr";

/**
 * Resultado del escaneo: lista EDITABLE de {cervecera, estilo, confianza}.
 * Al confirmar:
 *  - crear `scan` + `scan_items` en PocketBase (created_by o device_id)
 *  - contrastar con estilos previos del bar (query paralela)
 *  - generar la card compartible (react-native-view-shot + expo-sharing)
 */
export default function ScanResultado() {
  const router = useRouter();
  const params = useLocalSearchParams<{ payload?: string; mock?: string }>();
  const initial: ScanItem[] = params.payload ? JSON.parse(params.payload) : (mockScanItems as any);
  const [items, setItems] = useState(initial);

  const edit = (i: number, field: "beer_name", value: string) => {
    const next = [...items];
    next[i] = { ...next[i], [field]: value };
    setItems(next);
  };

  return (
    <View style={{ flex: 1, backgroundColor: palette.bg, padding: spacing(4) }}>
      <Text style={{ ...type.soft, marginBottom: spacing(3) }}>
        Revisa lo detectado. Toca para corregir antes de guardar.
      </Text>
      {items.map((item, i) => (
        <View key={i} style={{ backgroundColor: palette.surface, borderRadius: radius.md, borderWidth: 1, borderColor: palette.line, padding: spacing(3), marginBottom: spacing(2), gap: 6 }}>
          <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
            <Text style={{ ...type.body, fontWeight: "800" }}>{item.brewery?.name ?? "¿Cervecera?"}</Text>
            <Text style={{ ...type.soft, color: item.confidence > 0.85 ? palette.success : palette.danger }}>
              {Math.round(item.confidence * 100)}%
            </Text>
          </View>
          <TextInput
            value={item.beer_name ?? ""}
            onChangeText={(v) => edit(i, "beer_name", v)}
            placeholder="Nombre de la cerveza"
            style={{ ...type.body, padding: 0 }}
          />
          {item.style?.name ? <StyleBadge name={item.style.name} /> : <Text style={type.soft}>Estilo sin detectar — toca para asignar</Text>}
        </View>
      ))}
      <Pressable
        onPress={() => router.back() /* TODO: guardar en PocketBase + card compartible */}
        style={{ backgroundColor: palette.brand, borderRadius: radius.lg, padding: spacing(4), alignItems: "center", marginTop: spacing(3) }}
      >
        <Text style={{ fontWeight: "800", color: "#3D2A08" }}>Confirmar y guardar</Text>
      </Pressable>
    </View>
  );
}
