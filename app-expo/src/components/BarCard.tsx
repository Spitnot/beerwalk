import { Pressable, Text, View } from "react-native";
import { Link } from "expo-router";
import { palette, radius, spacing, type } from "@/theme";
import { StyleBadge } from "./StyleBadge";

export function BarCard({ bar }: { bar: { id: string; name: string; address: string; rating: number; lastScan: string; styles: string[] } }) {
  return (
    <Link href={`/bar/${bar.id}`} asChild>
      <Pressable
        style={{
          backgroundColor: palette.surface,
          borderRadius: radius.lg,
          padding: spacing(4),
          marginBottom: spacing(3),
          borderWidth: 1,
          borderColor: palette.line,
          gap: spacing(2),
        }}
      >
        <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
          <Text style={type.h2}>{bar.name}</Text>
          <Text style={{ ...type.body, fontWeight: "800", color: palette.brandDark }}>★ {bar.rating}</Text>
        </View>
        <Text style={type.soft}>{bar.address} · pizarra {bar.lastScan}</Text>
        <View style={{ flexDirection: "row", gap: 6, flexWrap: "wrap" }}>
          {bar.styles.map((s) => (
            <StyleBadge key={s} name={s} />
          ))}
        </View>
      </Pressable>
    </Link>
  );
}
