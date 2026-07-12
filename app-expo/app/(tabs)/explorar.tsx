import { useEffect, useState } from "react";
import { Text, View } from "react-native";
import Constants from "expo-constants";
import { Screen } from "@/components/Screen";
import { StyleBadge } from "@/components/StyleBadge";
import { BarCard } from "@/components/BarCard";
import { palette, radius, spacing, type } from "@/theme";
import { pb } from "@/lib/pocketbase";
import { mockBars } from "@/mocks";

/**
 * MapLibre GL es un módulo NATIVO: no existe en Expo Go, solo en un
 * development build (expo run:android|ios). Detectamos el entorno y cargamos
 * el módulo en runtime; en Expo Go se muestra el placeholder de siempre.
 *
 * OJO: el config plugin "@maplibre/maplibre-react-native" está quitado de
 * app.json para no romper Expo Go. Antes de hacer expo run:android|ios hay
 * que volver a añadirlo a la lista "plugins".
 */
const isExpoGo = Constants.appOwnership === "expo";
let ML: any = null;
if (!isExpoGo) {
  try {
    ML = require("@maplibre/maplibre-react-native");
  } catch {
    ML = null;
  }
}

const MAP_STYLE = "https://tiles.openfreemap.org/styles/liberty";

interface BarRecord {
  id: string;
  name: string;
  lat: number;
  lng: number;
  address: string;
}

export default function Explorar() {
  const filters = ["Hazy IPA", "Stout", "Lager", "Sour", "★ 4+"];
  const [bars, setBars] = useState<BarRecord[]>([]);

  useEffect(() => {
    pb.collection("bars")
      .getFullList<BarRecord>({ sort: "name", fields: "id,name,lat,lng,address" })
      .then(setBars)
      .catch(() => setBars(mockBars as any)); // sin backend seguimos pudiendo diseñar
  }, []);

  const MapView = ML?.MapView ?? ML?.default?.MapView;
  const Camera = ML?.Camera ?? ML?.default?.Camera;
  const PointAnnotation = ML?.PointAnnotation ?? ML?.default?.PointAnnotation;

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
          overflow: "hidden",
        }}
      >
        {MapView ? (
          <MapView style={{ flex: 1, alignSelf: "stretch" }} mapStyle={MAP_STYLE}>
            <Camera centerCoordinate={[2.15, 41.38]} zoomLevel={10.5} />
            {bars.map((b) => (
              <PointAnnotation key={b.id} id={b.id} coordinate={[b.lng, b.lat]}>
                <View
                  style={{
                    backgroundColor: palette.brand,
                    borderColor: palette.brandDark,
                    borderWidth: 2,
                    borderRadius: 999,
                    width: 22,
                    height: 22,
                    alignItems: "center",
                    justifyContent: "center",
                  }}
                >
                  <Text style={{ fontSize: 10 }}>🍺</Text>
                </View>
              </PointAnnotation>
            ))}
          </MapView>
        ) : (
          <Text style={type.soft}>
            {isExpoGo ? "Mapa disponible en el dev build (expo run:ios|android)" : "Cargando mapa…"}
          </Text>
        )}
      </View>
      {bars.map((bar: any) => (
        <BarCard
          key={bar.id}
          bar={{ rating: bar.rating ?? "–", lastScan: bar.lastScan ?? "sin escaneos aún", styles: bar.styles ?? [], ...bar }}
        />
      ))}
    </Screen>
  );
}
