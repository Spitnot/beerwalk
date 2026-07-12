import { useEffect, useState } from "react";
import { ActivityIndicator, Text, View } from "react-native";
import { useLocalSearchParams } from "expo-router";
import { Screen } from "@/components/Screen";
import { StyleBadge } from "@/components/StyleBadge";
import { palette, radius, spacing, type } from "@/theme";
import { pb } from "@/lib/pocketbase";

interface StyleRec {
  id: string;
  name: string;
  category: string;
  description: string;
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

/** Campo aún sin enriquecer: placeholder explícito, nunca hueco en blanco */
const PENDING = "Información no disponible todavía";

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <View
      style={{
        backgroundColor: palette.surface,
        borderRadius: radius.md,
        borderWidth: 1,
        borderColor: palette.line,
        padding: spacing(3),
        marginTop: spacing(3),
        gap: 6,
      }}
    >
      <Text style={{ ...type.soft, fontWeight: "800" }}>{title}</Text>
      {children}
    </View>
  );
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
        <StyleBadge name={styleOnly.name} category={styleOnly.category} />
        {styleOnly.category ? (
          <Text style={{ ...type.soft, marginTop: spacing(2) }}>Familia: {styleOnly.category}</Text>
        ) : null}
        <Text style={{ ...type.body, marginTop: spacing(3) }}>
          {styleOnly.description || PENDING}
        </Text>
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
        <Text style={type.body}>{beer.description || PENDING}</Text>
      </Section>

      <Section title="Notas de cata">
        <Text style={type.body}>{beer.tasting_notes || PENDING}</Text>
      </Section>

      <Section title={brewery ? `Cervecera · ${brewery.name}` : "Cervecera"}>
        {brewery ? (
          <>
            {brewery.origin ? <Text style={type.soft}>{brewery.origin}</Text> : null}
            <Text style={type.body}>{brewery.description || PENDING}</Text>
          </>
        ) : (
          <Text style={type.body}>{PENDING}</Text>
        )}
      </Section>

      {style ? (
        <Section title={`Estilo · ${style.name}`}>
          <Text style={type.body}>{style.description || PENDING}</Text>
        </Section>
      ) : null}
    </Screen>
  );
}
