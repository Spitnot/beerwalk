import { Tabs } from "expo-router";
import { Text } from "react-native";
import { palette } from "@/theme";
import { t } from "@/i18n";

const icon = (glyph: string) => ({ color }: { color: string }) => (
  <Text style={{ fontSize: 20, color }}>{glyph}</Text>
);

export default function TabsLayout() {
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: palette.brandDark,
        tabBarInactiveTintColor: palette.inkSoft,
        tabBarStyle: { backgroundColor: palette.surface, borderTopColor: palette.line },
      }}
    >
      <Tabs.Screen name="home" options={{ title: t("home"), tabBarIcon: icon("🏠") }} />
      <Tabs.Screen name="explorar" options={{ title: t("map"), tabBarIcon: icon("🗺️") }} />
      <Tabs.Screen name="escanear" options={{ title: t("scan"), tabBarIcon: icon("📷") }} />
      <Tabs.Screen name="buscar" options={{ title: t("search"), tabBarIcon: icon("🔍") }} />
      <Tabs.Screen name="perfil" options={{ title: t("profile"), tabBarIcon: icon("🍺") }} />
    </Tabs>
  );
}
