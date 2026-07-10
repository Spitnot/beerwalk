import { Text, View } from "react-native";
import { radius, styleColors } from "@/theme";

/** Badge de color por estilo: el color de la cerveza es el protagonista */
export function StyleBadge({ name, category }: { name: string; category?: string }) {
  const c = styleColors[category ?? name] ?? styleColors[name.split(" ").pop() ?? ""] ?? styleColors.default;
  return (
    <View style={{ backgroundColor: c.bg, borderRadius: radius.pill, paddingHorizontal: 10, paddingVertical: 4, alignSelf: "flex-start" }}>
      <Text style={{ color: c.fg, fontWeight: "800", fontSize: 12 }}>{name}</Text>
    </View>
  );
}
