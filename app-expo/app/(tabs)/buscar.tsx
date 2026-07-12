import { useEffect, useMemo, useState } from "react";
import { Pressable, Text, TextInput, View } from "react-native";
import { Link } from "expo-router";
import { Screen } from "@/components/Screen";
import { BarCard } from "@/components/BarCard";
import { StyleBadge } from "@/components/StyleBadge";
import { palette, radius, spacing, type } from "@/theme";
import { pb } from "@/lib/pocketbase";
import { mockBars } from "@/mocks";
import type { StyleBjcp } from "@/lib/bjcp";

interface StyleRow extends StyleBjcp {
  id: string;
  name: string;
  category: string;
}

export default function Buscar() {
  const [q, setQ] = useState("");
  const [styles, setStyles] = useState<StyleRow[]>([]);

  useEffect(() => {
    // Orden editorial del catálogo BJCP: familias entre sí y estilos dentro
    // de cada familia — nunca alfabético
    pb.collection("styles")
      .getFullList<StyleRow>({
        sort: "family_order,style_order,name",
        fields: "id,name,category,family,family_order,style_order,bjcp_category",
        requestKey: null,
      })
      .then(setStyles)
      .catch(() => setStyles([]));
  }, []);

  const styleResults = useMemo(() => {
    const needle = q.trim().toLowerCase();
    const filtered = needle
      ? styles.filter(
          (s) =>
            s.name.toLowerCase().includes(needle) ||
            (s.family ?? "").toLowerCase().includes(needle)
        )
      : styles;
    // Agrupar por familia conservando el orden editorial ya aplicado
    const families: { family: string; items: StyleRow[] }[] = [];
    for (const s of filtered) {
      const family = s.family || s.category || "Otros";
      const last = families[families.length - 1];
      if (last && last.family === family) last.items.push(s);
      else families.push({ family, items: [s] });
    }
    return families;
  }, [q, styles]);

  const barResults = mockBars.filter((b) => b.name.toLowerCase().includes(q.toLowerCase()));

  return (
    <Screen title="Buscar">
      <TextInput
        value={q}
        onChangeText={setQ}
        placeholder="Bares, cerveceras, estilos…"
        placeholderTextColor={palette.inkSoft}
        style={{
          backgroundColor: palette.surface,
          borderWidth: 1,
          borderColor: palette.line,
          borderRadius: radius.pill,
          paddingHorizontal: spacing(4),
          paddingVertical: spacing(3),
          marginBottom: spacing(4),
          fontSize: 15,
        }}
      />

      {styleResults.length > 0 && (
        <View style={{ marginBottom: spacing(4) }}>
          <Text style={{ ...type.soft, fontWeight: "800", marginBottom: spacing(2) }}>ESTILOS</Text>
          {styleResults.map(({ family, items }) => (
            <View key={family} style={{ marginBottom: spacing(3) }}>
              <Text style={{ ...type.soft, marginBottom: spacing(1) }}>{family}</Text>
              <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 6 }}>
                {items.map((s) => (
                  <Link key={s.id} href={`/cerveza/${s.id}`} asChild>
                    <Pressable>
                      <StyleBadge name={s.name} />
                    </Pressable>
                  </Link>
                ))}
              </View>
            </View>
          ))}
        </View>
      )}

      {barResults.length > 0 && (
        <Text style={{ ...type.soft, fontWeight: "800", marginBottom: spacing(2) }}>BARES</Text>
      )}
      {barResults.map((bar) => (
        <BarCard key={bar.id} bar={bar} />
      ))}
    </Screen>
  );
}
