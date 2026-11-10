#!/usr/bin/env bash
# Reinicia el esquema de la aplicación: borra y recrea las bases de datos de la APLICACIÓN
# (POSTGRES_DB y POSTGRES_DB_test), ejecuta el bootstrap (base, roles y extensión) y aplica
# Liquibase (`update`). Sirve para pasar de v1 a v2.0.0 o para empezar de cero (ADR 0007).
#
# DESTRUCTIVO: se pierden todos los datos de esas bases. Haz antes ./database/scripts/backup.sh.
#
# Garantías:
#   * Nunca toca la base de Keycloak (KEYCLOAK_DB_NAME ni `keycloak`), ni `postgres` ni las plantillas.
#   * Nunca borra el directorio de datos database/data/postgres: solo ejecuta DROP/CREATE DATABASE.
#   * Valida el nombre de cada base: solo acepta POSTGRES_DB o POSTGRES_DB_test.
#   * Pide confirmación (escribir el nombre de la base) salvo con --yes.
#
# Uso:
#   ./database/scripts/reset-app-schema.sh              # pide confirmación
#   ./database/scripts/reset-app-schema.sh --yes        # sin confirmación (CI, scripts)
#   ./database/scripts/reset-app-schema.sh --db smartmentor_test --yes   # solo esa base
#
# Variables (de .env o del entorno; las del entorno tienen prioridad):
#   POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD   obligatorias
#   OWNER_/API_/AI_DATABASE_USER y _PASSWORD        roles de la aplicación (ver bootstrap)
#   SEED_ADMIN_EMAIL                                correo del administrador inicial (puede ir vacío)
#   SEED_INSTRUCTOR_EMAIL, SEED_LEARNER_EMAIL       correos de los usuarios de desarrollo (pueden ir vacíos)
#   RESET_PG_CONTAINER      contenedor de PostgreSQL ajeno al compose (pruebas aisladas). Si se define,
#                           también se usan RESET_DOCKER_NETWORK (red) y RESET_LIQUIBASE_IMAGE (imagen).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SQL_FILE="$ROOT_DIR/database/bootstrap/01-create-database.sql"
ASSUME_YES=0
ONLY_DB=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --yes|-y) ASSUME_YES=1; shift ;;
    --db) ONLY_DB="${2:-}"; shift 2 ;;
    -h|--help) sed -n '2,26p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) echo "Argumento desconocido: $1 (usa --help)" >&2; exit 2 ;;
  esac
done

ROLE_VARS=(OWNER_DATABASE_USER OWNER_DATABASE_PASSWORD API_DATABASE_USER API_DATABASE_PASSWORD
           AI_DATABASE_USER AI_DATABASE_PASSWORD METRICS_DATABASE_USER METRICS_DATABASE_PASSWORD KEYCLOAK_DB_NAME KEYCLOAK_DB_USER KEYCLOAK_DB_PASSWORD)

# Las variables ya definidas en el entorno tienen prioridad sobre las de .env
SAVED_ENV=()
for _v in POSTGRES_DB POSTGRES_USER POSTGRES_PASSWORD SEED_ADMIN_EMAIL SEED_INSTRUCTOR_EMAIL SEED_LEARNER_EMAIL "${ROLE_VARS[@]}"; do
  if [[ -n "${!_v+x}" ]]; then SAVED_ENV+=("$_v=${!_v}"); fi
done
if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env"
  set +a
  for _entry in "${SAVED_ENV[@]+"${SAVED_ENV[@]}"}"; do export "${_entry?}"; done
fi

: "${POSTGRES_DB:?Define POSTGRES_DB (en .env o en el entorno)}"
: "${POSTGRES_USER:?Define POSTGRES_USER (en .env o en el entorno)}"
: "${POSTGRES_PASSWORD:?Define POSTGRES_PASSWORD (en .env o en el entorno)}"

PRIMARY_DB="$POSTGRES_DB"
TEST_DB="${POSTGRES_DB}_test"
KEYCLOAK_NAME="${KEYCLOAK_DB_NAME:-keycloak}"

validate_db_name() {
  local name="$1"
  if [[ ! "$name" =~ ^[a-z][a-z0-9_]{0,62}$ ]]; then
    echo "Error: nombre de base no válido: '$name'" >&2; return 1
  fi
  case "$name" in
    keycloak|"$KEYCLOAK_NAME"|postgres|template0|template1)
      echo "Error: la base '$name' está protegida; este script no la toca nunca." >&2; return 1 ;;
  esac
  if [[ "$name" != "$PRIMARY_DB" && "$name" != "$TEST_DB" ]]; then
    echo "Error: '$name' no es ni '$PRIMARY_DB' ni '$TEST_DB'." >&2; return 1
  fi
}

if [[ -n "$ONLY_DB" ]]; then DATABASES=("$ONLY_DB"); else DATABASES=("$PRIMARY_DB" "$TEST_DB"); fi
for db in "${DATABASES[@]}"; do validate_db_name "$db" || exit 1; done

# --- Ejecución de psql y de Liquibase: compose por defecto, contenedor ajeno si RESET_PG_CONTAINER ---
psql_admin() { # $1 = base de datos objetivo del bootstrap; el resto de argumentos van a psql
  local target="$1"; shift
  local envargs=(-e "POSTGRES_DB=$target")
  local v
  for v in "${ROLE_VARS[@]}"; do [[ -n "${!v:-}" ]] && envargs+=(-e "$v"); done
  if [[ -n "${RESET_PG_CONTAINER:-}" ]]; then
    docker exec -i "${envargs[@]}" "$RESET_PG_CONTAINER" psql -U "$POSTGRES_USER" -d postgres -v ON_ERROR_STOP=1 "$@"
  else
    docker compose -f "$ROOT_DIR/docker-compose.yml" exec -T "${envargs[@]}" postgres \
      psql -U "$POSTGRES_USER" -d postgres -v ON_ERROR_STOP=1 "$@"
  fi
}

run_liquibase() { # $1 = base de datos
  local db="$1"
  if [[ -n "${RESET_PG_CONTAINER:-}" ]]; then
    : "${RESET_DOCKER_NETWORK:?Con RESET_PG_CONTAINER define también RESET_DOCKER_NETWORK}"
    : "${RESET_LIQUIBASE_IMAGE:?Con RESET_PG_CONTAINER define también RESET_LIQUIBASE_IMAGE}"
    local lb_user="${RESET_LIQUIBASE_USER:-$POSTGRES_USER}"
    local lb_password="${RESET_LIQUIBASE_PASSWORD:-$POSTGRES_PASSWORD}"
    docker run --rm --network "$RESET_DOCKER_NETWORK" \
      -v "$ROOT_DIR/database/liquibase/changelog:/liquibase/changelog:ro" \
      -e "LIQUIBASE_COMMAND_URL=jdbc:postgresql://$RESET_PG_CONTAINER:5432/$db" \
      -e "LIQUIBASE_COMMAND_USERNAME=$lb_user" -e "LIQUIBASE_COMMAND_PASSWORD=$lb_password" \
      -e LIQUIBASE_COMMAND_CHANGELOG_FILE=db.changelog-master.xml \
      -e "SEED_ADMIN_EMAIL=${SEED_ADMIN_EMAIL:-}" \
      -e "SEED_INSTRUCTOR_EMAIL=${SEED_INSTRUCTOR_EMAIL:-}" -e "SEED_LEARNER_EMAIL=${SEED_LEARNER_EMAIL:-}" \
      "$RESET_LIQUIBASE_IMAGE" update
  else
    docker compose -f "$ROOT_DIR/docker-compose.yml" run --rm \
      -e "LIQUIBASE_COMMAND_URL=jdbc:postgresql://postgres:5432/$db" \
      -e "SEED_ADMIN_EMAIL=${SEED_ADMIN_EMAIL:-}" \
      -e "SEED_INSTRUCTOR_EMAIL=${SEED_INSTRUCTOR_EMAIL:-}" -e "SEED_LEARNER_EMAIL=${SEED_LEARNER_EMAIL:-}" liquibase update
  fi
}

# --- Confirmación ---
echo "Se BORRARÁN y recrearán estas bases de datos (se pierden todos sus datos):"
printf '  - %s\n' "${DATABASES[@]}"
echo "No se tocarán la base '$KEYCLOAK_NAME' ni el directorio database/data/postgres."
if [[ "$ASSUME_YES" -ne 1 ]]; then
  answer=""
  read -r -p "Escribe el nombre de la base principal ('${DATABASES[0]}') para confirmar: " answer || true
  if [[ "$answer" != "${DATABASES[0]}" ]]; then echo "Cancelado."; exit 1; fi
fi

# --- Reinicio ---
for db in "${DATABASES[@]}"; do
  echo "==> Reiniciando '$db'..."
  # El nombre ya fue validado (solo minúsculas, dígitos y guion bajo): se puede citar con seguridad.
  psql_admin "$db" -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$db' AND pid <> pg_backend_pid()" > /dev/null
  psql_admin "$db" -c "DROP DATABASE IF EXISTS \"$db\" WITH (FORCE)"
  psql_admin "$db" -f - < "$SQL_FILE"
  run_liquibase "$db"
done
echo "Listo. Esquema aplicado en: ${DATABASES[*]}"
