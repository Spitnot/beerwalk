import { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, Text, View } from "react-native";
import { Link, useLocalSearchParams } from "expo-router";
import { Screen } from "@/components/Screen";
import { StyleBadge } from "@/components/StyleBadge";
import { EnrichmentPulse, FadeIn } from "@/components/EnrichmentPulse";
import { palette, radius, spacing, type } from "@/theme";
import { pb } from "@/lib/pocketbase";
import { useEnrichments } from "@/lib/useEnrichments";

interface Bar {
  id: string;
  name: string;
  address: string;
}

interface ScanItemRecord {
  id: string;
  beer_name: string;
  scan: string;
  style?: string;
  enrichment_id?: string;
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

  const loadBoards = useCallback(() => {
    if (!id) return;
    pb.collection("scan_items")
      .getFullList<ScanItemRecord>({
        filter: `scan.bar = "${id}"`,
        expand: "scan,style",
        sort: "-created",
        requestKey: null,
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

  useEffect(() => {
    if (!id) return;
    pb.collection("bars")
      .getOne<Bar>(id, { fields: "id,name,address" })
      .then(setBar)
      .catch(() => setError("No se pudo cargar el bar. ¿Sigue existiendo?"));
    loadBoards();
  }, [id, loadBoards]);

  // Enriquecimiento EN VIVO sobre la pizarra actual: los items que aún están
  // "verificando en la red" lo muestran, y al resolverse se recarga la
  // pizarra (la tarea backend ya habrá reconciliado el scan_item).
  const currentItems = boards?.[0]?.items ?? [];
  const enrichStates = useEnrichments(currentItems.map((it) => it.enrichment_id));
  const resolvedKey = Object.entries(enrichStates)
    .filter(([, s]) => s.status !== "pending")
    .map(([k, s]) => `${k}:${s.status}`)
    .sort()
    .join(",");
  useEffect(() => {
    if (resolvedKey) loadBoards();
  }, [resolvedKey, loadBoards]);

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
          {current.items.map((it) => {
            const searching =
              it.enrichment_id && !it.expand?.style &&
              enrichStates[it.enrichment_id]?.status === "pending";
            return (
              <View key={it.id} style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
                <Text style={{ ...type.body, flexShrink: 1 }} numberOfLines={1}>{it.beer_name || "—"}</Text>
                {searching ? (
                  <EnrichmentPulse compact label="Verificando" />
                ) : it.expand?.style ? (
                  <FadeIn>
                    <Link href={`/cerveza/${it.expand.style.id}`}>
                      <StyleBadge name={it.expand.style.name} category={it.expand.style.category} />
                    </Link>
                  </FadeIn>
                ) : null}
              </View>
            );
          })}
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
