import { useEffect, useState } from "react";
import { ActivityIndicator, Text, View } from "react-native";
import { Link, useLocalSearchParams } from "expo-router";
import { Screen } from "@/components/Screen";
import { StyleBadge } from "@/components/StyleBadge";
import { palette, radius, spacing, type } from "@/theme";
import { pb } from "@/lib/pocketbase";

interface Bar {
  id: string;
  name: string;
  address: string;
}

interface ScanItemRecord {
  id: string;
  beer_name: string;
  scan: string;
  expand?: {
    scan?: { id: string; created: string };
    style?: { id: string; name: string; category: string };
  };
}

interface Board {
  scanId: string;
  created: string;
  items: ScanItemRecord[];
}

/** Detalle de bar: pizarra actual + timeline de pizarras anteriores, todo de PocketBase */
export default function BarDetail() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const [bar, setBar] = useState<Bar | null>(null);
  const [boards, setBoards] = useState<Board[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    pb.collection("bars")
      .getOne<Bar>(id, { fields: "id,name,address" })
      .then(setBar)
      .catch(() => setError("No se pudo cargar el bar. ¿Sigue existiendo?"));
    pb.collection("scan_items")
      .getFullList<ScanItemRecord>({
        filter: `scan.bar = "${id}"`,
        expand: "scan,style",
        sort: "-created",
      })
      .then((items) => {
        const byScan = new Map<string, Board>();
        for (const it of items) {
          const scanId = it.scan;
          const created = it.expand?.scan?.created ?? "";
          const board = byScan.get(scanId) ?? { scanId, created, items: [] };
          board.items.push(it);
          byScan.set(scanId, board);
        }
        setBoards([...byScan.values()].sort((a, b) => b.created.localeCompare(a.created)));
      })
      .catch(() => setError("No se pudieron cargar las pizarras de este bar."));
  }, [id]);

  if (error) {
    return (
      <Screen title="Bar">
        <Text style={{ ...type.soft, color: palette.danger }}>{error}</Text>
      </Screen>
    );
  }
  if (!bar || boards === null) {
    return (
      <Screen title="Bar">
        <ActivityIndicator color={palette.brandDark} />
      </Screen>
    );
  }

  const [current, ...previous] = boards;
  const fmt = (iso: string) =>
    iso ? new Date(iso).toLocaleDateString("es-ES", { day: "numeric", month: "short" }) : "fecha desconocida";

  return (
    <Screen title={bar.name}>
      <Text style={{ ...type.soft, marginBottom: spacing(3) }}>{bar.address}</Text>
      <Text style={{ ...type.h2, marginBottom: spacing(2) }}>Pizarra actual</Text>
      {current ? (
        <View style={{ gap: spacing(2), marginBottom: spacing(4) }}>
          <Text style={type.soft}>Escaneada el {fmt(current.created)}</Text>
          {current.items.map((it) => (
            <View key={it.id} style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
              <Text style={{ ...type.body, flexShrink: 1 }} numberOfLines={1}>{it.beer_name || "—"}</Text>
              {it.expand?.style ? (
                <Link href={`/cerveza/${it.expand.style.id}`}>
                  <StyleBadge name={it.expand.style.name} category={it.expand.style.category} />
                </Link>
              ) : null}
            </View>
          ))}
        </View>
      ) : (
        <Text style={{ ...type.soft, marginBottom: spacing(4) }}>
          Nadie ha escaneado la pizarra de este bar todavía. ¡Sé el primero!
        </Text>
      )}
      <Text style={{ ...type.h2, marginBottom: spacing(2) }}>Pizarras anteriores</Text>
      {previous.length === 0 && <Text style={type.soft}>Sin escaneos anteriores.</Text>}
      {previous.map((b) => (
        <View key={b.scanId} style={{ backgroundColor: palette.surface, borderWidth: 1, borderColor: palette.line, borderRadius: radius.md, padding: spacing(3), marginBottom: spacing(2) }}>
          <Text style={type.body}>{fmt(b.created)} — {b.items.length} cervezas detectadas</Text>
        </View>
      ))}
    </Screen>
  );
}
