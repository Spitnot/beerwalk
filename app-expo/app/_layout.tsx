import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { palette } from "@/theme";

export default function RootLayout() {
  return (
    <>
      <StatusBar style="dark" />
      <Stack
        screenOptions={{
          headerShadowVisible: false,
          headerStyle: { backgroundColor: palette.bg },
          headerTintColor: palette.ink,
          contentStyle: { backgroundColor: palette.bg },
        }}
      >
        <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
        <Stack.Screen name="onboarding" options={{ headerShown: false }} />
        {/* login/registro SIEMPRE como modal: el uso sin cuenta es primera clase */}
        <Stack.Screen name="auth" options={{ presentation: "modal", title: "Entrar" }} />
        <Stack.Screen name="scan-resultado" options={{ title: "Resultado del escaneo" }} />
        <Stack.Screen name="bar/[id]" options={{ title: "Bar" }} />
        <Stack.Screen name="cerveza/[id]" options={{ title: "Cerveza" }} />
        <Stack.Screen name="ajustes" options={{ title: "Ajustes" }} />
        <Stack.Screen name="panel/bar" options={{ title: "Panel de bar" }} />
        <Stack.Screen name="panel/cervecera" options={{ title: "Panel de cervecera" }} />
        <Stack.Screen name="panel/admin" options={{ title: "Moderación" }} />
      </Stack>
    </>
  );
}
