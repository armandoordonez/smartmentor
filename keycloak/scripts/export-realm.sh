#!/usr/bin/env bash
# Exporta el realm smartmentor (configuración y usuarios) a keycloak/realm/smartmentor-realm.json.
# Es el archivo que Keycloak importa solo cuando el realm no existe (docker compose up en un PC nuevo).
#
# Úsalo después de cambiar la configuración en la consola (clientes, mappers, roles, usuarios) para
# que el cambio viaje con el repositorio.
#
# ATENCIÓN: el archivo incluye datos sensibles (client secrets, llaves privadas de firma, hashes de
# contraseñas). Está permitido mientras sean datos de prueba; con datos reales, no se versiona.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
REALM="${1:-smartmentor}"
OUT_DIR="$ROOT_DIR/keycloak/realm"
COMPOSE=(docker compose -f "$ROOT_DIR/docker-compose.yml")

mkdir -p "$OUT_DIR"
echo "Deteniendo Keycloak para exportar con consistencia..."
"${COMPOSE[@]}" stop keycloak
trap '"${COMPOSE[@]}" up -d keycloak' EXIT

# export no admite el modo --import-realm; se ejecuta con el mismo servicio y base de datos.
"${COMPOSE[@]}" run --rm --no-deps keycloak export \
  --realm "$REALM" --users same_file --file "/opt/keycloak/data/import/$REALM-realm.json"
echo "Exportado: keycloak/realm/$REALM-realm.json"
