#!/usr/bin/env bash
# Restaura una copia de seguridad creada con backup.sh. REEMPLAZA los datos de la base de destino.
#
# Uso:
#   ./database/scripts/restore.sh database/backups/smartmentor_20261007_143000.dump
#   ./database/scripts/restore.sh database/backups/keycloak_20261007_143000.dump
#   ./database/scripts/restore.sh <archivo.dump> <base_destino>     # restaura en otra base
#   ./database/scripts/restore.sh <archivo.dump> --yes              # sin pedir confirmación
#
# La base de destino se deduce del nombre del archivo (<base>_YYYYMMDD_HHMMSS.dump) y se crea si no
# existe. Antes de restaurar la base de la aplicación o la de Keycloak, detén lo que la usa:
#   docker compose stop api        # para smartmentor
#   docker compose stop keycloak   # para keycloak
# y vuelve a levantarlo después (docker compose up -d). Si cambió el esquema, Liquibase lo ajusta.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COMPOSE=(docker compose -f "$ROOT_DIR/docker-compose.yml")

DUMP="${1:-}"
[[ -n "$DUMP" && -f "$DUMP" ]] || { sed -n '2,15p' "${BASH_SOURCE[0]}"; exit 1; }
shift
TARGET=""; ASSUME_YES=0
for arg in "$@"; do
  if [[ "$arg" == "--yes" ]]; then ASSUME_YES=1; else TARGET="$arg"; fi
done

if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env"
  set +a
fi
: "${POSTGRES_USER:?Define POSTGRES_USER (en .env o en el entorno)}"

if [[ -z "$TARGET" ]]; then
  TARGET="$(basename "$DUMP" | sed -E 's/_[0-9]{8}_[0-9]{6}\.dump$//')"
fi

# La base de Keycloak debe quedar a nombre de su rol, o Keycloak no podría usar las tablas.
ROLE_OPTION=()
OWNER_OPTION=()
if [[ -n "${KEYCLOAK_DB_NAME:-}" && "$TARGET" == "$KEYCLOAK_DB_NAME" ]]; then
  ROLE_OPTION=(--role="$KEYCLOAK_DB_USER")
  OWNER_OPTION=(OWNER "$KEYCLOAK_DB_USER")
fi

echo "Se restaurará: $DUMP"
echo "Base de destino: '$TARGET' (sus datos actuales se reemplazan)"
if [[ "$ASSUME_YES" -ne 1 ]]; then
  [[ -t 0 ]] || { echo "Error: sin terminal interactiva; usa --yes para confirmar" >&2; exit 1; }
  read -r -p "¿Continuar? Escribe 'si': " answer
  [[ "$answer" == "si" ]] || { echo "Cancelado."; exit 1; }
fi

"${COMPOSE[@]}" exec -T postgres psql -U "$POSTGRES_USER" -d postgres -v ON_ERROR_STOP=1 -qtA \
  -c "SELECT 'CREATE DATABASE \"$TARGET\" ${OWNER_OPTION[*]:-}' WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = '$TARGET')" \
  | { read -r create_sql || true; [[ -z "$create_sql" ]] || \
      "${COMPOSE[@]}" exec -T postgres psql -U "$POSTGRES_USER" -d postgres -v ON_ERROR_STOP=1 -qc "$create_sql"; }

"${COMPOSE[@]}" exec -T postgres pg_restore -U "$POSTGRES_USER" -d "$TARGET" \
  --clean --if-exists --no-owner "${ROLE_OPTION[@]}" < "$DUMP"
echo "Restauración terminada en '$TARGET'."
