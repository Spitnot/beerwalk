import { Text, View } from "react-native";
import { palette, radius, spacing } from "@/theme";

/** Pill ámbar de graduación — compartido por fichas y cards de escaneo */
export function AbvPill({ abv, small = false }: { abv: number; small?: boolean }) {
  return (
    <View
      style={{
        backgroundColor: palette.brand,
        borderRadius: radius.pill,
        paddingHorizontal: spacing(2),
        paddingVertical: small ? 2 : 3,
      }}
    >
      <Text style={{ fontSize: small ? 11 : 12, fontWeight: "800", color: "#3D2A08" }}>
        {abv}%{small ? "" : " vol."}
      </Text>
    </View>
  );
}
