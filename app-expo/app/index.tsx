import { useEffect, useState } from "react";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { Redirect } from "expo-router";

export default function Index() {
  const [done, setDone] = useState<boolean | null>(null);

  useEffect(() => {
    AsyncStorage.getItem("onboarding_done")
      .then((v) => setDone(v === "1"))
      .catch(() => setDone(false));
  }, []);

  if (done === null) return null; // leyendo el flag: no redirigir todavía
  return <Redirect href={done ? "/(tabs)/home" : "/onboarding"} />;
}
