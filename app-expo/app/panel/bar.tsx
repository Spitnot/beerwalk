import { Text } from "react-native";
import { Screen } from "@/components/Screen";
import { type } from "@/theme";

/** Panel rol "bar": reclamar/verificar local y ver histórico propio */
export default function PanelBar() {
  return (
    <Screen title="Tu local">
      <Text style={type.body}>1. Busca tu bar en el mapa y reclámalo.</Text>
      <Text style={type.body}>2. Verificación por el equipo (rol admin).</Text>
      <Text style={type.body}>3. Consulta el histórico de pizarras escaneadas de tu local.</Text>
    </Screen>
  );
}
