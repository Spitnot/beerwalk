import { Pressable, Text, View } from "react-native";
import { Link } from "expo-router";
import { Screen } from "@/components/Screen";
import { BarCard } from "@/components/BarCard";
import { palette, radius, spacing, type } from "@/theme";
import { mockBars } from "@/mocks";
import { t } from "@/i18n";

export default function Home() {
  return (
    <Screen title="BeerWalk">
      {/* Mapa reducido: placeholder hasta integrar MapLibre (ver explorar.tsx) */}
      <Link href="/explorar" asChild>
        <Pressable
          style={{
            height: 140,
            borderRadius: radius.lg,
            backgroundColor: "#DCE8DF",
            alignItems: "center",
            justifyContent: "center",
            marginBottom: spacing(4),
          }}
        >
          <Text style={{ ...type.body, fontWeight: "800" }}>🗺️ {t("nearby_bars")} — toca para explorar</Text>
        </Pressable>
      </Link>

      <Text style={{ ...type.h2, marginBottom: spacing(3) }}>Pizarras recientes</Text>
      <View>
        {mockBars.map((bar) => (
          <BarCard key={bar.id} bar={bar} />
        ))}
      </View>
    </Screen>
  );
}
