import { useCallback, useEffect, useState } from "react";
import { pb, isLoggedIn } from "./pocketbase";

export interface ClaimableRecord {
  id: string;
  name: string;
  claimed_by?: string;
  verified?: boolean;
}

/**
 * Patrón compartido reclamar -> verificar (panel de bar y de cervecera):
 * ambas collections tienen `claimed_by`/`verified` con las mismas reglas
 * de seguridad (ver docs/ESTADO_PROYECTO.md — solo el propio usuario puede
 * reclamar un registro SIN dueño, y nunca puede tocar `verified`, eso es
 * solo del equipo admin).
 */
export function useClaimable<T extends ClaimableRecord>(collection: "bars" | "breweries") {
  const [mine, setMine] = useState<T | null | undefined>(undefined); // undefined = cargando
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<T[]>([]);
  const [error, setError] = useState<string | null>(null);

  const loadMine = useCallback(() => {
    if (!isLoggedIn()) {
      setMine(null);
      return;
    }
    pb.collection(collection)
      .getFirstListItem<T>(`claimed_by = "${pb.authStore.record!.id}"`, { requestKey: null })
      .then(setMine)
      .catch(() => setMine(null));
  }, [collection]);

  useEffect(() => {
    loadMine();
  }, [loadMine]);

  useEffect(() => {
    if (!query.trim() || mine) {
      setResults([]);
      return;
    }
    pb.collection(collection)
      .getList<T>(1, 8, { filter: `name ~ "${query}" && claimed_by = ""`, sort: "name", requestKey: null })
      .then((r) => setResults(r.items))
      .catch(() => setResults([]));
  }, [query, collection, mine]);

  async function claim(id: string) {
    setError(null);
    if (!isLoggedIn()) {
      setError("Necesitas una cuenta para reclamar.");
      return;
    }
    try {
      const rec = await pb.collection(collection).update<T>(id, { claimed_by: pb.authStore.record!.id });
      setMine(rec);
    } catch {
      setError("No se pudo reclamar — puede que ya tenga dueño.");
    }
  }

  return { mine, query, setQuery, results, claim, error, reload: loadMine };
}
