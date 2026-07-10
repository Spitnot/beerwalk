import { useState } from "react";
import { Pressable, Text, TextInput, View } from "react-native";
import { useRouter } from "expo-router";
import { palette, radius, spacing, type } from "@/theme";
import { pb, claimGuestScans } from "@/lib/pocketbase";
import { getDeviceId } from "@/lib/device";

/**
 * Modal de login/registro. Solo aparece cuando el usuario quiere PERSISTIR
 * algo (valorar, seguir, corregir OCR con cuenta). El resto de la app es libre.
 * OAuth Google/Apple: pb.collection("users").authWithOAuth2({ provider: "google" })
 * (requiere configurar los providers en el Admin UI de PocketBase).
 */
export default function Auth() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function login(register: boolean) {
    setError(null);
    try {
      if (register) {
        await pb.collection("users").create({ email, password, passwordConfirm: password, role: "aficionado" });
      }
      await pb.collection("users").authWithPassword(email, password);
      // vincular escaneos hechos como invitado
      await claimGuestScans(await getDeviceId());
      router.back();
    } catch (e: any) {
      setError(e?.message ?? "Error de autenticación");
    }
  }

  const input = {
    backgroundColor: palette.surface,
    borderWidth: 1,
    borderColor: palette.line,
    borderRadius: radius.md,
    padding: spacing(3),
    marginBottom: spacing(3),
  } as const;

  return (
    <View style={{ flex: 1, backgroundColor: palette.bg, padding: spacing(5) }}>
      <Text style={{ ...type.h2, marginBottom: spacing(4) }}>Guarda tu camino cervecero</Text>
      <TextInput style={input} placeholder="Email" autoCapitalize="none" value={email} onChangeText={setEmail} />
      <TextInput style={input} placeholder="Contraseña" secureTextEntry value={password} onChangeText={setPassword} />
      {error && <Text style={{ color: palette.danger, marginBottom: spacing(3) }}>{error}</Text>}
      <Pressable onPress={() => login(false)} style={{ backgroundColor: palette.brand, borderRadius: radius.lg, padding: spacing(4), alignItems: "center", marginBottom: spacing(2) }}>
        <Text style={{ fontWeight: "800", color: "#3D2A08" }}>Entrar</Text>
      </Pressable>
      <Pressable onPress={() => login(true)} style={{ borderWidth: 1, borderColor: palette.line, borderRadius: radius.lg, padding: spacing(4), alignItems: "center" }}>
        <Text style={{ fontWeight: "800", color: palette.ink }}>Crear cuenta</Text>
      </Pressable>
      <Text style={{ ...type.soft, marginTop: spacing(4) }}>Próximamente: Google y Apple vía OAuth2 de PocketBase.</Text>
    </View>
  );
}
