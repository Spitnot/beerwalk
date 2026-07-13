import { useEffect, useState } from "react";
import { ActivityIndicator, Text, View } from "react-native";
import { Link, useLocalSearchParams } from "expo-router";
import { Screen } from "@/components/Screen";
import { Section, PENDING } from "@/components/Section";
import { StyleBadge } from "@/components/StyleBadge";
import { StyleStats } from "@/components/StyleStats";
import { EnrichmentPulse, FadeIn } from "@/components/EnrichmentPulse";
import { palette, radius, spacing, type } from "@/theme";
import { pb } from "@/lib/pocketbase";
import { useAnyPendingEnrichment } from "@/lib/useEnrichments";
import { BJCP_DISCLAIMER, type StyleBjcp } from "@/lib/bjcp";

interface StyleRec extends StyleBjcp {
  id: string;
  name: string;
  category: string;
  description: string;
}

const PROFILE_LABELS: [keyof StyleBjcp, string][] = [
  ["aroma_profile", "Aroma"],
  ["appearance_profile", "Aspecto"],
  ["flavor_profile", "Sabor"],
  ["mouthfeel_profile", "En boca"],
];

/** Nota discreta de atribución de la guía BJCP (al pie del detalle de estilo) */
function BjcpNote() {
  return (
    <Text style={{ ...type.soft, fontSize: 11, marginTop: spacing(4), lineHeight: 15 }}>
      {BJCP_DISCLAIMER}
    </Text>
  );
}

function StyleProfiles({ style }: { style: StyleBjcp }) {
  const rows = PROFILE_LABELS.filter(([key]) => style[key]);
  if (rows.length === 0) return null;
  return (
    <View style={{ gap: spacing(1), marginTop: spacing(2) }}>
      {rows.map(([key, label]) => (
        <Text key={key} style={type.body}>
          <Text style={{ fontWeight: "800" }}>{label}: </Text>
          {String(style[key])}
        </Text>
      ))}
    </View>
  );
}

interface BreweryRec {
  id: string;
  name: string;
  origin: string;
  description: string;
}

interface BeerRec {
  id: string;
  name: string;
  abv: number;
  description: string;
  tasting_notes: string;
  expand?: { brewery?: BreweryRec; style?: StyleRec };
}

/**
 * Detalle de cerveza (collection `beers`, con cervecera y estilo expandidos).
 * Fallback: los enlaces antiguos pasaban ids de `styles` por esta misma ruta;
 * si el id no es una beer, se muestra el detalle de estilo como antes.
 */
export default function CervezaDetail() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const [beer, setBeer] = useState<BeerRec | null>(null);
  const [styleOnly, setStyleOnly] = useState<StyleRec | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    pb.collection("beers")
      .getOne<BeerRec>(id, { expand: "brewery,style" })
      .then(setBeer)
      .catch(() =>
        pb.collection("styles")
          .getOne<StyleRec>(id)
          .then(setStyleOnly)
          .catch(() => setError("No se pudo cargar esta ficha."))
      );
  }, [id]);

  // Ficha VIVA: el enriquecimiento en background completa description/
  // tasting_notes/cervecera con el tiempo — si pasa mientras se mira la
  // ficha, el realtime la refresca solo (sin volver a entrar).
  const breweryId = beer?.expand?.brewery?.id;
  useEffect(() => {
    if (!beer?.id) return;
    let alive = true;
    const refresh = () =>
      pb.collection("beers")
        .getOne<BeerRec>(beer.id, { expand: "brewery,style", requestKey: null })
        .then((b) => alive && setBeer(b))
        .catch(() => {});
    const unsubs: (() => void)[] = [];
    pb.collection("beers").subscribe(beer.id, refresh)
      .then((un) => {
        if (alive) unsubs.push(un);
        else void un();
      })
      .catch(() => {});
    if (breweryId) {
      pb.collection("breweries").subscribe(breweryId, refresh)
        .then((un) => {
          if (alive) unsubs.push(un);
          else void un();
        })
        .catch(() => {});
    }
    return () => {
      alive = false;
      unsubs.forEach((un) => un());
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [beer?.id, breweryId]);

  // ¿Hay una búsqueda web en curso que podría rellenar los huecos de ESTA
  // ficha? Mientras la haya, los campos vacíos "buscan" en vez de decir
  // "no disponible" a secas.
  const anyPending = useAnyPendingEnrichment();

  if (error) {
    return (
      <Screen title="Cerveza">
        <Text style={{ ...type.soft, color: palette.danger }}>{error}</Text>
      </Screen>
    );
  }

  // ── Fallback: detalle de estilo (enlaces antiguos) ─────────────────────
  if (styleOnly) {
    return (
      <Screen title={styleOnly.name}>
        <View style={{ flexDirection: "row", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          <StyleBadge name={styleOnly.name} category={styleOnly.category} />
          {styleOnly.bjcp_category ? (
            <Text style={type.soft}>BJCP {styleOnly.bjcp_category}</Text>
          ) : null}
        </View>
        {styleOnly.family ? (
          <Text style={{ ...type.soft, marginTop: spacing(2) }}>Familia: {styleOnly.family}</Text>
        ) : null}
        <View style={{ marginTop: spacing(3) }}>
          <StyleStats style={styleOnly} />
        </View>
        <Text style={{ ...type.body, marginTop: spacing(3) }}>
          {styleOnly.overall_impression || styleOnly.description || PENDING}
        </Text>
        <StyleProfiles style={styleOnly} />
        {styleOnly.commercial_examples ? (
          <Text style={{ ...type.soft, marginTop: spacing(3) }}>
            Referencias del estilo: {styleOnly.commercial_examples}
          </Text>
        ) : null}
        <BjcpNote />
      </Screen>
    );
  }

  if (!beer) {
    return (
      <Screen title="Cerveza">
        <ActivityIndicator color={palette.brandDark} />
      </Screen>
    );
  }

  const brewery = beer.expand?.brewery;
  const style = beer.expand?.style;

  return (
    <Screen title={beer.name}>
      <View style={{ flexDirection: "row", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
        {style ? <StyleBadge name={style.name} category={style.category} /> : null}
        {beer.abv ? (
          <View
            style={{
              backgroundColor: palette.brand,
              borderRadius: radius.pill,
              paddingHorizontal: spacing(2),
              paddingVertical: 3,
            }}
          >
            <Text style={{ fontSize: 12, fontWeight: "800", color: "#3D2A08" }}>{beer.abv}% vol.</Text>
          </View>
        ) : null}
      </View>

      <Section title="Descripción">
        {beer.description ? (
          <FadeIn key={beer.description}><Text style={type.body}>{beer.description}</Text></FadeIn>
        ) : anyPending ? (
          <EnrichmentPulse label="Buscando más info en la red" />
        ) : (
          <Text style={type.body}>{PENDING}</Text>
        )}
      </Section>

      <Section title="Notas de cata">
        {beer.tasting_notes ? (
          <FadeIn key={beer.tasting_notes}><Text style={type.body}>{beer.tasting_notes}</Text></FadeIn>
        ) : anyPending ? (
          <EnrichmentPulse label="Buscando más info en la red" />
        ) : (
          <Text style={type.body}>{PENDING}</Text>
        )}
      </Section>

      <Section title={brewery ? `Cervecera · ${brewery.name}` : "Cervecera"}>
        {brewery ? (
          <>
            {brewery.origin ? <Text style={type.soft}>{brewery.origin}</Text> : null}
            <Link href={`/cervecera/${brewery.id}`}>
              <Text style={{ ...type.soft, fontWeight: "800", color: palette.brandDark }}>
                Ver ficha y todas sus cervezas →
              </Text>
            </Link>
            {brewery.description ? (
              <FadeIn key={brewery.description}><Text style={type.body}>{brewery.description}</Text></FadeIn>
            ) : anyPending ? (
              <EnrichmentPulse label="Buscando más info en la red" />
            ) : (
              <Text style={type.body}>{PENDING}</Text>
            )}
          </>
        ) : (
          <Text style={type.body}>{PENDING}</Text>
        )}
      </Section>

      {style ? (
        <Section title={`Estilo · ${style.name}${style.bjcp_category ? ` (BJCP ${style.bjcp_category})` : ""}`}>
          <StyleStats style={style} />
          <Text style={type.body}>{style.overall_impression || style.description || PENDING}</Text>
          <StyleProfiles style={style} />
        </Section>
      ) : null}
      {style ? <BjcpNote /> : null}
    </Screen>
  );
}
