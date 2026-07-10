import { ScrollView, Text, View } from "react-native";
import { palette, spacing, type } from "@/theme";

/** Contenedor base de pantalla con título grande estilo app social */
export function Screen({ title, children }: { title: string; children?: React.ReactNode }) {
  return (
    <ScrollView style={{ flex: 1, backgroundColor: palette.bg }} contentContainerStyle={{ padding: spacing(4) }}>
      <Text style={{ ...type.h1, marginBottom: spacing(4) }}>{title}</Text>
      <View>{children}</View>
    </ScrollView>
  );
}
