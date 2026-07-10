# 02 — Correr la app Expo en tu móvil físico

## Paso 1 — Instalar dependencias

```bash
cd app-expo
npm install
cp .env.example .env
```

## Paso 2 — Apuntar al entorno local

Tu móvil NO puede resolver `localhost` (eso sería el propio móvil). Necesitas
la IP de tu ordenador en la red wifi:

- macOS: `ipconfig getifaddr en0`
- Linux: `hostname -I | awk '{print $1}'`
- Windows: `ipconfig` → "Dirección IPv4"

Edita `app-expo/.env` con esa IP:

```
EXPO_PUBLIC_POCKETBASE_URL=http://192.168.1.XX:8090
EXPO_PUBLIC_OCR_URL=http://192.168.1.XX:8000
EXPO_PUBLIC_TRANSLATE_URL=http://192.168.1.XX:5000
```

Móvil y ordenador deben estar en la MISMA red wifi. Si no conecta, revisa el
firewall del ordenador (puertos 8090/8000/5000).

## Paso 3 — Arrancar con Expo Go (rápido, sin mapa nativo)

```bash
npx expo start
```

Instala **Expo Go** en el móvil y escanea el QR. Con Expo Go funciona TODO
excepto MapLibre (módulo nativo): el mapa muestra un placeholder y las listas
funcionan igual. Es el modo ideal para iterar en UI.

> Nota Android + HTTP: en desarrollo Expo permite tráfico http:// hacia IPs
> locales. Si en un build propio falla, añade `"usesCleartextTraffic": true`
> en android dentro de app.json (solo desarrollo; producción irá por HTTPS).

## Paso 4 — Development build (cuando toque el mapa real)

MapLibre requiere compilar un binario propio:

```bash
npx expo install expo-dev-client
npx expo run:android        # con el móvil por USB y modo desarrollador activo
# o iOS (necesita Mac + Xcode): npx expo run:ios --device
```

A partir de ahí `npx expo start` conecta con tu build en lugar de Expo Go, y
puedes descomentar la integración MapLibre en `app/(tabs)/explorar.tsx`
usando un estilo de tiles OSM libre (p. ej. OpenFreeMap Liberty).

## Estructura de la app

- `app/` — rutas (expo-router): tabs (home, explorar, escanear, buscar,
  perfil), modal de auth, resultado de escaneo, detalles, paneles por rol.
- `src/theme` — paleta viva por estilo de cerveza, radios, tipografía.
- `src/lib` — clientes de PocketBase, OCR, LibreTranslate (con cache), geo.
- `src/mocks` — datos falsos: cada pantalla funciona sin backend.
