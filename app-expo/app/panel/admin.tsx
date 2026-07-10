import { Text } from "react-native";
import { Screen } from "@/components/Screen";
import { type } from "@/theme";

/** Moderación: fusionar duplicados, verificar cuentas, diccionario maestro */
export default function PanelAdmin() {
  return (
    <Screen title="Moderación">
      <Text style={type.body}>• Duplicados pendientes de fusión (bares y cerveceras)</Text>
      <Text style={type.body}>• Cuentas bar/cervecera pendientes de verificar</Text>
      <Text style={type.body}>• Diccionario maestro — tras editar, llamar a POST /dictionary/refresh del OCR</Text>
    </Screen>
  );
}
