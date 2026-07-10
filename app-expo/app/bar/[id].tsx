import { Text, View } from "react-native";
import { useLocalSearchParams } from "expo-router";
import { Screen } from "@/components/Screen";
import { StyleBadge } from "@/components/StyleBadge";
import { palette, radius, spacing, type } from "@/theme";
import { mockBars, mockTimeline } from "@/mocks";

/** Detalle de bar: pizarra actual + timeline de pizarras anteriores */
export default function BarDetail() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const bar = mockBars.find((b) => b.id === id) ?? mockBars[0];
  return (
    <Screen title={bar.name}>
      <Text style={{ ...type.soft, marginBottom: spacing(3) }}>{bar.address} · ★ {bar.rating}</Text>
      <Text style={{ ...type.h2, marginBottom: spacing(2) }}>Pizarra actual</Text>
      <View style={{ flexDirection: "row", gap: 6, flexWrap: "wrap", marginBottom: spacing(4) }}>
        {bar.styles.map((s) => <StyleBadge key={s} name={s} />)}
      </View>
      <Text style={{ ...type.h2, marginBottom: spacing(2) }}>Pizarras anteriores</Text>
      {mockTimeline.map((t) => (
        <View key={t.date} style={{ backgroundColor: palette.surface, borderWidth: 1, borderColor: palette.line, borderRadius: radius.md, padding: spacing(3), marginBottom: spacing(2) }}>
          <Text style={type.body}>{t.date} — {t.items} cervezas detectadas</Text>
        </View>
      ))}
    </Screen>
  );
}
