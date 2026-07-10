import PocketBase, { AsyncAuthStore } from "pocketbase";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { POCKETBASE_URL } from "./config";

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
      pb.collection("scans").update(s.id, { created_by: pb.authStore.record!.id })
    )
  );
}
