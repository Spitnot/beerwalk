# BeerWalk — Estado del proyecto

> Checkpoint de sesión: **2026-07-13**. Este documento es la fuente de verdad
> sobre qué existe, qué se decidió y por qué. Sobrevive a cualquier limpieza
> de contexto de las sesiones de IA: ante la duda, créele a este archivo y al
> código, no a la memoria de nadie.

---

## 1. Resumen del sistema actual

BeerWalk reconoce las cervezas de la pizarra de un bar a partir de una foto y
las convierte en datos estructurados y fichas consultables. El flujo completo,
tal como funciona hoy de principio a fin:

**Escaneo.** El usuario (con cuenta o invitado) fotografía la pizarra desde la
app Expo. Antes de subir la foto, la app intenta detectar el bar por
proximidad GPS (Haversine contra la collection `bars`; casos CLARO / AMBIGUO /
SIN COINCIDENCIA con fallo seguro — sin permiso o sin señal, el escaneo sigue
igual). Solo en caso CLARO viaja un `bar_id` opcional a `POST /ocr`.

**OCR + agrupamiento.** El servicio FastAPI (`modulo-ocr`) pasa la imagen por
PaddleOCR (local, gratis) y agrupa las líneas sueltas en **bloques** por
proximidad espacial de sus bounding boxes (`blocks.py`, union-find con
umbrales calibrados contra una pizarra real en rejilla de 10 paneles que está
en `tests/fixtures/pizarra_rejilla_real.jpeg`).

**Matching + desempate.** Cada bloque se matchea con RapidFuzz
(case-insensitive, con guarda anti-falsos-positivos para nombres cortos) en
cascada: primero la **cervecera** del bloque (con alias de marca corta:
"Ayinger" ↔ "Ayinger Privatbrauerei"), después el **catálogo `beers` acotado a
esa cervecera** (Fase 0 del desempate: evita que un nombre genérico como
"Blat" se asigne a la cervecera equivocada), y por último estilos sueltos. Los
nombres genéricos ambiguos sin cervecera clara NO se adivinan. Cuando dos
candidatas de `beers` empatan en score dentro de esa cervecera, dos fases de
desempate adicionales entran en cascada (ambas con fallo seguro: si no hay
dato, no se descarta nada y sigue el criterio de siempre —nombre más largo—):
**Fase 1**, el ABV leído en el bloque (regex estricta: % o un solo decimal,
nunca un precio de dos decimales) desempata hacia la candidata cuyo ABV de
catálogo lo confirme (tolerancia ±0,4 pp); **Fase 3**, si el ABV no resolvió,
el historial de escaneos de ESE bar (`bar_id` de la detección por
proximidad) desempata hacia la candidata que ese bar ya sirvió antes (set
membership sobre `scan_items`, sin componente posicional todavía —eso es la
Fase 2, sin implementar). Antes de llegar a la cascada de `beers`, la jerga
de estilo de mostrador (NEIPA, DIPA, CDA, ESB, Hefeweizen...) se traduce a
su nombre canónico del catálogo (`resolve_style_alias`, tabla curada a mano
en `dictionary.STYLE_ALIASES`) — sin esto, "NEIPA" ya fuzzy-matcheaba al
estilo genérico "IPA" (es substring literal) perdiendo la especificidad
real de la pizarra.

**Refuerzo Vision (condicional).** Si >40% de los bloques quedan sin
reconocer o la confianza media es baja, UNA llamada a Gemini Vision lee la
imagen completa y sus bloques se fusionan con los de PaddleOCR (Vision manda
donde Paddle falló; lo que Paddle resolvió bien se conserva). Cada escaneo
deja una fila en `ocr_metrics` (tokens reales incluidos) y `GET /stats` agrega
el % semanal de escaneos con refuerzo — ese % **bajando** es la señal de que
el catálogo madura.

**Enriquecimiento (background, no bloquea).** Los bloques leídos con confianza
pero sin ficha disparan una tarea: búsqueda en la instancia **SearxNG propia**
+ extracción/corroboración/parafraseo con Gemini, con flujo
**cervecera-primero** (paso 0: hipótesis de marca del LLM, porque el texto OCR
destrozado da 0 resultados en buscadores; paso 1: confirmar cervecera y
completar su ficha; paso 2: la cerveza concreta acotada a esa marca). La
corroboración del paso 2 NO es un booleano autoevaluado por el LLM: este
aporta citas literales (`corroborating_quotes`, url + fragmento) y el código
verifica de forma independiente que cada cita existe tal cual en su página de
origen y menciona, juntos en el mismo fragmento, la cervecera Y la cerveza —
exige ≥2 citas verificadas de dominios distintos, o 1 sola si es la web
oficial ya conocida. Si hay corroboración verificada se publican
`brewery`/`beer` con `source="auto-web"`, descripción y notas de cata
**parafraseadas** y `source_url` de trazabilidad; si no, `no_match` y el item
queda "sin detectar". La reconciliación con el escaneo usa un `enrichment_id`
(UUID) que cubre ambos órdenes de llegada.

**Guardado.** La respuesta al usuario es inmediata; en `scan-resultado` revisa,
corrige, elige bar (preseleccionado si la proximidad fue CLARO) y confirma.
Se crean `scan` + `scan_items` en PocketBase (invitados vía `device_id`;
al registrarse pueden reclamar sus escaneos presentando el `device_id` como
prueba de posesión).

**Círculo virtuoso**: Vision/enriquecimiento crean fichas → los siguientes
escaneos matchean por catálogo → menos llamadas externas con el tiempo.

## 2. Decisiones de producto ya tomadas (no revisitar sin motivo nuevo)

| Decisión | Por qué |
|---|---|
| **Invitados sin cuenta crean scans/bares libremente, pero NUNCA modifican/borran nada** (ni suyo ni ajeno; solo el creador logueado o admin). | Fricción cero para el caso de uso central (cerveza en mano) sin abrir la puerta a vandalismo. El invitado recupera la propiedad al registrarse vía claim con `device_id`. Verificado con matriz curl por rol el 12-jul. |
| **Gemini se mantiene para enriquecimiento/Vision (no Ollama todavía)** — decisión revisable, con vigilancia activa de cuota/coste. | El tier gratuito cubre el volumen actual (ojo: **20 peticiones/día POR MODELO** — texto en `gemini-flash-lite-latest`, Vision en `gemini-flash-latest`, buckets separados). Ollama self-hosted queda como plan B si la cuota o el coste muerden. |
| **PaddleOCR sigue como motor principal**; no se sustituye por modelos de visión alternativos. | Se probaron GLM-OCR y PP-OCRv5 sobre pizarras reales con letra decorativa y ninguno mejoró sustancialmente. El punto débil se cubre con el refuerzo condicional de Gemini Vision, no cambiando de motor. |
| **Auto-publicación de fichas de enriquecimiento activa con confianza alta, PERO la confirmación manual del usuario en el escaneo se mantiene.** | El pipeline publica fichas de catálogo solo con corroboración clara (mejor no crear que crear mal); quitar la confirmación del usuario al guardar exige semanas de datos reales de acierto. Pendiente de revisar con métricas acumuladas. |
| **Estilos: vocabulario controlado.** El enriquecimiento NUNCA auto-crea estilos, solo enlaza por fuzzy a los existentes. | Evitar duplicados semánticos (IPA / India Pale Ale) que degradan el matching. El catálogo de estilos se cura vía seed BJCP + admin. |
| **Untappd vetado como fuente** (scraping contra sus ToS). | Solo se añadiría como fuente si algún día hay acceso a su API oficial. |
| **Birrapedia vetada como fuente** (verificación legal 12-jul-2026). | Sus condiciones de uso prohíben expresamente el acceso "a través de mecanismos/medios distintos de la interfaz" y reservan todos los derechos sobre sus bases de datos; no tiene API. Solo utilizable con autorización expresa (hay email de contacto en sus condiciones). Las tiendas online (se revisó Labirratorium) también se descartan: robots.txt anti-crawler, catálogo con copyright, sin API pública. |
| **Fuentes del seed de cerveceras: AECAI + Wikidata como índice, webs oficiales como fuente.** `description` se deja vacía en el seed. | AECAI (robots.txt permite todo) solo aporta URL + pista de nombre; Wikidata es CC0. El nombre canónico se extrae de la web oficial de cada cervecera respetando su robots.txt individual y con rate limit. La descripción de marketing de cada web tiene copyright: la rellenará el enriquecimiento con paráfrasis (misma política que BJCP). |
| **Nombre del proyecto: BeerWalk** (genérico). | Pulir marca más adelante; no invertir ahora. |
| **NUNCA mencionar ni asociar la app con CAMRA.** | Marca registrada; es solo inspiración de filosofía. No debe aparecer en UI, textos, marketing ni metadatos. |
| **Textos BJCP siempre parafraseados.** | La guía BJCP 2023 tiene copyright: los descriptivos del catálogo están redactados por nosotros; solo los rangos numéricos, códigos y ejemplos comerciales (datos factuales) se copian tal cual. Disclaimer visible en Ajustes y en el detalle de estilo. |

## 3. Arquitectura y stack — LO QUE HAY DE VERDAD

> ⚠️ Corrección de registro: en una revisión de diseño se describió por error
> una arquitectura "objetivo" con SQLite/FTS5, tabla `ocr_sinonimos`, OpenCV,
> PaddleOCR "Slim" y Qwen 2.5. **Nada de eso existe en este repo.** Lo real:

- **App móvil**: Expo SDK 54 (React Native, expo-router, Expo Go). GPS con
  expo-location. Realtime de PocketBase por SSE con polyfill
  `react-native-sse` (RN no trae EventSource; el polyfill se instala en
  `src/lib/pocketbase.ts` solo si falta — en web se usa el nativo). `app-expo/`.
- **Backend de datos**: **PocketBase** (SQLite embebido, pero vía PocketBase —
  no hay SQLite propio ni FTS5). Schema en `pocketbase/pb_schema.json`
  (12 collections). Reglas por rol endurecidas + rate limiting nativo por IP.
- **Servicio OCR**: FastAPI (`modulo-ocr/`): PaddleOCR estándar + PIL (sin
  OpenCV) + RapidFuzz + agrupación espacial propia (`blocks.py`). Sin tabla de
  sinónimos (el equivalente funcional son los alias de marca en
  `dictionary.py` y el matching case-insensitive).
- **Búsqueda web**: **SearxNG self-hosted** (servicio del docker-compose, API
  JSON, sin API key) — misma filosofía que LibreTranslate.
- **LLM**: **Gemini** vía API (no Qwen, no Ollama): `gemini-flash-lite-latest`
  para texto (extracción/parafraseo) y `gemini-flash-latest` para Vision.
  Gotchas documentados en el código: usar SIEMPRE alias `-latest` (las
  versiones fijas rechazan usuarios nuevos), saltar los "thought parts" al
  parsear, backoff largo en 429.
- **Traducción**: LibreTranslate self-hosted (post-MVP en la UI).
- **Infra local**: docker-compose (`pocketbase` 8090, `ocr` 8000, `searxng`
  8888, `translate` 5000). Producción prevista: mismo compose en Coolify.
- **Background jobs**: BackgroundTasks nativas de FastAPI, sin cola. Limitación
  aceptada del MVP: si el proceso se reinicia a mitad de tarea, se pierde sin
  reintento (documentado en `enrichment.py`; revisar si crece el volumen).

## 4. Estado de cada bloque/fase (a 2026-07-12)

| Frente | Estado |
|---|---|
| Bloque 1 — Enriquecimiento cervecera-primero + `tasting_notes` + ficha de cerveza en UI | ✅ Terminado, verificado e2e (caso "Aymgar"→Ayinger) y commiteado |
| Bloque 2 — Catálogo BJCP 2023 (39 estilos, 7 familias editoriales, disclaimer, badges ABV/IBU/SRM, buscador ordenado) | ✅ Terminado, verificado (seed idempotente + curl) y commiteado |
| Bloque 3 — seed de cerveceras españolas | ✅ Terminado (13-jul). Verificación legal hecha: Birrapedia y tiendas descartadas (ver decisiones), AECAI + Wikidata como índice. `modulo-datos/seed_breweries_es.py` construido y ejecutado: 59 candidatas procesadas, catálogo en **76 cerveceras** (antes ~18). Idempotente verificado (re-ejecución: 0 creadas, 59 al día), dedupe por nombre normalizado + dominio de source_url, checkpoint incremental (gitignorado), robots.txt por dominio + rate limit 1,5s, guard anti-dominios-expirados (caso real: la web de Dos Dingos sirve un casino chino — su ficha apunta al índice AECAI). Objetivo ~200 NO alcanzado de golpe por diseño: el resto crece orgánicamente vía enriquecimiento. Reglas admin-only verificadas con curl (sin auth 400 / superuser crea+borra). |
| Bloque 4 — Indicador visual de enriquecimiento en curso (estado `pending` + realtime de PocketBase + UI animada) | ✅ Terminado (13-jul). Backend: `pending` añadido al select de `enrichments` (schema + PB vivo), la tarea lo escribe al arrancar y el resultado final PATCHea ese mismo registro (upsert por `enrichment_id`, nunca dos filas). Frontend: realtime de PocketBase vía SSE (polyfill `react-native-sse`, imprescindible en RN), hook `useEnrichments` (suscripción única filtrada en cliente, cero polling), indicador propio `EnrichmentPulse` (lupa oscilando + puntos "escribiendo" + glow ámbar respirando sobre la card, nada de ActivityIndicator) y transición con fade al resolver. Aplicado en `scan-resultado` (con fusión del resultado en el item), `bar/[id]` (pizarra actual, recarga al resolver) y `cerveza/[id]` (ficha viva suscrita a su beer/brewery; huecos muestran "buscando" si hay enriquecimiento en curso). **Verificado e2e con escaneo real**: 4 tareas emitieron `create: pending` → `update: no_match` por SSE (suscriptor Node con el mismo SDK), y tránsito `pending→created` con relación `beer` verificado aparte. Los 4 bloques originales están completos. |
| Desempate — Fase 0 (acotado por cervecera) | ✅ Hecha y verificada con la pizarra real |
| Desempate — Fase 1 (regex ABV con fallo seguro y tolerancia ±0,4, NUNCA igualdad exacta) | ✅ Terminada (13-jul). `app/abv.py` nuevo: exige % o un solo decimal (nunca un precio de dos), rango de cordura 2-20% (descarta volúmenes en litros tipo "0,5L"). Actúa como tie-break DENTRO de `_best_match` solo entre candidatas ya empatadas en score — nunca impone, nunca descarta por ausencia de dato. Verificado con la pizarra real: 0/10 bloques cambian (ninguno de esos textos trae un ABV limpio; comprobado emparejando por similitud de texto, no por índice, porque PaddleOCR no es perfectamente determinista entre ejecuciones) y con tests sintéticos donde el ABV sí decide correctamente entre dos nombres empatados. |
| Desempate — Fase 2 (persistir coordenadas de bloques en scan_items) | ⏳ Sin implementar (fuera de alcance de esta sesión) |
| Desempate — Fase 3 (historial de bar) | ✅ Terminada (13-jul). Versión simple acordada: set membership sobre `beer` de `scan_items` pasados de ese `bar_id` (`get_bar_beer_history` en `dictionary.py`, filtro `scan.bar = "X" && beer != ""`), sin componente posicional (eso es Fase 2). Mismo tie-break dentro de `_best_match`, en cascada DESPUÉS de la Fase 1: solo actúa si tras el ABV sigue habiendo empate. Fallo seguro: sin `bar_id` o bar sin historial, no cambia nada. Verificado con datos reales (bar+scan_item creados y borrados contra el PocketBase vivo) y con tests que confirman que la Fase 1 sigue mandando cuando decide, aunque el historial "prefiera" la otra candidata. |
| Seguridad por rol (12 collections) | ✅ Cerrada y verificada con matriz curl real por rol (incluye fix de auto-escalado a admin y claim seguro por `device_id`) + rate limiting nativo activado |
| Pipeline híbrido PaddleOCR + Gemini Vision + métricas `ocr_metrics`/`GET /stats` | ✅ Hecho y verificado (foto real de 10 paneles, tokens y coste medidos) |

**Pendientes menores anotados por el camino:**

- ~~Endurecer el prompt de corroboración del paso 2 del enriquecimiento~~ ✅
  **Arreglado (13-jul)**. El falso positivo real ("Capricorn Feat Artesants"
  corroborada para el hint "Blat" de Espiga) pasó porque el listón era un
  booleano autoevaluado por el propio LLM, sin ninguna verificación
  estructural: una fuente que solo mencionaba el descriptor de estilo
  ("Blat"=trigo) sin el nombre de la cervecera bastó para que el modelo se
  autoconvenciera de "≥2 fuentes independientes". Ahora el LLM aporta citas
  literales y el código verifica en `_verify_corroboration`
  (`enrichment.py`) que cada una existe tal cual en su página y menciona
  cervecera+cerveza juntas — ver detalle en §7.
- ~~Alias de estilos para el matching~~ ✅ **Cerrado (13-jul, noche)**. Ver
  detalle en §9.
- El juicio del LLM en el paso 2 (si hay o no citas verificables) puede tener
  varianza entre ejecuciones. Aceptable por diseño, pero vigilarlo en las
  métricas ahora que el listón es más estricto.
- **Duplicado real de beer detectado en un escaneo de prueba (13-jul)**: la
  deduplicación de `beers` (hoy: nombre exacto + fuzzy por cervecera en
  `enrichment.py`) puede necesitar el mismo refuerzo que se aplicó a
  `breweries` tras el caso del dominio secuestrado (variantes de nombre
  normalizado + comparación por dominio de source_url). Las 3 fases del
  desempate y el listón de corroboración ya se cerraron esta sesión sin
  abordar esto — sigue pendiente, sin arreglar.
- `docs/01-03` anteriores pueden contener detalles desactualizados respecto a
  este documento; este archivo manda.

## 5. Próximo paso concreto

**Los 4 bloques originales, las 3 fases del desempate abordadas (0, 1, 3),
el arreglo del listón de corroboración, el seed de bares vía OSM y el alias
de estilos están completos.** Lo que queda, por orden de valor:

1. **Revisar los 21 casos dudosos** del seed de bares OSM en
   `modulo-datos/seed/.bars_osm_review.json` (§8) — decisión de admin, no
   automatizable con la info disponible.
2. **Deduplicación de `beers`** — revisar si necesita el mismo refuerzo que
   `breweries` (variantes de nombre normalizado + dominio de source_url),
   a raíz del duplicado real detectado en un escaneo de prueba (§4).
3. **Fase 2 del desempate** (persistir coordenadas de bloques en
   `scan_items`, componente posicional) — deliberadamente fuera de alcance
   hasta ahora; sin implementar.
4. Vigilar en las métricas si el listón de corroboración más estricto
   (§7) reduce demasiado la tasa de auto-publicación — el criterio nuevo es
   honesto pero más exigente; si `no_match` sube mucho, revisar el prompt.
5. **Extender el seed de bares OSM** a más ciudades/regiones (hoy solo
   Barcelona ciudad) reejecutando `seed_bars_osm.py` con otro `--bbox`/
   `--city` — es idempotente y seguro de repetir.

Pendiente de validación en dispositivo (no bloquea): el indicador del
Bloque 4 está verificado a nivel de datos y suscripción con el mismo SDK de
la app; falta solo verlo en Expo Go en un móvil (animación y transiciones),
sin entorno de simulador en esta máquina.

Notas del Bloque 3 que quedan vivas:

- Las fichas del seed tienen `description` vacía a propósito (copyright);
  se completan vía enriquecimiento. Unas 8 tienen `source_url` apuntando al
  índice AECAI porque su web oficial estaba caída/bloqueada — candidatas a
  revisión manual del admin.
- El seed es re-ejecutable sin miedo (idempotente en nombre y dominio); si se
  quiere refrescar contra las webs, borrar antes
  `modulo-datos/seed/.breweries_es_checkpoint.json`.

## 6. Auditoría de estado completa (13-jul-2026)

Revisión post-bloques de TODO el frente de app, pipeline y seguridad, con
código leído y curl real contra el PocketBase vivo.

### 6.1 Pantallas — real vs mock

| Pantalla | Estado | Detalle |
|---|---|---|
| Home (feed) | ✅ REAL (cerrado 13-jul, ver §10) | Dos carruseles de descubrimiento con datos reales (`beers`/`scans`); el mini-mapa sigue siendo un placeholder estático que enlaza a Explorar (el Mapa en sí queda fuera de este encargo). |
| Buscador — estilos | ✅ REAL | Catálogo BJCP de PocketBase con orden editorial por familias (Bloque 2). |
| Buscador — bares | ✅ REAL (cerrado 13-jul, commit `7ba4e50`) | Mismo patrón que cerveceras: texto libre por nombre/dirección contra `bars` real, `mockBars` fuera de esta pantalla. |
| Buscador — cerveceras | ✅ REAL (cerrado 13-jul, post-auditoría) | Sección CERVECERAS contra `breweries` real: búsqueda de texto libre por nombre u origen, contador de cervezas en catálogo por cervecera (una sola lectura de `beers` agregada en cliente, sin N+1), y nueva pantalla `cervecera/[id]` (descripción enriquecida o "buscando…" con el patrón del Bloque 4, ficha viva por realtime, y sus cervezas del catálogo enlazando a `cerveza/[id]`, que a su vez enlaza de vuelta). `verified` no se muestra ni filtra (flag interno de admin). `Section` extraída a componente compartido. Verificado con datos reales: "espiga"/"ayinger"/"gara" devuelven las fichas reales del catálogo de 76. |
| Perfil (estadísticas) | ✅ REAL (cerrado 13-jul, ver §10) | Estadísticas agregadas de verdad sobre `scan_items` propios (invitado vía `device_id`, logueado vía `created_by`) + historial de escaneos propios en lista vertical. |
| Panel de bar | ✅ REAL (cerrado 13-jul, ver §10) | Reclamar → verificar → histórico, con `claimed_by`/`verified` reales de `bars` (reglas de seguridad ampliadas para permitirlo). |
| Panel de cervecera | ✅ REAL (cerrado 13-jul, ver §10) | Mismo patrón sobre `breweries`, con formulario de edición básica real (origin/description/source_url). |
| Panel de admin | ✅ REAL (cerrado 13-jul, ver §10) | Lista real de bares/cerveceras reclamados sin verificar + acción real de verificar + botón real a `POST /dictionary/refresh`. "Duplicados pendientes de fusión" queda explícitamente sin implementar (sin mecanismo de detección real todavía — no se fabricó un dato falso). |
| Ajustes | 🟨 MIXTO | Idioma/notificaciones/borrar-datos son texto no funcional; la sección "Acerca de" (disclaimer BJCP + enlace) sí es real. |
| Explorar/mapa | 🟨 MIXTO | Bares desde PocketBase (fallback a mock sin red); MapLibre solo en dev build y el placeholder de Expo Go sigue correcto (check de `appOwnership`, plugin fuera de app.json). |
| bar/[id], cerveza/[id], scan-resultado | ✅ REAL | PocketBase + realtime del Bloque 4. |

### 6.2 Pipeline — cabos sueltos confirmados (estado en el momento de la auditoría, 13-jul mañana)

> Todo lo de esta subsección quedó CERRADO más tarde la misma sesión —
> ver §7 para el detalle de la implementación real. Se deja el texto
> original de la auditoría sin reescribir, como registro de qué estaba
> pendiente en ese momento.

- **Fase 1 desempate (ABV)**: NO implementada en ningún momento intermedio —
  cero código de filtro ABV en el matching (el `abv` solo se guarda en fichas
  vía enriquecimiento). Sigue solo diseñada.
- **Fase 3 desempate (historial de bar)**: bloqueada SOLO por implementación.
  El `bar_id` llega verificado a `/ocr` y el hook TODO está en `main.py`;
  no hay ningún otro prerequisito pendiente.
- **Listón de corroboración**: SIN TOCAR. El prompt mantiene el criterio
  simple ("≥2 fuentes independientes O la web oficial") que causó el falso
  positivo "Capricorn". Nota: en el escaneo real del 13-jul se comportó
  conservador (4/4 no_match), la varianza documentada sigue.
- **Seed de bares OSM/Overpass**: NO implementado — cero referencias en el
  código. Bares en BD: **3** (los demo originales: La Espuma, El Grifo
  Dorado, Bar Llúpol). (Cerrado más tarde la misma sesión — ver §8.)

### 6.3 Seguridad — sin regresiones

- Diff programático reglas vivas ↔ `pb_schema.json`: **0 diferencias** en las
  12 collections (los cambios de schema de BJCP/cerveceras/pending no tocaron
  reglas).
- Spot-checks curl (13-jul): POST `beers` sin auth → 400; PATCH `bars` sin
  auth → 404 (oculto); signup con `role=admin` → 400 (anti-escalado intacto);
  invitado crea scan con `device_id` → 200 (fricción cero intacta).
- Rate limiting nativo: ACTIVO, 5 reglas.

### 6.4 Mejoras de UX del escaneo (13-jul, post-auditoría)

1. **Loading del escaneo con vida**: `ScanningBoard` (lupa barriendo la
   pizarra + glow ámbar + puntos) sustituye al ActivityIndicator estático de
   `escanear.tsx` que parecía un cuelgue. Mismo lenguaje visual que
   EnrichmentPulse.
2. **Bar desacoplado del resultado**: `scans.bar` pasó a opcional (PB vivo +
   schema, verificado con curl), `save()` ya no exige bar, el selector se
   marca "(opcional)" y la card compartible funciona sin bar ("Pizarra
   descubierta"). Ver resultados y guardarlos nunca depende del bar.
3. **scan-resultado rediseñada a cards con jerarquía**: borde de color por
   estilo (styleColors), cervecera enlazada a su ficha, nombre grande
   editable, badge de estilo + AbvPill, y fragmento de cata/descripción
   (beer > cervecera > estilo) — lo que no se lee en la tiza. Con
   EnrichmentPulse si aún se enriquece; nunca hueco vacío. `AbvPill` extraído
   a componente compartido (cerveza/cervecera/scan-resultado).

### 6.5 Resumen ejecutivo (momento de la auditoría, 13-jul mañana)

- **Bloques originales: 4/4 terminados al 100%** (1 enriquecimiento, 2 BJCP,
  3 cerveceras, 4 indicador realtime).
- **Fases del desempate (1-3): 0/3 empezadas** (la Fase 0 previa sí está
  hecha y verificada; la 3 tiene el terreno preparado con `bar_id` + hook).
- **A medias / deuda visible**: Home, Buscador de bares, Perfil y los 3
  paneles siguen en mock/placeholder. (La búsqueda de cerveceras, detectada
  como inexistente en esta auditoría, se cerró el mismo 13-jul — ver 6.1.)

> Actualización de la tarde del mismo 13-jul: Fase 1, Fase 3 y el listón de
> corroboración se implementaron y verificaron — ver §7. El resumen de
> arriba queda como estaba en el momento de la auditoría; el estado real
> y actual de las 3 fases está en la tabla de §4.

## 7. Cierre de las 3 fases del desempate + arreglo de corroboración (13-jul, tarde)

Sesión de continuación tras la auditoría de §6: cierre de Fase 1, Fase 3, y
el pendiente de corroboración que ya se había anotado.

### 7.1 Fase 1 — filtro de ABV

`modulo-ocr/app/abv.py` (nuevo): `extract_abv(text)` exige `%` (entero o un
decimal) o, sin símbolo, un patrón estricto de UN SOLO decimal —
`(?<!\d)(\d{1,2}[.,]\d)(?!\d)`. Un precio español ("4,50", dos decimales)
nunca matchea por el lookahead; un rango de cordura 2-20% descarta además
volúmenes de servicio en litros ("0,5L") que calzarían el mismo patrón.

En `matching.py`, `_best_match` acepta `abv_lookup`/`block_abv` opcionales:
si hay empate de score entre candidatas de `beers`, y hay ABV limpio en el
bloque, se filtra hacia las empatadas cuyo `abv` de catálogo esté a ≤0,4 pp
(`ABV_TOLERANCE` en `config.py`) — solo si eso deja al menos una candidata;
si no, no se toca nada (fallo seguro bidireccional). `dictionary.py` ahora
trae `abv` del catálogo `beers` (campo añadido a `_fetch_beers`).

Verificación: 8 tests nuevos en `test_abv.py` + 4 en `test_matching.py`
(caso sintético real: "Blat"/"Blanc" empatan a 100 de partial_ratio —
verificado con rapidfuzz directamente— y sin Fase 1 el criterio de siempre
elige mal "Blanc"; con ABV de bloque=5,1 elige bien "Blat"). Contra
`pizarra_rejilla_real.jpeg`: **0/10 bloques cambian** — ninguno de esos
textos trae un ABV limpio (verificado con `extract_abv` sobre los 10
textos reales), así que la nueva lógica no tiene ocasión de actuar en esta
foto concreta; comprobado emparejando por similitud de texto entre dos
ejecuciones, no por índice, porque PaddleOCR no es perfectamente
determinista entre corridas (reordena bloques y varía ligeramente el texto).

### 7.2 Fase 3 — historial de bar

Versión simple acordada: set membership, sin componente posicional
(eso sería Fase 2, sin implementar). `dictionary.py` añade
`get_bar_beer_history(bar_id)`: pagina `scan_items` filtrando
`scan.bar = "X" && beer != ""` y devuelve el set de ids de `beer` ya vistos
en ese bar. Fallo seguro: cualquier error o bar sin escaneos → set vacío.

`main.py` la llama una vez por escaneo cuando hay `bar_id` (proximidad
CLARO) y pasa el resultado a cada `match_block(..., bar_beer_ids=...)`.
Dentro de `_best_match`, este historial es un tie-break que actúa EN
CASCADA DESPUÉS de la Fase 1: si, tras el filtro de ABV, sigue habiendo
empate de score, se prefiere la candidata cuyo id conste en el historial
del bar — y solo si al menos una de las empatadas consta (si no, no se
toca nada).

Verificación: 4 tests nuevos en `test_matching.py`, incluyendo el punto
crítico pedido — `test_fase1_decide_antes_de_llegar_a_fase3`: con ABV en el
bloque, la Fase 1 ya resuelve el empate hacia "Blat", y aunque el historial
del bar "prefiera" a propósito la otra candidata ("Blanc", conflicto
deliberado), Fase 3 nunca llega a actuar porque el empate ya no existe.
Además, verificación con datos REALES: bar y `scan_item` creados en el
PocketBase vivo (Cerveseria La Espuma + Ayinger Bräuweisse), confirmado que
`get_bar_beer_history()` devuelve el id correcto contra la API real, y
limpieza posterior de los registros de prueba.

### 7.3 Arreglo del listón de corroboración

Causa raíz confirmada en `enrichment.py`: `"corroborated": bool` era un
juicio autoevaluado por el propio LLM sin ninguna verificación estructural
detrás. Con el hint "Blat" (trigo, catalán) para Espiga, la búsqueda trajo
páginas de OTRA marca ("Capricorn Feat Artesants") que solo mencionaban el
descriptor de estilo, nunca "Espiga" — y el modelo las contó como "fuentes
independientes" de esa cerveza sin que nada se lo impidiera.

Arreglo: el LLM ya no declara "corroborado", aporta **evidencia**
(`corroborating_quotes`: lista de `{url, quote}` con el fragmento LITERAL
de una de las páginas dadas). `_verify_corroboration` (nueva, en
`enrichment.py`) audita en código cada cita: (1) debe ser localizable tal
cual en el texto de la página que dice citar (rechaza invención/paráfrasis);
(2) debe mencionar, dentro de ese mismo fragmento corto (máx. 300
caracteres), tanto la marca como el nombre de la cerveza (rechaza fuentes
tangenciales que solo hablan del estilo/descriptor genérico — exactamente
el hueco que dejó pasar Capricorn). Sigue exigiendo ≥2 citas verificadas de
dominios distintos, o 1 sola si su dominio es la web oficial ya conocida de
la cervecera (`brewery.source_url`, fetch añadido en `_enrich_item_inner`).

Verificación: 8 tests nuevos en `test_corroboration.py`, incluyendo la
reproducción exacta del patrón Capricorn (se rechaza), dos fuentes
independientes válidas (corrobora), la web oficial sola (corrobora), una
fuente no oficial sola (no basta, sin cambios respecto al criterio previo),
cita inventada/no localizable (se descarta), cita de una URL fuera de las
páginas dadas (se descarta), cita demasiado larga (se descarta), y **Ayinger**
(caso real ya enriquecido del Bloque 1) con dos fuentes reales que sí
mencionan marca+cerveza — confirma que el listón más estricto no rompe lo
que sí debe pasar.

### 7.4 Estado de los tests

`modulo-ocr/tests`: **44/44 en verde** (22 antes de esta sesión + 6 nuevos
en `test_abv.py` + 4 de Fase 1 y 4 de Fase 3 en `test_matching.py` + 8 en
`test_corroboration.py` − ninguno roto). Servicio `ocr` reconstruido y sano
en cada paso.

## 8. Seed de bares reales vía OpenStreetMap (13-jul, noche)

Por qué ahora: la detección de proximidad GPS y la Fase 3 del desempate
(§7) solo se pueden probar de verdad con densidad real de bares — hasta
este seed solo había 3 (los demo). Piloto: Barcelona ciudad.

### 8.1 Fuente y esquema

**Overpass API** (OpenStreetMap), sin API key, datos © OpenStreetMap
contributors bajo licencia ODbL. Gotcha real: la petición sin headers da
**406** del Apache de overpass-api.de (no del intérprete) — hace falta
`User-Agent` descriptivo y `Accept: application/json, text/*;q=0.1`
explícitos.

Etiquetas consultadas: `amenity=bar`, `amenity=pub`, `craft_beer=yes`,
`microbrewery=yes`. Probado en Barcelona ciudad: `craft_beer=yes` dio
**0 resultados** (la etiqueta apenas se usa en OSM España) y
`microbrewery=yes` solo 15 — `amenity=bar`/`pub` domina el volumen (1764
nodos totales, 1641 con nombre) y es el universo correcto: cualquier bar
es un sitio válido de escaneo, no hace falta que esté especializado en
cerveza artesana. No se descartó ninguna etiqueta por "ruido" de datos mal
etiquetados — el volumen es simplemente denso en una ciudad grande.

Campos nuevos en `bars` (schema vivo + `pb_schema.json`, mismo patrón que
`pending` en `enrichments`): `source` (text), `verified` (bool), `osm_id`
(text, `"node/<id>"` — permite reconocer en re-ejecuciones qué nodo OSM ya
se sembró sin depender de fuzzy matching).

### 8.2 Deduplicación en cascada (nunca a ciegas)

`modulo-datos/seed_bars_osm.py`, con `rapidfuzz.token_set_ratio` (no
`ratio` simple — se probó empíricamente contra pares reales de Barcelona:
`ratio` da 60-89 para variantes legítimas del mismo bar como "Peter Pan"
vs "Peter Pan Bar", perdiendo separación frente a nombres realmente
distintos; `token_set_ratio` da 100 en esas mismas variantes y ≤45 en
pares de bares distintos de la muestra — mucho mejor separado) y radio
Haversine de 30m:

1. `osm_id` ya sembrado → re-ejecución idempotente, se salta.
2. ≤30m + similitud ≥90 → MISMO bar: no se crea, se completan huecos
   (address/source/osm_id) sin pisar nada.
3. ≤30m + similitud <55 → bares DISTINTOS que coinciden en la misma
   zona/calle: se crea normal.
4. ≤30m + similitud [55,90) → caso DUDOSO: no se decide solo, se anota en
   `seed/.bars_osm_review.json` (candidato + bar existente parecido +
   distancia + similitud) y no se toca PocketBase para ese candidato.

Efecto colateral útil no buscado: como el script compara cada candidato
contra TODO lo ya visto (incluidos los candidatos ya "creados" en el mismo
lote), también detecta duplicados **dentro de los propios datos de OSM**
(el mismo local mapeado dos veces por contribuyentes distintos) — 6 casos
reales en Barcelona (ej. "Shôko"/"Shôko" a 23m, "Temple Bar"/"Temple Bar
Irish Pub" a 10m), fusionados igual que si fueran duplicados contra
PocketBase.

### 8.3 Resultado en Barcelona ciudad

bbox `41.32,2.05,41.47,2.23` (Barcelona ciudad; parámetro también acepta
`--city "Barcelona, Spain"`, que geocodifica el bbox vía Nominatim, sin
key). Resultado real:

- **1641 bares con nombre** encontrados por Overpass (de 1764 nodos
  totales; 123 sin nombre en OSM, descartados — `name` es obligatorio).
- **1614 creados**, **6 duplicados** (fusionados, ver 8.2), **1 completado**
  (hueco rellenado en un bar existente), **21 dudosos** anotados para
  revisión de admin.
- **Total de bares en PocketBase: 1617** (3 demo + 1614 nuevos).
- **Idempotencia verificada**: re-ejecutar el mismo comando da
  `0 creados, 6 duplicados, 0 completados, 21 dudosos` — exactamente
  reproducible, no genera basura al repetir.

Muestra real (10 de los 1614): Bar-Granja la Crema, JazzMan, Bar Lua,
Zorita, Bar Celona Chic, Bar Saint Michel, La Mulatona, Bar Lips,
Vermuteria Catalana, La bodegueta de Guinardó — todas con lat/lng reales
y la mayoría con dirección de OSM.

### 8.4 Verificación de permisos con curl real

**Corrección de premisa**: `bars.createRule` NO es admin-only — está
vacío (`""`), decisión de producto ya documentada en §2 ("invitados sin
cuenta crean scans/bares libremente"). Verificado con curl real: POST sin
auth a `bars` → **200** (cualquiera puede crear un bar). Lo que SÍ es
admin/dueño-only es `updateRule`: PATCH sin auth → **404** (oculto);
PATCH con superuser → **200**. El script usa credenciales de superusuario
de todas formas (igual que los demás seeds) porque la parte de completar
huecos en bares existentes SÍ necesita esas credenciales.

### 8.5 Pendiente

Los 21 casos de `seed/.bars_osm_review.json` son decisión de admin (ver
§5). El script es reejecutable para otras ciudades/bboxes sin tocar nada;
Cataluña completa o el resto de España quedan para cuando se decida
ampliar el piloto.

## 9. Alias de jerga de estilos (13-jul, noche)

Diseño recibido de un chat externo sin acceso al repo (útil como
inspiración de intención, no aplicado como diff literal — se adaptó al
`dictionary.py`/`matching.py` reales de después de Fase 1/Fase 3/
corroboración).

### 9.1 El problema real (confirmado antes de tocar código)

Sin este arreglo, "NEIPA" ya **fuzzy-matcheaba accidentalmente** al estilo
genérico "IPA" con `partial_ratio`=100 (porque "IPA" es substring literal
de "NEIPA"), mientras que el estilo realmente correcto ("Hazy IPA") solo
alcanzaba 66,7 — por debajo del `MATCH_THRESHOLD`. Mismo patrón con "DIPA"
(100 vs "IPA", 62,5 vs "Double IPA" real). Verificado directamente con
rapidfuzz antes de escribir nada, para confirmar que el pendiente era real
y no solo teórico.

### 9.2 Diseño implementado

- **`dictionary.STYLE_ALIASES`**: tabla curada a mano, deliberadamente
  conservadora — NEIPA→Hazy IPA, DIPA→Double IPA, CDA→Black IPA,
  APA→Pale Ale, ESB→Best Bitter, RIS→Imperial Stout,
  Hefeweizen/Weizen/Weissbier→Wheat, Blanche→Witbier. Ninguna abreviatura
  ambigua (tipo "TIPA", que en la práctica puede significar cosas
  distintas según el bar) — mejor sin resolver que crear una identidad
  falsa, mismo criterio que el resto del desempate.
- **`matching.resolve_style_alias(text, styles)`**: función pura, TOKEN
  EXACTO tras normalizar (no fuzzy — un partial_ratio laxo sobre
  abreviaturas de 3-4 letras daría falsos positivos). Fallo seguro DOBLE:
  (1) si el canónico no existe en el catálogo `styles` actual, no resuelve
  — nunca inventa un id; (2) si la propia clave del alias coincidiera con
  un estilo REAL ya existente en el catálogo (caso hipotético, no pasa hoy
  con el catálogo BJCP), tampoco resuelve — nunca pisa una entrada real.
- **Dónde se llama**: en `match_line` (`matching.py`), como intento previo
  a la fuzzy normal — `resolve_style_alias(line, styles) or _best_match(...)`
  — y en el mismo punto para el refuerzo Vision (`vision.py`,
  `build_vision_item`), para que un "NEIPA" leído por Gemini Vision se
  canonice igual que uno leído por PaddleOCR. El catálogo `beers` (cuando
  hay match directo de cerveza) no lo necesita: su `style` sale de la
  relación ya guardada, canónica por construcción.
- **Requisito de visualización — solo estilos, no cerveceras**: el
  resultado de `resolve_style_alias` SIEMPRE muestra el nombre canónico
  ("Hazy IPA"), nunca la jerga de la pizarra. El alias corto de
  CERVECERA (`brand_aliases` en `dictionary.py`, ej. "Ayinger" en vez de
  "Ayinger Privatbrauerei") sigue mostrándose tal cual — comportamiento
  intacto, verificado con test explícito de coexistencia.

### 9.3 Verificación

`modulo-ocr/tests`: **57/57 en verde** (44 antes de esta sesión + 9 en
`test_style_aliases.py` nuevo + 4 de integración en `test_matching.py`).
Casos cubiertos: cada alias de la tabla resuelve a su canónico; fallo
seguro cuando el canónico no está en el catálogo (CDA sin "Black IPA" en
la BD → no resuelve); fallo seguro de no-pisar (caso hipotético "APA" real
+ "Pale Ale" real coexistiendo → no resuelve, se deja para el fuzzy
normal); exige token completo, no substring ("Capadipa" no dispara DIPA);
texto sin jerga conocida no resuelve; y el test de coexistencia confirma
que en la misma línea el alias de cervecera se muestra corto ("Ayinger")
mientras el de estilo se muestra canónico ("Hazy IPA"). Servicio `ocr`
reconstruido y sano (sin ciclos de import entre `matching.py` y
`dictionary.py`).

## 10. Home, Perfil y paneles con datos reales (13-jul, madrugada)

Las 5 pantallas que quedaban en mock/placeholder tras la auditoría de §6
(salvo el Mapa, deliberadamente fuera de este encargo) pasan a datos
reales de PocketBase. Sin referencias visuales disponibles
(`design-system-reference/` no existe en el repo): se usaron los tokens
de `theme/index.ts` tal cual, como se pidió explícitamente.

### 10.1 Criterio carrusel vs. lista — decisión por sección

| Pantalla · sección | Decisión | Por qué |
|---|---|---|
| Home · "Últimas descubiertas" (`beers` recientes) | Carrusel | Descubrimiento puro: sin jerarquía entre cervezas nuevas, nada pasa si el usuario no ve alguna. |
| Home · "Actividad cerca" (`scans` recientes) | Carrusel | Mismo motivo: es "qué se está escaneando por ahí", para curiosear, no un registro que auditar. |
| Perfil · "Tus escaneos" (historial propio) | **Lista vertical** | Es TU propio registro — hay que poder repasarlo entero para saber qué has hecho; ocultar uno por diseño sería perder tu propio historial. |
| Panel de bar · histórico de pizarras del local | **Lista vertical** | Ya identificado en el encargo original: registro que hay que poder auditar completo. |
| Panel de admin · pendientes de verificar | **Lista vertical** | Es una cola de moderación: el admin necesita verlas TODAS, ninguna puede quedar oculta tras un swipe. |

Los carruseles usan cards planas sin sombra (ya era el estilo de la app) con
ancho fijo menor que la pantalla, así la siguiente card asoma cortada en el
borde — la única pista de que hay más contenido, tal como se pidió.

### 10.2 Hallazgo de seguridad y cambio deliberado (aprobado antes de construir)

Verificado con curl ANTES de tocar código: un usuario normal reclamando un
bar u una cervecera sin dueño recibía **404** en ambos casos — la regla
existente solo permitía editar si `claimed_by` YA eras tú, nunca la
transición inicial "sin reclamar → reclamado por mí" para nadie que no
fuera admin. `breweries.updateRule` además era admin-only sin excepción, ni
siquiera un dueño ya reclamado podía editar su propia ficha.

Se amplió `bars.updateRule` y `breweries.updateRule` (schema + PocketBase
vivo) con un guardarraíl explícito: el reclamante puede fijar `claimed_by`
en un registro sin dueño y editar sus otros campos, pero **nunca puede
tocar `verified`** en la misma petición (mismo patrón que ya protege `role`
en `users`). Verificado con 8 comprobaciones curl reales (reclamar propio
✅, robar+auto-verificar ajeno ❌, editar tras reclamar ✅, auto-verificarse
a uno mismo ❌, tercero sin reclamar ❌, admin verificando ✅) — todas con
el resultado esperado.

### 10.3 Qué se construyó

- **`src/lib/time.ts`**: `relativeEs(iso)`, formato relativo en español
  reutilizado en Home y Perfil.
- **`src/lib/useClaimable.ts`**: hook compartido reclamar → verificar para
  `bars`/`breweries` (misma forma de datos, mismas reglas) — evita
  duplicar la lógica en los dos paneles.
- **Home**: carrusel de `beers` recientes (expand brewery+style, ABV) +
  carrusel de `scans` recientes (expand bar, conteo de items agregado en
  cliente con el mismo patrón ya usado en Buscador — una sola lectura de
  `scan_items`, sin N+1).
- **Perfil**: estadísticas reales (nº de `style`/`brewery`/`bar` distintos
  agregados sobre los `scan_items` del usuario o invitado) + lista de sus
  escaneos.
- **Panel de bar/cervecera**: buscar → reclamar → (pendiente/verificado) →
  histórico (bar) o formulario de edición (cervecera), con `useClaimable`.
- **Panel de admin**: lista real de `bars`/`breweries` con
  `claimed_by != "" && verified = false`, botón real de verificar, y botón
  real a `POST /dictionary/refresh` del servicio OCR. "Duplicados
  pendientes de fusión" se deja como sección visible pero explícitamente
  sin datos (no hay mecanismo de detección real, y no se fabricó uno falso
  para rellenar el hueco).
- **`theme/index.ts`**: dos tokens nuevos — `mapPreviewBg` (color de la
  card de mini-mapa en Home, que ya estaba hardcodeado antes de esta
  sesión) y `onBrand` (texto oscuro sobre fondo ámbar, patrón que ya se
  repetía suelto en 8+ sitios del código previo — se promovió a token y se
  aplicó en los archivos tocados en esta sesión; los 8 sitios preexistentes
  fuera de este encargo quedan como están, no se tocaron).

### 10.4 Verificación

Sin simulador disponible en esta máquina (limitación ya conocida de
sesiones anteriores): no hay capturas de pantalla reales. En su lugar,
verificación equivalente y más estricta —
replicar EXACTAMENTE las consultas de cada pantalla contra el PocketBase
real y confirmar que devuelven datos que existen de verdad:

- Home: las 6 `beers` reales del catálogo aparecen en "Últimas
  descubiertas" (Ayinger Bräuweisse, Blat de Espiga, Simplex...); los 3
  `scans` reales aparecen en "Actividad cerca" con su conteo de items real
  (15/11/5 cervezas, verificado contra `scan_items` real).
- Perfil (invitado con `device_id` real que tiene 2 escaneos genuinos):
  stats calculados = 9 estilos, 7 cerveceras, 2 bares — verificado a mano
  contra los 26 `scan_items` reales de esos 2 escaneos.
- Flujo reclamar → pendiente → verificar probado de punta a punta con
  escrituras reales (no solo lectura): reclamar aparece en la cola de admin,
  verificar lo saca de la cola, y `useClaimable` recupera el registro ya
  verificado — con limpieza posterior de los datos de prueba.
- `npx tsc --noEmit`: limpio. Bundle de Metro exportado sin errores de
  import/resolución.
- `modulo-ocr/tests`: 57/57 siguen en verde (nada de este encargo tocó ese
  módulo).
- Grep de hex hardcodeados en los 7 archivos tocados: limpio tras mover
  `onBrand` y `mapPreviewBg` a `theme/index.ts`.

### 10.5 Pendiente explícito

- **Mapa**: fuera de este encargo, sigue exactamente como estaba.
- **"Duplicados pendientes de fusión"** en Panel de admin: sin mecanismo
  real, ver 10.3.
- Los 8 sitios preexistentes con `"#3D2A08"` suelto (auth.tsx,
  onboarding.tsx, scan-resultado.tsx, escanear.tsx, buscar.tsx,
  AbvPill.tsx) no se tocaron — ahora que `palette.onBrand` existe como
  token, sería un cambio mecánico pendiente para una pasada de limpieza
  aparte.
- Validación visual real en dispositivo/simulador sigue pendiente (mismo
  motivo de siempre: sin entorno disponible en esta máquina).

## 11. Guardarraíl completo de "reclamar" en bars/breweries (14-jul)

Cierre de sesión: `main` publicado a `origin` (commit `489af7f`, confirmado
idéntico local↔remoto). A continuación, endurecimiento del patrón
reclamar→verificar de §10.2.

### 11.1 Diagnóstico previo

Confirmado leyendo el schema real (no de memoria): `claimed_by`/`verified`
siguen llamándose así en ambas collections. El modelo de invitado
(`device_id`, campo de texto plano en `scans`/`scan_items`) es
estructuralmente independiente del sistema de auth de PocketBase — un
invitado nunca tiene sesión, así que `@request.auth.id` es siempre `""`
para él en el servidor. Conclusión: **"reclamar requiere cuenta
registrada" ya se cumplía de facto** antes de tocar nada (un invitado no
tiene forma de satisfacer `claimed_by = @request.auth.id` ni
`@request.body.claimed_by = @request.auth.id`); no hubo que ajustar nada
para ese criterio ni fue necesario preguntar.

### 11.2 Hueco real encontrado y cerrado

Las reglas de §10.2 ya cerraban: reasignación por un tercero (bloqueada),
auto-verificación (bloqueada), control total de admin (ya existía). Pero
**un dueño ya reclamado SÍ podía tocar `claimed_by` en la misma petición**
(reasignarlo a otro o vaciarlo) — esa rama solo exigía
`@request.body.verified:isset = false`, nunca protegió `claimed_by`. Se
cerró añadiendo `@request.body.claimed_by:isset = false` a las dos ramas
de "ya soy el dueño" (en `bars`, tanto la de `created_by` como la de
`claimed_by`; en `breweries`, la de `claimed_by`) — mismo patrón exacto ya
auditado para `role` en `users` (`@request.body.role:isset = false`).

Reglas resultantes:

```
breweries.updateRule:
@request.auth.role = 'admin' ||
(claimed_by = @request.auth.id && @request.body.verified:isset = false && @request.body.claimed_by:isset = false) ||
(claimed_by = '' && @request.body.claimed_by = @request.auth.id && @request.body.verified:isset = false)

bars.updateRule:
@request.auth.id != '' && (
  (created_by = @request.auth.id && @request.body.verified:isset = false && @request.body.claimed_by:isset = false) ||
  (claimed_by = @request.auth.id && @request.body.verified:isset = false && @request.body.claimed_by:isset = false) ||
  @request.auth.role = 'admin' ||
  (claimed_by = '' && @request.body.claimed_by = @request.auth.id && @request.body.verified:isset = false)
)
```

### 11.3 Verificación curl real (14-jul)

Auditoría de 12 llamadas reales contra el PocketBase vivo (usuarios de
prueba creados y borrados en la misma corrida):

| # | Acción | HTTP |
|---|---|---|
| 1/1b | Invitado sin login reclama bar/brewery | **404** ambos |
| 2/2b | userA logueado reclama bar/brewery sin dueño | **200** ambos |
| 3/3b | userB reclama el mismo bar/brewery, ya de userA | **404** ambos |
| 4/4b | userA (dueño) se auto-verifica | **404** ambos |
| 4c | userA (dueño) intenta liberar su propio `claimed_by` | **404** (hueco cerrado) |
| 4d | userA (dueño) intenta reasignar `claimed_by` a userB | **404** (hueco cerrado) |
| 4e | userA (dueño) edita `address` sin tocar claimed_by/verified | **200** |
| 5/5b | Admin verifica bar/brewery | **200** ambos |
| 5c | Admin reasigna `claimed_by` a otro usuario | **200** |
| 5d | Admin limpia (libera) un `claimed_by` | **200** |

Los 12 resultados coinciden exactamente con el diseño del Paso 2. Registros
de prueba restaurados a su estado original tras la verificación.
