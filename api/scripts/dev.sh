#!/usr/bin/env bash
# Herramientas de desarrollo de la API, ejecutadas en contenedores (no hace falta instalar Python ni uv).
#
# Uso (desde cualquier carpeta):
#   api/scripts/dev.sh lock              genera/actualiza uv.lock
#   api/scripts/dev.sh format            ordena imports y formatea el código con Ruff
#   api/scripts/dev.sh lint              ruff check + ruff format --check
#   api/scripts/dev.sh typecheck         mypy (modo estricto)
#   api/scripts/dev.sh prepare-test-db   crea y migra la base smartmentor_test (Liquibase)
#   api/scripts/dev.sh test [args]       pytest (usa smartmentor_test; ver prepare-test-db)
#   api/scripts/dev.sh all               lint + typecheck + test
#
# Requiere que el contenedor de PostgreSQL esté arriba (docker compose up -d postgres).
set -euo pipefail

API_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT_DIR="$(cd "$API_DIR/.." && pwd)"
UV_IMAGE="ghcr.io/astral-sh/uv:0.9.30-python3.12-bookworm"
TEST_DB="smartmentor_test"
NETWORK="smartmentor_default"

set -a
# shellcheck disable=SC1091
source "$ROOT_DIR/.env"
set +a

uv_run() {
  docker run --rm --user "$(id -u):$(id -g)" --network "$NETWORK" \
    -e HOME=/tmp -e UV_CACHE_DIR=/tmp/uv-cache -e UV_LINK_MODE=copy -e UV_PYTHON_DOWNLOADS=never \
    -e DATABASE_HOST=postgres -e DATABASE_PORT=5432 -e DATABASE_NAME="$TEST_DB" \
    -e DATABASE_USER="$POSTGRES_USER" -e DATABASE_PASSWORD="$POSTGRES_PASSWORD" \
    -e APP_ENV=test -e LOG_LEVEL=WARNING \
    -e OIDC_ISSUER_URL=http://keycloak.test/realms/smartmentor \
    -e OIDC_JWKS_URL=http://keycloak.test/realms/smartmentor/protocol/openid-connect/certs \
    -e OIDC_AUDIENCE=smartmentor-api \
    -v "$API_DIR:/app" -w /app "$UV_IMAGE" "$@"
}

prepare_test_db() {
  echo "Preparando la base $TEST_DB..."
  POSTGRES_DB="$TEST_DB" "$ROOT_DIR/database/scripts/bootstrap.sh"
  docker compose -f "$ROOT_DIR/docker-compose.yml" run --rm \
    -e LIQUIBASE_COMMAND_URL="jdbc:postgresql://postgres:5432/$TEST_DB" liquibase update
}

case "${1:-}" in
  lock)      uv_run uv lock ;;
  format)    uv_run sh -c "uv run ruff check --fix --select I . && uv run ruff format ." ;;
  lint)      uv_run sh -c "uv run ruff check . && uv run ruff format --check ." ;;
  typecheck) uv_run uv run mypy ;;
  prepare-test-db) prepare_test_db ;;
  test)      shift; uv_run uv run pytest "$@" ;;
  all)
    uv_run sh -c "uv run ruff check . && uv run ruff format --check . && uv run mypy"
    uv_run uv run pytest
    ;;
  *) sed -n '2,13p' "${BASH_SOURCE[0]}"; exit 1 ;;
esac
