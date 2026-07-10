import { Text } from "react-native";
import { Screen } from "@/components/Screen";
import { type } from "@/theme";

/** Panel rol "cervecera": reclamar marca y gestionar info básica */
export default function PanelCervecera() {
  return (
    <Screen title="Tu cervecera">
      <Text style={type.body}>Reclama tu marca del diccionario maestro y edita su información básica.</Text>
    </Screen>
  );
}
