import { useEffect, useRef, useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, Text, TextInput, View } from "react-native";
import { Link, useLocalSearchParams, useRouter } from "expo-router";
import ViewShot from "react-native-view-shot";
import * as Sharing from "expo-sharing";
import { palette, radius, spacing, type } from "@/theme";
import { StyleBadge } from "@/components/StyleBadge";
import { pb, isLoggedIn } from "@/lib/pocketbase";
import { getDeviceId } from "@/lib/device";
import type { ScanItem } from "@/lib/ocr";

interface Bar {
  id: string;
  name: string;
}

/** Los ids de PocketBase tienen 15 chars; los de mocks no. Evita relaciones inválidas. */
const isPbId = (id: string | null | undefined): id is string => !!id && id.length === 15;

/**
 * Resultado del escaneo: lista EDITABLE de {cervecera, estilo, confianza}.
 * Al confirmar se crea `scan` + `scan_items` en PocketBase (created_by si hay
 * sesión, device_id si invitado) y se ofrece la card compartible (view-shot).
 */
export default function ScanResultado() {
  const router = useRouter();
  const params = useLocalSearchParams<{ payload?: string; imageUri?: string; barId?: string }>();
  // Sin payload no hay nada que revisar: esta pantalla solo se abre tras un OCR exitoso.
  const initial: ScanItem[] = params.payload ? JSON.parse(params.payload) : [];
  const [items, setItems] = useState(initial);
  const [corrected, setCorrected] = useState<Set<number>>(new Set());
  const [bars, setBars] = useState<Bar[]>([]);
  // Preseleccionado si la detección por proximidad fue CLARO; editable siempre
  const [barId, setBarId] = useState<string | null>(params.barId ?? null);
  const [saving, setSaving] = useState(false);
  const [savedBar, setSavedBar] = useState<Bar | null>(null);
  const [error, setError] = useState<string | null>(null);
  const cardRef = useRef<ViewShot>(null);

  useEffect(() => {
    pb.collection("bars")
      .getFullList<Bar>({ sort: "name", fields: "id,name" })
      .then(setBars)
      .catch(() => setError("No se pudo cargar la lista de bares."));
  }, []);

  const edit = (i: number, value: string) => {
    const next = [...items];
    next[i] = { ...next[i], beer_name: value };
    setItems(next);
    setCorrected((prev) => new Set(prev).add(i));
  };

  async function save() {
    if (!barId) {
      setError("Elige en qué bar estás antes de guardar.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("bar", barId);
      form.append("raw_ocr_json", JSON.stringify(items));
      if (isLoggedIn()) form.append("created_by", pb.authStore.record!.id);
      else form.append("device_id", await getDeviceId());
      if (params.imageUri) {
        // @ts-expect-error — React Native FormData file
        form.append("image", { uri: params.imageUri, name: "board.jpg", type: "image/jpeg" });
      }
      const scan = await pb.collection("scans").create(form);

      // Enriquecimiento web: si alguna tarea en background ya terminó, su
      // resultado está en `enrichments` — enlazamos la beer directamente.
      // Si aún no terminó, guardamos el enrichment_id y la tarea reconciliará
      // el scan_item ella misma al acabar. Un fallo aquí nunca bloquea el guardado.
      const enrichmentIds = items.map((it) => it.enrichment_id).filter((id): id is string => !!id);
      const enriched = new Map<string, { beer: string; brewery?: string; style?: string }>();
      if (enrichmentIds.length > 0) {
        try {
          const records = await pb.collection("enrichments").getFullList({
            filter: enrichmentIds.map((id) => `enrichment_id="${id}"`).join(" || "),
            expand: "beer",
            requestKey: null,
          });
          for (const r of records) {
            if (r.status === "created" && r.beer) {
              enriched.set(r.enrichment_id, {
                beer: r.beer,
                brewery: r.expand?.beer?.brewery || undefined,
                style: r.expand?.beer?.style || undefined,
              });
            }
          }
        } catch {
          // sin resultados de enriquecimiento: se guarda igual
        }
      }

      await Promise.all(
        items.map((it, i) => {
          const hit = it.enrichment_id ? enriched.get(it.enrichment_id) : undefined;
          return pb.collection("scan_items").create(
            {
              scan: scan.id,
              ...(isPbId(it.brewery?.id) ? { brewery: it.brewery!.id } : hit?.brewery ? { brewery: hit.brewery } : {}),
              ...(isPbId(it.style?.id) ? { style: it.style!.id } : hit?.style ? { style: hit.style } : {}),
              ...(isPbId(it.beer?.id) ? { beer: it.beer!.id } : hit ? { beer: hit.beer } : {}),
              ...(it.enrichment_id ? { enrichment_id: it.enrichment_id } : {}),
              beer_name: it.beer_name ?? "",
              confidence: it.confidence,
              corrected_by_user: corrected.has(i),
            },
            { requestKey: null } // permite creates en paralelo sin autocancelación del SDK
          );
        })
      );
      setSavedBar(bars.find((b) => b.id === barId) ?? null);
    } catch (e) {
      setError("No se pudo guardar el escaneo. Revisa la conexión con el servidor.");
    } finally {
      setSaving(false);
    }
  }

  async function shareCard() {
    try {
      const uri = await cardRef.current?.capture?.();
      if (uri && (await Sharing.isAvailableAsync())) {
        await Sharing.shareAsync(uri, { mimeType: "image/png", dialogTitle: "Compartir descubrimiento" });
      }
    } catch {
      setError("No se pudo generar la card para compartir.");
    }
  }

  // ── Vista post-guardado: card compartible ──────────────────────────────
  if (savedBar) {
    const today = new Date().toLocaleDateString("es-ES", { day: "numeric", month: "long" });
    return (
      <ScrollView
        style={{ flex: 1, backgroundColor: palette.bg }}
        contentContainerStyle={{ flexGrow: 1, padding: spacing(4), justifyContent: "center" }}
      >
        <Text style={{ ...type.h2, textAlign: "center", marginBottom: spacing(3) }}>¡Escaneo guardado! 🎉</Text>
        <ViewShot ref={cardRef} options={{ format: "png", quality: 1 }}>
          <View
            style={{
              backgroundColor: palette.surface,
              borderRadius: radius.lg,
              borderWidth: 1,
              borderColor: palette.line,
              padding: spacing(5),
              gap: spacing(2),
            }}
          >
            <Text style={{ fontSize: 13, fontWeight: "800", color: palette.brandDark }}>🍺 BeerWalk</Text>
            <Text style={type.h2}>{savedBar.name}</Text>
            <Text style={{ ...type.soft, marginBottom: spacing(2) }}>
              {today} · {items.length} grifos en pizarra
            </Text>
            {items.map((it, i) => (
              <View key={i} style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
                <Text style={{ ...type.body, flexShrink: 1 }} numberOfLines={1}>
                  <Text style={{ fontWeight: "800" }}>{it.beer_name || "—"}</Text>
                  {it.brewery?.name ? ` · ${it.brewery.name}` : ""}
                </Text>
                {it.style?.name ? <StyleBadge name={it.style.name} /> : null}
              </View>
            ))}
            <Text style={{ ...type.soft, marginTop: spacing(2), textAlign: "right" }}>beerwalk.app</Text>
          </View>
        </ViewShot>
        <Pressable
          onPress={shareCard}
          style={{ backgroundColor: palette.brand, borderRadius: radius.lg, padding: spacing(4), alignItems: "center", marginTop: spacing(4) }}
        >
          <Text style={{ fontWeight: "800", color: "#3D2A08" }}>Compartir card</Text>
        </Pressable>
        <Pressable onPress={() => router.back()} style={{ padding: spacing(3), alignItems: "center" }}>
          <Text style={{ ...type.soft, fontWeight: "800" }}>Volver</Text>
        </Pressable>
        {error && <Text style={{ ...type.soft, color: palette.danger, textAlign: "center" }}>{error}</Text>}
      </ScrollView>
    );
  }

  // ── Vista de revisión/edición ──────────────────────────────────────────
  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: palette.bg }}
      contentContainerStyle={{ padding: spacing(4), paddingBottom: spacing(8) }}
      keyboardShouldPersistTaps="handled"
    >
      <Text style={{ ...type.soft, marginBottom: spacing(3) }}>
        Revisa lo detectado. Toca para corregir antes de guardar.
      </Text>
      {items.map((item, i) => (
        <View key={i} style={{ backgroundColor: palette.surface, borderRadius: radius.md, borderWidth: 1, borderColor: palette.line, padding: spacing(3), marginBottom: spacing(2), gap: 6 }}>
          <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
            <Text style={{ ...type.body, fontWeight: "800" }}>{item.brewery?.name ?? "¿Cervecera?"}</Text>
            <Text style={{ ...type.soft, color: item.confidence > 0.85 ? palette.success : palette.danger }}>
              {Math.round(item.confidence * 100)}%
            </Text>
          </View>
          <TextInput
            value={item.beer_name ?? ""}
            onChangeText={(v) => edit(i, v)}
            placeholder="Nombre de la cerveza"
            style={{ ...type.body, padding: 0 }}
          />
          {item.style?.name ? (
            // Preferente: ficha completa de la cerveza si el bloque matcheó
            // el catálogo `beers`; si no, el detalle de estilo como antes.
            isPbId(item.beer?.id) ? (
              <Link href={`/cerveza/${item.beer!.id}`}>
                <StyleBadge name={item.style.name} />
              </Link>
            ) : isPbId(item.style.id) ? (
              <Link href={`/cerveza/${item.style.id}`}>
                <StyleBadge name={item.style.name} />
              </Link>
            ) : (
              <StyleBadge name={item.style.name} />
            )
          ) : (
            <Text style={type.soft}>Estilo sin detectar — toca para asignar</Text>
          )}
        </View>
      ))}

      <Text style={{ ...type.body, fontWeight: "800", marginTop: spacing(2), marginBottom: spacing(2) }}>¿En qué bar estás?</Text>
      <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 6 }}>
        {bars.map((b) => (
          <Pressable
            key={b.id}
            onPress={() => setBarId(b.id)}
            style={{
              backgroundColor: barId === b.id ? palette.brand : palette.surface,
              borderWidth: 1,
              borderColor: barId === b.id ? palette.brandDark : palette.line,
              borderRadius: radius.pill,
              paddingHorizontal: spacing(3),
              paddingVertical: spacing(2),
            }}
          >
            <Text style={{ fontWeight: "800", fontSize: 13, color: barId === b.id ? "#3D2A08" : palette.ink }}>{b.name}</Text>
          </Pressable>
        ))}
        {bars.length === 0 && <Text style={type.soft}>Cargando bares…</Text>}
      </View>

      <Pressable
        onPress={save}
        disabled={saving}
        style={{ backgroundColor: palette.brand, opacity: saving ? 0.6 : 1, borderRadius: radius.lg, padding: spacing(4), alignItems: "center", marginTop: spacing(4) }}
      >
        {saving ? <ActivityIndicator color="#3D2A08" /> : <Text style={{ fontWeight: "800", color: "#3D2A08" }}>Confirmar y guardar</Text>}
      </Pressable>
      {error && <Text style={{ ...type.soft, color: palette.danger, marginTop: spacing(3) }}>{error}</Text>}
    </ScrollView>
  );
}
