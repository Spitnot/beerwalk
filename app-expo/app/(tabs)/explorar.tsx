import { Text, View } from "react-native";
import { Screen } from "@/components/Screen";
import { StyleBadge } from "@/components/StyleBadge";
import { BarCard } from "@/components/BarCard";
import { palette, radius, spacing, type } from "@/theme";
import { mockBars } from "@/mocks";

/**
 * Mapa / explorar.
 * MapLibre GL (@maplibre/maplibre-react-native) es un módulo NATIVO:
 * no funciona en Expo Go, requiere un development build (expo run:android|ios).
 * Ver docs/02-app-expo-movil.md. Mientras tanto: placeholder + lista.
 *
 * Integración prevista:
 *   <MapView style={{flex:1}} mapStyle="https://tiles.openfreemap.org/styles/liberty">
 *     {bars.map(b => <PointAnnotation key={b.id} coordinate={[b.lng, b.lat]} ... />)}
 *   </MapView>
 */
export default function Explorar() {
  const filters = ["Hazy IPA", "Stout", "Lager", "Sour", "★ 4+"];
  return (
    <Screen title="Explorar">
      <View style={{ flexDirection: "row", gap: 6, flexWrap: "wrap", marginBottom: spacing(3) }}>
        {filters.map((f) => (
          <StyleBadge key={f} name={f} />
        ))}
      </View>
      <View
        style={{
          height: 260,
          borderRadius: radius.lg,
          backgroundColor: "#DCE8DF",
          alignItems: "center",
          justifyContent: "center",
          marginBottom: spacing(4),
        }}
      >
        <Text style={type.soft}>Aquí va MapLibre GL + tiles OSM (requiere dev build)</Text>
      </View>
      {mockBars.map((bar) => (
        <BarCard key={bar.id} bar={bar} />
      ))}
    </Screen>
  );
}
