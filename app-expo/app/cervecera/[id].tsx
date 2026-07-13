import { useEffect, useState } from "react";
import { ActivityIndicator, Pressable, Text, View } from "react-native";
import { Link, useLocalSearchParams } from "expo-router";
import { Screen } from "@/components/Screen";
import { Section, PENDING } from "@/components/Section";
import { StyleBadge } from "@/components/StyleBadge";
import { EnrichmentPulse, FadeIn } from "@/components/EnrichmentPulse";
import { palette, radius, spacing, type } from "@/theme";
import { pb } from "@/lib/pocketbase";
import { useAnyPendingEnrichment } from "@/lib/useEnrichments";

interface BreweryRec {
  id: string;
  name: string;
  origin: string;
  description: string;
}

interface BeerRow {
  id: string;
  name: string;
  abv: number;
  expand?: { style?: { id: string; name: string; category: string } };
}

/**
 * Detalle de cervecera: ficha (descripción enriquecida o "buscando…") +
 * sus cervezas conocidas del catálogo `beers`, cada una enlazando a su ficha.
 * `verified` es un flag interno de revisión de admin y no se muestra.
 */
export default function CerveceraDetail() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const [brewery, setBrewery] = useState<BreweryRec | null>(null);
  const [beers, setBeers] = useState<BeerRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const anyPending = useAnyPendingEnrichment();

  useEffect(() => {
    if (!id) return;
    pb.collection("breweries")
      .getOne<BreweryRec>(id)
      .then(setBrewery)
      .catch(() => setError("No se pudo cargar esta cervecera. ¿Sigue existiendo?"));
    pb.collection("beers")
      .getFullList<BeerRow>({
        filter: `brewery = "${id}"`,
        expand: "style",
        sort: "name",
        requestKey: null,
      })
      .then(setBeers)
      .catch(() => setBeers([]));
  }, [id]);

  // Ficha VIVA (mismo patrón que cerveza/[id]): si el enriquecimiento en
  // background completa la descripción mientras se mira, aparece sola.
  useEffect(() => {
    if (!id) return;
    let alive = true;
    let unsubscribe: (() => void) | undefined;
    pb.collection("breweries")
      .subscribe(id, (e) => {
        if (alive && e.action === "update") setBrewery(e.record as unknown as BreweryRec);
      })
      .then((un) => {
        if (alive) unsubscribe = un;
        else void un();
      })
      .catch(() => {});
    return () => {
      alive = false;
      unsubscribe?.();
    };
  }, [id]);

  if (error) {
    return (
      <Screen title="Cervecera">
        <Text style={{ ...type.soft, color: palette.danger }}>{error}</Text>
      </Screen>
    );
  }
  if (!brewery) {
    return (
      <Screen title="Cervecera">
        <ActivityIndicator color={palette.brandDark} />
      </Screen>
    );
  }

  return (
    <Screen title={brewery.name}>
      {brewery.origin ? <Text style={type.soft}>{brewery.origin}</Text> : null}

      <Section title="Descripción">
        {brewery.description ? (
          <FadeIn key={brewery.description}>
            <Text style={type.body}>{brewery.description}</Text>
          </FadeIn>
        ) : anyPending ? (
          <EnrichmentPulse label="Buscando más info en la red" />
        ) : (
          <Text style={type.body}>{PENDING}</Text>
        )}
      </Section>

      <Section title={`Cervezas en el catálogo${beers?.length ? ` · ${beers.length}` : ""}`}>
        {beers === null ? (
          <ActivityIndicator color={palette.brandDark} />
        ) : beers.length === 0 ? (
          <Text style={type.body}>
            Todavía no conocemos cervezas suyas — escanea una pizarra que las tenga y
            aparecerán aquí.
          </Text>
        ) : (
          beers.map((b) => (
            <Link key={b.id} href={`/cerveza/${b.id}`} asChild>
              <Pressable
                style={{
                  flexDirection: "row",
                  alignItems: "center",
                  justifyContent: "space-between",
                  gap: 8,
                  paddingVertical: spacing(1),
                }}
              >
                <Text style={{ ...type.body, fontWeight: "800", flexShrink: 1 }} numberOfLines={1}>
                  {b.name}
                </Text>
                <View style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
                  {b.abv ? (
                    <View
                      style={{
                        backgroundColor: palette.brand,
                        borderRadius: radius.pill,
                        paddingHorizontal: spacing(2),
                        paddingVertical: 2,
                      }}
                    >
                      <Text style={{ fontSize: 11, fontWeight: "800", color: "#3D2A08" }}>
                        {b.abv}%
                      </Text>
                    </View>
                  ) : null}
                  {b.expand?.style ? (
                    <StyleBadge name={b.expand.style.name} category={b.expand.style.category} />
                  ) : null}
                </View>
              </Pressable>
            </Link>
          ))
        )}
      </Section>
    </Screen>
  );
}
