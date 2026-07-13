import { useEffect, useState } from "react";
import { Link } from "expo-router";
import { Pressable, ScrollView, Text, View } from "react-native";
import { Screen } from "@/components/Screen";
import { AbvPill } from "@/components/AbvPill";
import { StyleBadge } from "@/components/StyleBadge";
import { palette, radius, spacing, type } from "@/theme";
import { pb } from "@/lib/pocketbase";
import { relativeEs } from "@/lib/time";
import { t } from "@/i18n";

interface BeerRow {
  id: string;
  name: string;
  abv?: number;
  expand?: { brewery?: { id: string; name: string }; style?: { id: string; name: string; category?: string } };
}

interface ScanRow {
  id: string;
  created: string;
  expand?: { bar?: { id: string; name: string; address: string } };
}

/**
 * Carrusel horizontal — SIEMPRE de descubrimiento: sin jerarquía entre
 * items, no pasa nada si el usuario no ve alguno (puede deslizar cuando
 * quiera). Ancho de card menor que la pantalla para que la siguiente
 * asome cortada en el borde (única pista de que hay más, sin sombras).
 */
function Carousel({ children }: { children: React.ReactNode }) {
  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: spacing(3), paddingRight: spacing(6) }}>
      {children}
    </ScrollView>
  );
}

export default function Home() {
  const [beers, setBeers] = useState<BeerRow[] | null>(null);
  const [scans, setScans] = useState<ScanRow[] | null>(null);
  const [itemCounts, setItemCounts] = useState<Record<string, number>>({});

  useEffect(() => {
    // "Últimas descubiertas": las beers más recientes del catálogo (manuales
    // o creadas por el enriquecimiento). Descubrimiento puro — orden por
    // fecha, sin jerarquía entre ellas.
    pb.collection("beers")
      .getList<BeerRow>(1, 10, { sort: "-created", expand: "brewery,style", requestKey: null })
      .then((r) => setBeers(r.items))
      .catch(() => setBeers([]));

    // "Actividad cerca": los escaneos más recientes de cualquier bar.
    // (Sin geolocalización todavía conectada aquí: "cerca" hoy es "reciente
    // en el tiempo"; el filtro geográfico real vive en la detección de
    // proximidad del propio escaneo, no en este feed.)
    pb.collection("scans")
      .getList<ScanRow>(1, 10, { sort: "-created", expand: "bar", requestKey: null })
      .then(async (r) => {
        setScans(r.items);
        if (r.items.length === 0) return;
        // Conteo de items por scan: una sola lectura agregada en cliente,
        // mismo patrón que el contador de cervezas por cervecera en Buscar.
        const filter = r.items.map((s) => `scan="${s.id}"`).join(" || ");
        const rows = await pb.collection("scan_items").getFullList<{ scan: string }>({
          filter, fields: "scan", requestKey: null,
        });
        const counts: Record<string, number> = {};
        for (const row of rows) counts[row.scan] = (counts[row.scan] ?? 0) + 1;
        setItemCounts(counts);
      })
      .catch(() => setScans([]));
  }, []);

  return (
    <Screen title="BeerWalk">
      <ScrollView contentContainerStyle={{ gap: spacing(5) }}>
        <Link href="/explorar" asChild>
          <Pressable
            style={{
              height: 140,
              borderRadius: radius.lg,
              backgroundColor: palette.mapPreviewBg,
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Text style={{ ...type.body, fontWeight: "800" }}>🗺️ {t("nearby_bars")} — toca para explorar</Text>
          </Pressable>
        </Link>

        <View style={{ gap: spacing(3) }}>
          <Text style={type.h2}>Últimas descubiertas</Text>
          {beers === null ? (
            <Text style={type.soft}>Cargando…</Text>
          ) : beers.length === 0 ? (
            <Text style={type.soft}>Todavía no hay cervezas en el catálogo — escanea una pizarra para empezar.</Text>
          ) : (
            <Carousel>
              {beers.map((b) => (
                <Link key={b.id} href={`/cerveza/${b.id}`} asChild>
                  <Pressable
                    style={{
                      width: 168,
                      borderWidth: 1,
                      borderColor: palette.line,
                      borderRadius: radius.md,
                      padding: spacing(3),
                      gap: 6,
                      backgroundColor: palette.surface,
                    }}
                  >
                    {b.expand?.style ? <StyleBadge name={b.expand.style.name} category={b.expand.style.category} /> : null}
                    <Text style={{ ...type.body, fontWeight: "800" }} numberOfLines={2}>{b.name}</Text>
                    {b.expand?.brewery ? <Text style={type.soft} numberOfLines={1}>{b.expand.brewery.name}</Text> : null}
                    {b.abv ? <AbvPill abv={b.abv} small /> : null}
                  </Pressable>
                </Link>
              ))}
            </Carousel>
          )}
        </View>

        <View style={{ gap: spacing(3) }}>
          <Text style={type.h2}>Actividad cerca</Text>
          {scans === null ? (
            <Text style={type.soft}>Cargando…</Text>
          ) : scans.length === 0 ? (
            <Text style={type.soft}>Nadie ha escaneado una pizarra todavía. ¡Sé el primero!</Text>
          ) : (
            <Carousel>
              {scans.map((s) => (
                <Link key={s.id} href={s.expand?.bar ? `/bar/${s.expand.bar.id}` : "/(tabs)/home"} asChild>
                  <Pressable
                    style={{
                      width: 200,
                      borderWidth: 1,
                      borderColor: palette.line,
                      borderRadius: radius.md,
                      padding: spacing(3),
                      gap: 4,
                      backgroundColor: palette.surface,
                    }}
                  >
                    <Text style={{ ...type.body, fontWeight: "800" }} numberOfLines={1}>
                      {s.expand?.bar?.name ?? "Bar sin identificar"}
                    </Text>
                    <Text style={type.soft} numberOfLines={1}>{s.expand?.bar?.address}</Text>
                    <Text style={type.soft}>
                      {relativeEs(s.created)} · {itemCounts[s.id] ?? 0} {itemCounts[s.id] === 1 ? "cerveza" : "cervezas"}
                    </Text>
                  </Pressable>
                </Link>
              ))}
            </Carousel>
          )}
        </View>
      </ScrollView>
    </Screen>
  );
}
