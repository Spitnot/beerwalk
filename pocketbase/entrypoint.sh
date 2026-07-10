#!/bin/sh
# Crea el superusuario la primera vez (idempotente: si ya existe, falla en
# silencio y seguimos) y arranca PocketBase escuchando en todas las interfaces.
if [ -n "$PB_ADMIN_EMAIL" ] && [ -n "$PB_ADMIN_PASSWORD" ]; then
  /pb/pocketbase superuser upsert "$PB_ADMIN_EMAIL" "$PB_ADMIN_PASSWORD" || true
fi
exec /pb/pocketbase serve --http=0.0.0.0:8090
