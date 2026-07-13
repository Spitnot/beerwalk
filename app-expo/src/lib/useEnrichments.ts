import { useEffect, useState } from "react";
import { pb } from "./pocketbase";

export type EnrichmentStatus = "pending" | "created" | "no_match" | "error";

export interface EnrichedBeer {
  id: string;
  name: string;
  brewery?: { id: string; name: string };
  style?: { id: string; name: string; category?: string };
}

export interface EnrichmentState {
  status: EnrichmentStatus;
  beer?: EnrichedBeer;
}

interface EnrichmentRecord {
  enrichment_id: string;
  status: EnrichmentStatus;
  beer?: string;
}

/** Si el enrichment terminó en `created`, trae la beer con cervecera y estilo */
async function withBeer(record: EnrichmentRecord): Promise<EnrichmentState> {
  if (record.status !== "created" || !record.beer) return { status: record.status };
  try {
    const beer = await pb
      .collection("beers")
      .getOne(record.beer, { expand: "brewery,style", requestKey: null });
    return {
      status: "created",
      beer: {
        id: beer.id,
        name: beer.name,
        brewery: beer.expand?.brewery
          ? { id: beer.expand.brewery.id, name: beer.expand.brewery.name }
          : undefined,
        style: beer.expand?.style
          ? {
              id: beer.expand.style.id,
              name: beer.expand.style.name,
              category: beer.expand.style.category,
            }
          : undefined,
      },
    };
  } catch {
    return { status: "created" };
  }
}

/**
 * Estado EN VIVO de los enriquecimientos web (collection `enrichments`).
 * Carga el estado actual y se suscribe al realtime de PocketBase (SSE, cero
 * polling): cuando la tarea en background del módulo OCR pasa de `pending` a
 * created/no_match/error, el mapa devuelto se actualiza solo.
 *
 * `assumePending`: para escaneos recién hechos — un enrichment_id sin
 * registro todavía significa "la tarea acaba de dispararse" y se muestra
 * como pending desde el primer render.
 */
export function useEnrichments(
  ids: (string | null | undefined)[],
  opts?: { assumePending?: boolean }
): Record<string, EnrichmentState> {
  const assumePending = opts?.assumePending ?? false;
  const [states, setStates] = useState<Record<string, EnrichmentState>>({});
  const key = ids.filter(Boolean).sort().join(",");

  useEffect(() => {
    const wanted = new Set(key ? key.split(",") : []);
    if (wanted.size === 0) return;
    let alive = true;

    const apply = async (record: EnrichmentRecord) => {
      const state = await withBeer(record);
      if (alive) setStates((prev) => ({ ...prev, [record.enrichment_id]: state }));
    };

    // Foto inicial: por si alguna tarea ya terminó antes de abrir la pantalla
    (async () => {
      try {
        const records = await pb.collection("enrichments").getFullList<EnrichmentRecord>({
          filter: [...wanted].map((id) => `enrichment_id="${id}"`).join(" || "),
          requestKey: null,
        });
        if (assumePending && alive) {
          const seen = new Set(records.map((r) => r.enrichment_id));
          setStates((prev) => {
            const next = { ...prev };
            for (const id of wanted) if (!seen.has(id) && !next[id]) next[id] = { status: "pending" };
            return next;
          });
        }
        await Promise.all(records.map(apply));
      } catch {
        // sin conexión no hay indicador; la pantalla funciona igual
      }
    })();

    // Realtime: una única suscripción al topic completo, filtrada en cliente
    // (los escaneos traen pocos ids y la collection tiene tráfico bajo)
    let unsubscribe: (() => void) | undefined;
    pb.collection("enrichments")
      .subscribe<EnrichmentRecord>("*", (e) => {
        if (wanted.has(e.record.enrichment_id)) void apply(e.record);
      })
      .then((un) => {
        if (!alive) un();
        else unsubscribe = un;
      })
      .catch(() => {});

    return () => {
      alive = false;
      unsubscribe?.();
    };
  }, [key, assumePending]);

  return states;
}

/**
 * ¿Hay AHORA MISMO algún enriquecimiento en curso en el sistema?
 * Para pantallas de ficha (bar/cerveza) donde no se conocen los
 * enrichment_id concretos pero una tarea pendiente puede completar campos
 * vacíos de la ficha que se está mirando.
 */
export function useAnyPendingEnrichment(): boolean {
  const [pending, setPending] = useState(false);

  useEffect(() => {
    let alive = true;
    const check = () =>
      pb
        .collection("enrichments")
        .getList(1, 1, { filter: 'status = "pending"', requestKey: null })
        .then((r) => alive && setPending(r.totalItems > 0))
        .catch(() => {});
    check();
    let unsubscribe: (() => void) | undefined;
    pb.collection("enrichments")
      .subscribe("*", check)
      .then((un) => {
        if (!alive) un();
        else unsubscribe = un;
      })
      .catch(() => {});
    return () => {
      alive = false;
      unsubscribe?.();
    };
  }, []);

  return pending;
}
