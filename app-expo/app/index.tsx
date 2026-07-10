import { Redirect } from "expo-router";

// TODO: leer flag "onboarding_done" de AsyncStorage y decidir destino
export default function Index() {
  return <Redirect href="/onboarding" />;
}
