import * as SecureStore from "expo-secure-store";

const KEY = "beerwalk_device_id";

/** id estable por instalación, para asociar escaneos en modo invitado */
export async function getDeviceId(): Promise<string> {
  let id = await SecureStore.getItemAsync(KEY);
  if (!id) {
    id = `dev_${Math.random().toString(36).slice(2)}${Date.now().toString(36)}`;
    await SecureStore.setItemAsync(KEY, id);
  }
  return id;
}
