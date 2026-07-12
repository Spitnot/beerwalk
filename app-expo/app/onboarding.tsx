import { Pressable, Text, View } from "react-native";
import { useRouter } from "expo-router";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { palette, radius, spacing, type } from "@/theme";

export default function Onboarding() {
  const router = useRouter();

  async function start() {
    await AsyncStorage.setItem("onboarding_done", "1").catch(() => {});
    router.replace("/(tabs)/home");
  }
  return (
    <View style={{ flex: 1, backgroundColor: palette.brand, justifyContent: "flex-end", padding: spacing(6) }}>
      <Text style={{ fontSize: 56 }}>🍺</Text>
      <Text style={{ fontSize: 36, fontWeight: "800", color: "#3D2A08", marginBottom: spacing(2) }}>BeerWalk</Text>
      <Text style={{ ...type.body, color: "#3D2A08", marginBottom: spacing(8) }}>
        Escanea la pizarra de cualquier bar, descubre qué hay de grifo cerca de ti y comparte tus hallazgos. Sin cuenta, sin fricción.
      </Text>
      <Pressable
        onPress={start}
        style={{ backgroundColor: palette.ink, borderRadius: radius.pill, padding: spacing(4), alignItems: "center" }}
      >
        <Text style={{ color: "#FFF", fontWeight: "800", fontSize: 16 }}>Empezar a caminar</Text>
      </Pressable>
    </View>
  );
}
