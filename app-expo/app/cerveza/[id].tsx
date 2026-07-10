import { Text } from "react-native";
import { useLocalSearchParams } from "expo-router";
import { Screen } from "@/components/Screen";
import { StyleBadge } from "@/components/StyleBadge";
import { spacing, type } from "@/theme";

export default function CervezaDetail() {
  const { id } = useLocalSearchParams<{ id: string }>();
  return (
    <Screen title="Soup">
      <Text style={{ ...type.soft, marginBottom: spacing(2) }}>Garage Beer Co · id {id}</Text>
      <StyleBadge name="Hazy IPA" />
      <Text style={{ ...type.body, marginTop: spacing(3) }}>
        Turbia, jugosa, aromas tropicales, amargor bajo.
        {/* La descripción se traduce bajo demanda con translateCached() */}
      </Text>
    </Screen>
  );
}
