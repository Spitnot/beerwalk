import { useEffect, useMemo, useState } from "react";
import { Pressable, Text, TextInput, View } from "react-native";
import { Link } from "expo-router";
import { Screen } from "@/components/Screen";
import { StyleBadge } from "@/components/StyleBadge";
import { palette, radius, spacing, type } from "@/theme";
import { pb } from "@/lib/pocketbase";
import type { StyleBjcp } from "@/lib/bjcp";

interface StyleRow extends StyleBjcp {
  id: string;
  name: string;
  category: string;
}

interface BreweryRow {
  id: string;
  name: string;
  origin: string;
}

interface BarRow {
  id: string;
  name: string;
  address: string;
}

export default function Buscar() {
  const [q, setQ] = useState("");
  const [styles, setStyles] = useState<StyleRow[]>([]);
  const [breweries, setBreweries] = useState<BreweryRow[]>([]);
  const [beerCounts, setBeerCounts] = useState<Record<string, number>>({});
  const [bars, setBars] = useState<BarRow[]>([]);

  useEffect(() => {
    // Orden editorial del catálogo BJCP: familias entre sí y estilos dentro
    // de cada familia — nunca alfabético
    pb.collection("styles")
      .getFullList<StyleRow>({
        sort: "family_order,style_order,name",
        fields: "id,name,category,family,family_order,style_order,bjcp_category",
        requestKey: null,
      })
      .then(setStyles)
      .catch(() => setStyles([]));
    // Catálogo real de cerveceras (Bloque 3). `verified` es un flag interno
    // de revisión de admin: aquí no se filtra ni se muestra.
    pb.collection("breweries")
      .getFullList<BreweryRow>({ sort: "name", fields: "id,name,origin", requestKey: null })
      .then(setBreweries)
      .catch(() => setBreweries([]));
    // Bares reales (los demo + los creados desde la app)
    pb.collection("bars")
      .getFullList<BarRow>({ sort: "name", fields: "id,name,address", requestKey: null })
      .then(setBars)
      .catch(() => setBars([]));
    // Conteo de cervezas por cervecera: una sola lectura del catálogo `beers`
    // (pequeño y solo campo brewery), agregada en cliente — sin N+1
    pb.collection("beers")
      .getFullList<{ brewery: string }>({ fields: "brewery", requestKey: null })
      .then((rows) => {
        const counts: Record<string, number> = {};
        for (const r of rows) if (r.brewery) counts[r.brewery] = (counts[r.brewery] ?? 0) + 1;
        setBeerCounts(counts);
      })
      .catch(() => {});
  }, []);

  const styleResults = useMemo(() => {
    const needle = q.trim().toLowerCase();
    const filtered = needle
      ? styles.filter(
          (s) =>
            s.name.toLowerCase().includes(needle) ||
            (s.family ?? "").toLowerCase().includes(needle)
        )
      : styles;
    // Agrupar por familia conservando el orden editorial ya aplicado
    const families: { family: string; items: StyleRow[] }[] = [];
    for (const s of filtered) {
      const family = s.family || s.category || "Otros";
      const last = families[families.length - 1];
      if (last && last.family === family) last.items.push(s);
      else families.push({ family, items: [s] });
    }
    return families;
  }, [q, styles]);

  // Texto libre sobre nombre u origen, mismo criterio que estilos
  const breweryResults = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return needle
      ? breweries.filter(
          (b) =>
            b.name.toLowerCase().includes(needle) ||
            (b.origin ?? "").toLowerCase().includes(needle)
        )
      : breweries;
  }, [q, breweries]);

  // Texto libre sobre nombre o dirección, mismo criterio que cerveceras
  const barResults = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return needle
      ? bars.filter(
          (b) =>
            b.name.toLowerCase().includes(needle) ||
            (b.address ?? "").toLowerCase().includes(needle)
        )
      : bars;
  }, [q, bars]);

  return (
    <Screen title="Buscar">
      <TextInput
        value={q}
        onChangeText={setQ}
        placeholder="Bares, cerveceras, estilos…"
        placeholderTextColor={palette.inkSoft}
        style={{
          backgroundColor: palette.surface,
          borderWidth: 1,
          borderColor: palette.line,
          borderRadius: radius.pill,
          paddingHorizontal: spacing(4),
          paddingVertical: spacing(3),
          marginBottom: spacing(4),
          fontSize: 15,
        }}
      />

      {styleResults.length > 0 && (
        <View style={{ marginBottom: spacing(4) }}>
          <Text style={{ ...type.soft, fontWeight: "800", marginBottom: spacing(2) }}>ESTILOS</Text>
          {styleResults.map(({ family, items }) => (
            <View key={family} style={{ marginBottom: spacing(3) }}>
              <Text style={{ ...type.soft, marginBottom: spacing(1) }}>{family}</Text>
              <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 6 }}>
                {items.map((s) => (
                  <Link key={s.id} href={`/cerveza/${s.id}`} asChild>
                    <Pressable>
                      <StyleBadge name={s.name} />
                    </Pressable>
                  </Link>
                ))}
              </View>
            </View>
          ))}
        </View>
      )}

      {breweryResults.length > 0 && (
        <View style={{ marginBottom: spacing(4) }}>
          <Text style={{ ...type.soft, fontWeight: "800", marginBottom: spacing(2) }}>CERVECERAS</Text>
          {breweryResults.map((b) => (
            <Link key={b.id} href={`/cervecera/${b.id}`} asChild>
              <Pressable
                style={{
                  backgroundColor: palette.surface,
                  borderWidth: 1,
                  borderColor: palette.line,
                  borderRadius: radius.md,
                  padding: spacing(3),
                  marginBottom: spacing(2),
                  flexDirection: "row",
                  alignItems: "center",
                  justifyContent: "space-between",
                  gap: 8,
                }}
              >
                <View style={{ flexShrink: 1 }}>
                  <Text style={{ ...type.body, fontWeight: "800" }} numberOfLines={1}>{b.name}</Text>
                  {b.origin ? <Text style={type.soft} numberOfLines={1}>{b.origin}</Text> : null}
                </View>
                {beerCounts[b.id] ? (
                  <View
                    style={{
                      backgroundColor: palette.brand,
                      borderRadius: radius.pill,
                      paddingHorizontal: spacing(2),
                      paddingVertical: 3,
                    }}
                  >
                    <Text style={{ fontSize: 12, fontWeight: "800", color: "#3D2A08" }}>
                      {beerCounts[b.id]} 🍺
                    </Text>
                  </View>
                ) : null}
              </Pressable>
            </Link>
          ))}
        </View>
      )}

      {barResults.length > 0 && (
        <Text style={{ ...type.soft, fontWeight: "800", marginBottom: spacing(2) }}>BARES</Text>
      )}
      {barResults.map((b) => (
        <Link key={b.id} href={`/bar/${b.id}`} asChild>
          <Pressable
            style={{
              backgroundColor: palette.surface,
              borderWidth: 1,
              borderColor: palette.line,
              borderRadius: radius.md,
              padding: spacing(3),
              marginBottom: spacing(2),
            }}
          >
            <Text style={{ ...type.body, fontWeight: "800" }} numberOfLines={1}>{b.name}</Text>
            {b.address ? <Text style={type.soft} numberOfLines={1}>{b.address}</Text> : null}
          </Pressable>
        </Link>
      ))}
    </Screen>
  );
}
