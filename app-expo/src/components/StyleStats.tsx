import { Text, View } from "react-native";
import { palette, radius, spacing } from "@/theme";
import { styleColorHex, type StyleBjcp } from "@/lib/bjcp";

function Badge({ label, value }: { label: string; value: string }) {
  return (
    <View
      style={{
        backgroundColor: palette.surface,
        borderWidth: 1,
        borderColor: palette.line,
        borderRadius: radius.pill,
        paddingHorizontal: spacing(3),
        paddingVertical: spacing(1),
        flexDirection: "row",
        alignItems: "center",
        gap: 6,
      }}
    >
      <Text style={{ fontSize: 11, fontWeight: "800", color: palette.inkSoft }}>{label}</Text>
      <Text style={{ fontSize: 13, fontWeight: "800", color: palette.ink }}>{value}</Text>
    </View>
  );
}

/** Badges de rango ABV / IBU / color SRM de un estilo (guía BJCP) */
export function StyleStats({ style }: { style: StyleBjcp }) {
  const color = styleColorHex(style);
  const rows: [string, string][] = [];
  if (style.abv_min || style.abv_max) rows.push(["ABV", `${style.abv_min}–${style.abv_max}%`]);
  if (style.ibu_min || style.ibu_max) rows.push(["IBU", `${style.ibu_min}–${style.ibu_max}`]);
  if (rows.length === 0 && !color) return null;
  return (
    <View style={{ flexDirection: "row", flexWrap: "wrap", gap: spacing(2), alignItems: "center" }}>
      {rows.map(([label, value]) => (
        <Badge key={label} label={label} value={value} />
      ))}
      {color ? (
        <View
          style={{
            flexDirection: "row",
            alignItems: "center",
            gap: 6,
            backgroundColor: palette.surface,
            borderWidth: 1,
            borderColor: palette.line,
            borderRadius: radius.pill,
            paddingHorizontal: spacing(3),
            paddingVertical: spacing(1),
          }}
        >
          <Text style={{ fontSize: 11, fontWeight: "800", color: palette.inkSoft }}>COLOR</Text>
          <View style={{ width: 14, height: 14, borderRadius: 7, backgroundColor: color, borderWidth: 1, borderColor: palette.line }} />
          <Text style={{ fontSize: 13, fontWeight: "800", color: palette.ink }}>
            {style.srm_min}–{style.srm_max} SRM
          </Text>
        </View>
      ) : null}
    </View>
  );
}
