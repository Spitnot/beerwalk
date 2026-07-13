import PocketBase, { AsyncAuthStore } from "pocketbase";
import AsyncStorage from "@react-native-async-storage/async-storage";
import EventSource from "react-native-sse";
import { POCKETBASE_URL } from "./config";

// El realtime de PocketBase usa Server-Sent Events y React Native no trae
// EventSource nativo — sin este polyfill, subscribe() no conecta jamás.
// En web sí existe: solo se instala si falta.
if (typeof global.EventSource === "undefined") {
  // @ts-expect-error — la firma del polyfill no es idéntica a la del DOM
  global.EventSource = EventSource;
}

/** Persistimos la sesión en AsyncStorage para sobrevivir reinicios de la app */
const store = new AsyncAuthStore({
  save: async (serialized) => AsyncStorage.setItem("pb_auth", serialized),
  initial: AsyncStorage.getItem("pb_auth"),
});

export const pb = new PocketBase(POCKETBASE_URL, store);

export const isLoggedIn = () => pb.authStore.isValid;

/**
 * Al registrarse, vinculamos los escaneos hechos como invitado (device_id)
 * al nuevo usuario, sin perder datos.
 */
export async function claimGuestScans(deviceId: string) {
  if (!pb.authStore.record) return;
  const scans = await pb.collection("scans").getFullList({
    filter: `device_id = "${deviceId}" && created_by = ""`,
  });
  await Promise.all(
    scans.map((s) =>
      // device_id en el body = prueba de posesión: la regla de scans solo
      // permite reclamar un scan sin dueño si presentas su device_id y te
      // lo asignas a ti mismo (evita que cualquier logueado reclame scans ajenos)
      pb.collection("scans").update(s.id, {
        created_by: pb.authStore.record!.id,
        device_id: deviceId,
      })
    )
  );
}
