import { Pressable, Text, View } from "react-native";
import { Link } from "expo-router";
import { Screen } from "@/components/Screen";
import { palette, radius, spacing, type } from "@/theme";
import { mockStats } from "@/mocks";
import { isLoggedIn } from "@/lib/pocketbase";

function Stat({ n, label }: { n: number; label: string }) {
  return (
    <View style={{ flex: 1, backgroundColor: palette.surface, borderRadius: radius.md, borderWidth: 1, borderColor: palette.line, padding: spacing(3), alignItems: "center" }}>
      <Text style={{ fontSize: 26, fontWeight: "800", color: palette.brandDark }}>{n}</Text>
      <Text style={type.soft}>{label}</Text>
    </View>
  );
}

export default function Perfil() {
  const logged = isLoggedIn();
  return (
    <Screen title="Perfil">
      {/* Estadísticas: en real, agregación sobre scans/scan_items del usuario */}
      <View style={{ flexDirection: "row", gap: spacing(2), marginBottom: spacing(4) }}>
        <Stat n={mockStats.styles} label="estilos" />
        <Stat n={mockStats.breweries} label="cerveceras" />
        <Stat n={mockStats.bars} label="bares" />
      </View>

      {!logged && (
        <Link href="/auth" asChild>
          <Pressable style={{ backgroundColor: palette.brand, borderRadius: radius.lg, padding: spacing(4), alignItems: "center", marginBottom: spacing(3) }}>
            <Text style={{ fontWeight: "800", color: "#3D2A08" }}>Crear cuenta / entrar</Text>
          </Pressable>
        </Link>
      )}

      <View style={{ gap: spacing(2) }}>
        <Link href="/ajustes" style={type.body}>⚙️ Ajustes</Link>
        <Link href="/panel/bar" style={type.body}>🏪 Soy un bar</Link>
        <Link href="/panel/cervecera" style={type.body}>🏭 Soy una cervecera</Link>
        <Link href="/panel/admin" style={type.body}>🛡️ Moderación (admin)</Link>
      </View>
    </Screen>
  );
}
