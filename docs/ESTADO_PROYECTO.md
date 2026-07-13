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
nombres genéricos ambiguos sin cervecera clara NO se adivinan.

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
completar su ficha; paso 2: la cerveza concreta acotada a esa marca). Si hay
corroboración clara se publican `brewery`/`beer` con `source="auto-web"`,
descripción y notas de cata **parafraseadas** y `source_url` de trazabilidad;
si no, `no_match` y el item queda "sin detectar". La reconciliación con el
escaneo usa un `enrichment_id` (UUID) que cubre ambos órdenes de llegada.

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
  expo-location. `app-expo/`.
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
| Bloque 4 — Indicador visual de enriquecimiento en curso (estado `pending` + realtime de PocketBase + UI animada) | ⏳ Pendiente. Requiere escribir el estado `pending` al arrancar la tarea (hoy solo se escribe al terminar). |
| Desempate — Fase 0 (acotado por cervecera) | ✅ Hecha y verificada con la pizarra real |
| Desempate — Fase 1 (regex ABV con fallo seguro y tolerancia ±0,3-0,5, NUNCA igualdad exacta) | ⏳ Desbloqueada, sin implementar |
| Desempate — Fase 2 (persistir coordenadas de bloques en scan_items) | ⏳ Sin implementar |
| Desempate — Fase 3 (historial de bar) | ⏳ Desbloqueada técnicamente (el `bar_id` llega verificado a `/ocr` cuando la proximidad es CLARO; hook TODO en `main.py`), filtro sin implementar |
| Seguridad por rol (12 collections) | ✅ Cerrada y verificada con matriz curl real por rol (incluye fix de auto-escalado a admin y claim seguro por `device_id`) + rate limiting nativo activado |
| Pipeline híbrido PaddleOCR + Gemini Vision + métricas `ocr_metrics`/`GET /stats` | ✅ Hecho y verificado (foto real de 10 paneles, tokens y coste medidos) |

**Pendientes menores anotados por el camino:**

- **Endurecer el prompt de corroboración del paso 2 del enriquecimiento**: se
  detectó un falso positivo real ("Capricorn Feat Artesants" corroborada para
  el hint "Blat" de Espiga). La ficha errónea se eliminó, pero la causa raíz
  (el listón acepta resultados tangenciales) sigue sin arreglar.
- Alias de estilos para el matching (una pizarra que dice "NEIPA" no matchea
  la ficha "Hazy IPA"): mecanismo pendiente de diseñar.
- El juicio "corroborated" del LLM tiene varianza entre ejecuciones (a veces
  conservador de más). Aceptable por diseño, pero vigilarlo en las métricas.
- `docs/01-03` anteriores pueden contener detalles desactualizados respecto a
  este documento; este archivo manda.

## 5. Próximo paso concreto

**Bloque 4 — indicador visual de enriquecimiento en curso**: escribir el
estado `pending` al arrancar la tarea de enriquecimiento (hoy solo se escribe
al terminar), suscripción realtime de PocketBase en la app y UI animada en
`scan-resultado`.

Notas del Bloque 3 que quedan vivas:

- Las fichas del seed tienen `description` vacía a propósito (copyright);
  se completan vía enriquecimiento. Unas 8 tienen `source_url` apuntando al
  índice AECAI porque su web oficial estaba caída/bloqueada — candidatas a
  revisión manual del admin.
- El seed es re-ejecutable sin miedo (idempotente en nombre y dominio); si se
  quiere refrescar contra las webs, borrar antes
  `modulo-datos/seed/.breweries_es_checkpoint.json`.
