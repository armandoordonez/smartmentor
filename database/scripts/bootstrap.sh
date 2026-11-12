#!/usr/bin/env bash
# Crea las bases de datos de SmartMentor (aplicación y Keycloak) si no existen (idempotente).
#
# Uso:
#   ./database/scripts/bootstrap.sh
#       Local: ejecuta dentro del contenedor smartmentor-postgres con las variables de .env.
#   ADMIN_DATABASE_URL="postgresql://admin:clave@host:5432/postgres" POSTGRES_DB=smartmentor \
#       ./database/scripts/bootstrap.sh
#       Base remota (Neon, etc.): usa un usuario administrador. ADMIN_DATABASE_URL puede ir en .env. Usa psql 15 o
#       superior si lo tienes y, si no, el de la imagen de PostgreSQL (Docker).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SQL_FILE="$ROOT_DIR/database/bootstrap/01-create-database.sql"

# Las variables ya definidas en el entorno tienen prioridad sobre las de .env
_DB_OVERRIDE="${POSTGRES_DB:-}"
ENV_FILE="${ENV_FILE:-$ROOT_DIR/.env}"
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ENV_FILE"
  set +a
fi
POSTGRES_DB="${_DB_OVERRIDE:-${POSTGRES_DB:-}}"

: "${POSTGRES_DB:?Define POSTGRES_DB (en .env o en el entorno)}"

if [[ -n "${ADMIN_DATABASE_URL:-}" ]]; then
  echo "Bootstrap de '$POSTGRES_DB' con ADMIN_DATABASE_URL (base remota)..."
  export POSTGRES_DB
  if [[ -z "${BOOTSTRAP_DOCKER_NETWORK:-}" ]] && command -v psql >/dev/null && [[ "$(psql --version | grep -oE '[0-9]+' | head -1)" -ge 15 ]]; then
    psql "$ADMIN_DATABASE_URL" -v ON_ERROR_STOP=1 -f "$SQL_FILE"
  else
    # Sin psql 15 o superior en esta máquina (Windows, macOS): se usa el de la imagen de PostgreSQL.
    # Las contraseñas pasan por variables de entorno del contenedor, no por la línea de comandos.
    command -v docker >/dev/null || { echo "Error: se necesita psql 15 o superior, o Docker" >&2; exit 1; }
    docker run --rm -i ${BOOTSTRAP_DOCKER_NETWORK:+--network "$BOOTSTRAP_DOCKER_NETWORK"} -e ADMIN_DATABASE_URL -e POSTGRES_DB \
        -e KEYCLOAK_DB_NAME -e KEYCLOAK_DB_USER -e KEYCLOAK_DB_PASSWORD \
        -e OWNER_DATABASE_USER -e OWNER_DATABASE_PASSWORD -e API_DATABASE_USER -e API_DATABASE_PASSWORD \
        -e AI_DATABASE_USER -e AI_DATABASE_PASSWORD -e METRICS_DATABASE_USER -e METRICS_DATABASE_PASSWORD \
        "${BOOTSTRAP_PSQL_IMAGE:-pgvector/pgvector:0.8.7-pg17-bookworm}" \
        sh -c 'psql "$ADMIN_DATABASE_URL" -v ON_ERROR_STOP=1 -f -' < "$SQL_FILE"
  fi
else
  : "${POSTGRES_USER:?Define POSTGRES_USER (en .env o en el entorno)}"
  echo "Bootstrap de '$POSTGRES_DB' en el contenedor smartmentor-postgres..."
  docker compose -f "$ROOT_DIR/docker-compose.yml" exec -T -e POSTGRES_DB="$POSTGRES_DB" \
      -e KEYCLOAK_DB_NAME -e KEYCLOAK_DB_USER -e KEYCLOAK_DB_PASSWORD \
      -e OWNER_DATABASE_USER -e OWNER_DATABASE_PASSWORD -e API_DATABASE_USER -e API_DATABASE_PASSWORD \
      -e AI_DATABASE_USER -e AI_DATABASE_PASSWORD -e METRICS_DATABASE_USER -e METRICS_DATABASE_PASSWORD postgres \
    psql -U "$POSTGRES_USER" -d postgres -v ON_ERROR_STOP=1 -f - < "$SQL_FILE"
fi
echo "Listo."
