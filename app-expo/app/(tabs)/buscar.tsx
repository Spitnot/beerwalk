import { useState } from "react";
import { TextInput } from "react-native";
import { Screen } from "@/components/Screen";
import { BarCard } from "@/components/BarCard";
import { palette, radius, spacing } from "@/theme";
import { mockBars } from "@/mocks";

export default function Buscar() {
  const [q, setQ] = useState("");
  const results = mockBars.filter((b) => b.name.toLowerCase().includes(q.toLowerCase()));
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
      {results.map((bar) => (
        <BarCard key={bar.id} bar={bar} />
      ))}
    </Screen>
  );
}
