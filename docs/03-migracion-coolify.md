# 03 — Migración a producción con Coolify

Principio: el MISMO docker-compose, otro `.env`. Nada de código cambia.

## Paso 0 — Prerequisitos

- VPS con Coolify instalado y un dominio apuntando al VPS.
- Tres subdominios en tu DNS (registros A hacia la IP del VPS):
  - `pb.tudominio.com` → PocketBase
  - `ocr.tudominio.com` → servicio OCR
  - `translate.tudominio.com` → LibreTranslate

## Paso 1 — Subir el repo

Sube el proyecto a un repo Git (GitHub/Gitea). Coolify desplegará desde ahí.

## Paso 2 — Crear el recurso en Coolify

1. **+ New → Resource → Docker Compose**.
2. Conecta el repositorio y selecciona `docker-compose.local.yml` como fichero
   compose (o duplica el fichero como `docker-compose.yml` si prefieres).
3. En **Environment Variables**, pega el contenido de tu `.env` de producción:

```
PB_ADMIN_EMAIL=admin@tudominio.com
PB_ADMIN_PASSWORD=contraseña-larga-y-única
POCKETBASE_URL_INTERNAL=http://pocketbase:8090
OCR_LANG=es
MATCH_THRESHOLD=78
LT_LOAD_ONLY=es,ca,en
LT_DISABLE_WEB_UI=true
```

## Paso 3 — Dominios y HTTPS

En cada servicio del compose, dentro de Coolify, asigna su dominio:
- pocketbase → `https://pb.tudominio.com` (puerto interno 8090)
- ocr → `https://ocr.tudominio.com` (puerto interno 8000)
- libretranslate → `https://translate.tudominio.com` (puerto interno 5000)

Coolify configura Traefik y emite los certificados Let's Encrypt
automáticamente. Tras el deploy, comprueba:
`https://pb.tudominio.com/_/` y `https://ocr.tudominio.com/health`.

> Recomendable: elimina los mapeos `ports:` del compose en producción (Coolify
> enruta por red interna; no hace falta exponer puertos al exterior).

## Paso 4 — Datos

1. Importa `pocketbase/pb_schema.json` en el Admin UI de producción.
2. Ejecuta el seed contra producción:
   ```bash
   python modulo-datos/seed_pocketbase.py --url https://pb.tudominio.com \
     --email admin@tudominio.com --password ...
   curl -X POST https://ocr.tudominio.com/dictionary/refresh
   ```
3. Configura OAuth Google/Apple en PocketBase Admin → Collections → users →
   Options → OAuth2 (necesitarás credenciales de Google Cloud / Apple Dev).

## Paso 5 — La app apunta a producción

En `app-expo/.env` (o en los env de EAS Build):

```
EXPO_PUBLIC_POCKETBASE_URL=https://pb.tudominio.com
EXPO_PUBLIC_OCR_URL=https://ocr.tudominio.com
EXPO_PUBLIC_TRANSLATE_URL=https://translate.tudominio.com
```

Eso es TODA la migración desde el punto de vista del código.

## Backup del SQLite de PocketBase

Los datos viven en el volumen `pb_data` (`/pb/pb_data` en el contenedor).

Opción A — backups nativos de PocketBase (la más simple):
Admin UI → Settings → Backups → programa backups diarios. Puedes conectar un
S3 compatible si algún día quieres copias fuera del VPS.

Opción B — cron en el VPS:
```bash
# /etc/cron.daily/beerwalk-backup
docker exec beerwalk-pocketbase /pb/pocketbase backup
docker cp beerwalk-pocketbase:/pb/pb_data/backups /var/backups/beerwalk/
```

Restaurar: Admin UI → Settings → Backups → Restore (o copiar el zip al
volumen y restaurar desde ahí). Prueba una restauración ANTES de necesitarla.

## Checklist final de producción

- [ ] Contraseña de superusuario fuerte y distinta a la local
- [ ] `LT_DISABLE_WEB_UI=true` (LibreTranslate solo como API)
- [ ] CORS del servicio OCR restringido (editar `allow_origins` en main.py)
- [ ] Reglas de las collections revisadas (las de MVP son permisivas)
- [ ] Backups programados y restauración probada
- [ ] Monitoriza el tamaño del volumen `ocr_models` y `pb_data`
