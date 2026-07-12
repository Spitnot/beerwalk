import { useEffect, useState } from "react";
import { ActivityIndicator, Text } from "react-native";
import { useLocalSearchParams } from "expo-router";
import { Screen } from "@/components/Screen";
import { StyleBadge } from "@/components/StyleBadge";
import { palette, spacing, type } from "@/theme";
import { pb } from "@/lib/pocketbase";

interface Style {
  id: string;
  name: string;
  category: string;
  description: string;
}

/** Detalle de estilo (colección `styles`; no existe colección de cervezas individuales) */
export default function CervezaDetail() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const [style, setStyle] = useState<Style | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    pb.collection("styles")
      .getOne<Style>(id)
      .then(setStyle)
      .catch(() => setError("No se pudo cargar este estilo."));
  }, [id]);

  if (error) {
    return (
      <Screen title="Estilo">
        <Text style={{ ...type.soft, color: palette.danger }}>{error}</Text>
      </Screen>
    );
  }
  if (!style) {
    return (
      <Screen title="Estilo">
        <ActivityIndicator color={palette.brandDark} />
      </Screen>
    );
  }

  return (
    <Screen title={style.name}>
      <StyleBadge name={style.name} category={style.category} />
      {style.category ? (
        <Text style={{ ...type.soft, marginTop: spacing(2) }}>Familia: {style.category}</Text>
      ) : null}
      <Text style={{ ...type.body, marginTop: spacing(3) }}>
        {style.description || "Sin descripción todavía."}
        {/* La descripción se traduce bajo demanda con translateCached() — post-MVP */}
      </Text>
    </Screen>
  );
}
