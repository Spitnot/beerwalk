import { Linking, Pressable, Text, View } from "react-native";
import { Screen } from "@/components/Screen";
import { palette, radius, spacing, type } from "@/theme";
import { BJCP_DISCLAIMER, BJCP_URL } from "@/lib/bjcp";

export default function Ajustes() {
  return (
    <Screen title="Ajustes">
      <View style={{ gap: spacing(3) }}>
        <Text style={type.body}>🌐 Idioma: Català / Castellano / English</Text>
        <Text style={type.body}>🔔 Notificaciones (post-MVP)</Text>
        <Text style={type.body}>🗑️ Borrar datos de invitado</Text>
      </View>

      <View
        style={{
          marginTop: spacing(5),
          backgroundColor: palette.surface,
          borderRadius: radius.md,
          borderWidth: 1,
          borderColor: palette.line,
          padding: spacing(3),
          gap: spacing(2),
        }}
      >
        <Text style={{ ...type.body, fontWeight: "800" }}>Acerca de</Text>
        <Text style={{ ...type.soft, lineHeight: 18 }}>{BJCP_DISCLAIMER}</Text>
        <Pressable onPress={() => Linking.openURL(BJCP_URL)}>
          <Text style={{ ...type.soft, fontWeight: "800", color: palette.brandDark }}>
            Abrir la guía oficial en bjcp.org →
          </Text>
        </Pressable>
      </View>
    </Screen>
  );
}
