#!/usr/bin/env bash
# Exporta la configuración del realm smartmentor a keycloak/realm/smartmentor-realm.json.
# Es el archivo que Keycloak importa solo cuando el realm no existe (docker compose up en un PC nuevo).
#
# Úsalo después de cambiar la configuración en la consola (clientes, mappers, roles) para que el
# cambio viaje con el repositorio.
#
# El export crudo se escribe en una carpeta temporal fuera del repositorio y se pasa por
# sanitize-realm.py: el archivo versionado NO lleva usuarios, client secrets ni llaves de firma.
# Los usuarios se crean en la consola de cada PC y los secretos los genera Keycloak al importar.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
REALM="${1:-smartmentor}"
OUT_DIR="$ROOT_DIR/keycloak/realm"
COMPOSE=(docker compose -f "$ROOT_DIR/docker-compose.yml")

mkdir -p "$OUT_DIR"
RAW_DIR="$(mktemp -d)"
chmod 777 "$RAW_DIR"
echo "Deteniendo Keycloak para exportar con consistencia..."
"${COMPOSE[@]}" stop keycloak
trap 'rm -rf "$RAW_DIR"; "${COMPOSE[@]}" up -d keycloak' EXIT

# export no admite el modo --import-realm; se ejecuta con el mismo servicio y base de datos.
# El export crudo va a un volumen temporal y no a keycloak/realm, que es la carpeta que se importa.
"${COMPOSE[@]}" run --rm --no-deps -v "$RAW_DIR:/export" keycloak export \
  --realm "$REALM" --users same_file --file "/export/$REALM-realm.json"
python3 -I "$ROOT_DIR/keycloak/scripts/sanitize-realm.py" "$RAW_DIR/$REALM-realm.json" "$OUT_DIR/$REALM-realm.json"
echo "Exportado sin secretos: keycloak/realm/$REALM-realm.json"
