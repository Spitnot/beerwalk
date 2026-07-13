import { View, Text } from "react-native";
import { palette, radius, spacing, type } from "@/theme";

/** Campo aún sin enriquecer: placeholder explícito, nunca hueco en blanco */
export const PENDING = "Información no disponible todavía";

/** Bloque de ficha con título suave — compartido por cerveza y cervecera */
export function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <View
      style={{
        backgroundColor: palette.surface,
        borderRadius: radius.md,
        borderWidth: 1,
        borderColor: palette.line,
        padding: spacing(3),
        marginTop: spacing(3),
        gap: 6,
      }}
    >
      <Text style={{ ...type.soft, fontWeight: "800" }}>{title}</Text>
      {children}
    </View>
  );
}
