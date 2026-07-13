import { useEffect, useState } from "react";
import { Pressable, ScrollView, Text, View } from "react-native";
import { Link } from "expo-router";
import { Screen } from "@/components/Screen";
import { palette, radius, spacing, type } from "@/theme";
import { pb, isLoggedIn } from "@/lib/pocketbase";
import { getDeviceId } from "@/lib/device";
import { relativeEs } from "@/lib/time";

interface ScanRow {
  id: string;
  created: string;
  bar?: string;
  expand?: { bar?: { id: string; name: string } };
}

interface Stats {
  styles: number;
  breweries: number;
  bars: number;
}

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
  const [stats, setStats] = useState<Stats | null>(null);
  const [history, setHistory] = useState<ScanRow[] | null>(null);

  useEffect(() => {
    async function load() {
      const filter = logged
        ? `created_by = "${pb.authStore.record!.id}"`
        : `device_id = "${await getDeviceId()}" && created_by = ""`;

      const scans = await pb.collection("scans").getFullList<ScanRow>({
        filter, sort: "-created", expand: "bar", requestKey: null,
      });
      setHistory(scans);

      if (scans.length === 0) {
        setStats({ styles: 0, breweries: 0, bars: 0 });
        return;
      }
      // nº de estilos/cerveceras/bares DISTINTOS registrados por este
      // usuario (o invitado) — agregación real sobre scan_items propios,
      // no una cifra decorativa.
      const itemsFilter = scans.map((s) => `scan="${s.id}"`).join(" || ");
      const items = await pb.collection("scan_items").getFullList<{ brewery?: string; style?: string }>({
        filter: itemsFilter, fields: "brewery,style", requestKey: null,
      });
      const styles = new Set(items.map((i) => i.style).filter(Boolean));
      const breweries = new Set(items.map((i) => i.brewery).filter(Boolean));
      const bars = new Set(scans.map((s) => s.bar).filter(Boolean));
      setStats({ styles: styles.size, breweries: breweries.size, bars: bars.size });
    }
    load().catch(() => setStats({ styles: 0, breweries: 0, bars: 0 }));
  }, [logged]);

  return (
    <Screen title="Perfil">
      <ScrollView contentContainerStyle={{ gap: spacing(4) }}>
        <View style={{ flexDirection: "row", gap: spacing(2) }}>
          <Stat n={stats?.styles ?? 0} label="estilos" />
          <Stat n={stats?.breweries ?? 0} label="cerveceras" />
          <Stat n={stats?.bars ?? 0} label="bares" />
        </View>

        {!logged && (
          <Link href="/auth" asChild>
            <Pressable style={{ backgroundColor: palette.brand, borderRadius: radius.lg, padding: spacing(4), alignItems: "center" }}>
              <Text style={{ fontWeight: "800", color: palette.onBrand }}>Crear cuenta / entrar</Text>
            </Pressable>
          </Link>
        )}

        <View style={{ gap: spacing(2) }}>
          <Link href="/ajustes" style={type.body}>⚙️ Ajustes</Link>
          <Link href="/panel/bar" style={type.body}>🏪 Soy un bar</Link>
          <Link href="/panel/cervecera" style={type.body}>🏭 Soy una cervecera</Link>
          <Link href="/panel/admin" style={type.body}>🛡️ Moderación (admin)</Link>
        </View>

        {/* Historial propio: es TU registro — hay que poder repasarlo
            entero para auditar qué has escaneado, nunca ocultar un ítem
            por diseño. Lista vertical, no carrusel. */}
        <View style={{ gap: spacing(2) }}>
          <Text style={type.h2}>Tus escaneos</Text>
          {history === null ? (
            <Text style={type.soft}>Cargando…</Text>
          ) : history.length === 0 ? (
            <Text style={type.soft}>
              {logged ? "Todavía no has guardado ningún escaneo." : "Escanea una pizarra para empezar tu camino cervecero."}
            </Text>
          ) : (
            history.map((s) => (
              <Link key={s.id} href={s.expand?.bar ? `/bar/${s.expand.bar.id}` : "/(tabs)/home"} asChild>
                <Pressable
                  style={{
                    flexDirection: "row", justifyContent: "space-between", alignItems: "center",
                    borderBottomWidth: 1, borderBottomColor: palette.line, paddingVertical: spacing(2),
                  }}
                >
                  <Text style={type.body} numberOfLines={1}>{s.expand?.bar?.name ?? "Sin bar asignado"}</Text>
                  <Text style={type.soft}>{relativeEs(s.created)}</Text>
                </Pressable>
              </Link>
            ))
          )}
        </View>
      </ScrollView>
    </Screen>
  );
}
