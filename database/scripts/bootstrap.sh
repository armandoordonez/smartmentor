#!/usr/bin/env bash
# Crea la base de datos de SmartMentor si no existe (idempotente).
#
# Uso:
#   ./database/scripts/bootstrap.sh
#       Local: ejecuta dentro del contenedor smartmentor-postgres con las variables de .env.
#   ADMIN_DATABASE_URL="postgresql://admin:clave@host:5432/postgres" POSTGRES_DB=smartmentor \
#       ./database/scripts/bootstrap.sh
#       Otros ambientes: usa un usuario administrador y requiere psql 15 o superior.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SQL_FILE="$ROOT_DIR/database/bootstrap/01-create-database.sql"

# Las variables ya definidas en el entorno tienen prioridad sobre las de .env
_DB_OVERRIDE="${POSTGRES_DB:-}"
if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env"
  set +a
fi
POSTGRES_DB="${_DB_OVERRIDE:-${POSTGRES_DB:-}}"

: "${POSTGRES_DB:?Define POSTGRES_DB (en .env o en el entorno)}"

if [[ -n "${ADMIN_DATABASE_URL:-}" ]]; then
  echo "Bootstrap de '$POSTGRES_DB' con ADMIN_DATABASE_URL..."
  command -v psql >/dev/null || { echo "Error: se necesita psql 15 o superior" >&2; exit 1; }
  POSTGRES_DB="$POSTGRES_DB" psql "$ADMIN_DATABASE_URL" -v ON_ERROR_STOP=1 -f "$SQL_FILE"
else
  : "${POSTGRES_USER:?Define POSTGRES_USER (en .env o en el entorno)}"
  echo "Bootstrap de '$POSTGRES_DB' en el contenedor smartmentor-postgres..."
  docker compose -f "$ROOT_DIR/docker-compose.yml" exec -T -e POSTGRES_DB="$POSTGRES_DB" postgres \
    psql -U "$POSTGRES_USER" -d postgres -v ON_ERROR_STOP=1 -f - < "$SQL_FILE"
fi
echo "Listo."
