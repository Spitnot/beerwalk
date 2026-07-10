import { Text, View } from "react-native";
import { Screen } from "@/components/Screen";
import { spacing, type } from "@/theme";

export default function Ajustes() {
  return (
    <Screen title="Ajustes">
      <View style={{ gap: spacing(3) }}>
        <Text style={type.body}>🌐 Idioma: Català / Castellano / English</Text>
        <Text style={type.body}>🔔 Notificaciones (post-MVP)</Text>
        <Text style={type.body}>🗑️ Borrar datos de invitado</Text>
      </View>
    </Screen>
  );
}
