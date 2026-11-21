#!/usr/bin/env bash
# Baja las bases de Neon (aplicación y Keycloak) a archivos y las sube a la base local, BARRIENDO antes
# la base local actual. Es el camino inverso de remote-sync.sh (que sube lo local a Neon).
#
# Uso:
#   database/scripts/neon-to-local.sh pull                 # solo respalda Neon en database/backups/neon_<fecha>/
#   database/scripts/neon-to-local.sh restore [CARPETA]    # barre la base local y sube un respaldo de Neon
#                                                          # (el más reciente si no das carpeta)
#   database/scripts/neon-to-local.sh sync                 # pull + restore
#   database/scripts/neon-to-local.sh restore --yes        # sin pedir confirmación
#
# Requisitos:
#   * Contenedor smartmentor-postgres en marcha (docker compose up -d postgres). Sus herramientas
#     pg_dump y pg_restore 17 son las que se usan, así que no hace falta instalar nada más.
#   * .env con DATABASE_HOST/DATABASE_PORT de Neon (conexión directa, sin -pooler) y las contraseñas de
#     OWNER_DATABASE_* y KEYCLOAK_DB_*. Para `pull`, DATABASE_HOST debe apuntar a Neon, no a `postgres`.
#
# Qué hace restore, en orden:
#   1. Copia de seguridad de la base local actual con backup.sh (database/backups/).
#   2. Detiene api, ai, ai-worker y keycloak (si no, siguen conectados a lo que se borra).
#   3. BORRA las bases locales de la aplicación y de Keycloak (DROP DATABASE ... WITH (FORCE)).
#      No toca `postgres`, las plantillas ni `smartmentor_test`.
#   4. Las recrea con bootstrap.sh (base, roles y pgvector) y restaura cada volcado con los dueños de siempre
#      (OWNER_DATABASE_USER y KEYCLOAK_DB_USER), conservando los permisos hacia los roles de API, IA y métricas.
#   5. Verifica y muestra cuántos cambios de Liquibase y usuarios quedaron.
# No levanta de nuevo los servicios: hazlo tú (docker compose up -d) cuando apuntes el .env a la base local
# (DATABASE_HOST=postgres, DATABASE_SSL=false, DATABASE_JDBC_PARAMS vacío y KC_DB_URL local; ver database/README.md).
#
# Los volcados de Keycloak traen hashes de contraseñas y llaves: son secretos, no los subas al repositorio
# (database/backups/ está ignorado por git). Las contraseñas se pasan por variables de entorno del
# contenedor, nunca por la línea de comandos.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BACKUP_ROOT="$ROOT_DIR/database/backups"
COMPOSE=(docker compose -f "$ROOT_DIR/docker-compose.yml")

die() { echo "Error: $*" >&2; exit 1; }
say() { printf '\n== %s\n' "$*"; }
usage() { sed -n '2,13p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; }

CMD="${1:-}"
[[ -n "$CMD" ]] && shift
YES=0
DIR_ARG=""
for arg in "$@"; do
  case "$arg" in
    --yes) YES=1 ;;
    -h|--help) usage; exit 0 ;;
    -*) die "Argumento desconocido: $arg" ;;
    *) DIR_ARG="$arg" ;;
  esac
done
case "$CMD" in
  pull|restore|sync) ;;
  -h|--help|"") usage; exit 0 ;;
  *) die "Comando desconocido: $CMD (usa pull, restore o sync)" ;;
esac

ENV_FILE="${ENV_FILE:-$ROOT_DIR/.env}"
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ENV_FILE"
  set +a
fi
: "${POSTGRES_USER:?Define POSTGRES_USER en .env}"
APP_DB="${POSTGRES_DB:-smartmentor}"
KC_DB="${KEYCLOAK_DB_NAME:-keycloak}"
OWNER_ROLE="${OWNER_DATABASE_USER:-smartmentor_owner}"
KC_ROLE="${KEYCLOAK_DB_USER:-}"

command -v docker >/dev/null 2>&1 || die "Docker no está instalado o no está en el PATH."
docker ps --format '{{.Names}}' | grep -qx smartmentor-postgres \
  || die "El contenedor smartmentor-postgres no está en marcha. Levántalo con: docker compose up -d postgres"

# ---------------------------------------------------------------------------------------------
do_pull() {
  : "${DATABASE_HOST:?Define DATABASE_HOST (el host de Neon) en .env}"
  [[ "$DATABASE_HOST" != "postgres" && "$DATABASE_HOST" != "localhost" ]] \
    || die "DATABASE_HOST apunta a la base local ($DATABASE_HOST). Para bajar de Neon pon su host en .env."
  : "${OWNER_DATABASE_PASSWORD:?Define OWNER_DATABASE_PASSWORD en .env}"
  : "${KEYCLOAK_DB_PASSWORD:?Define KEYCLOAK_DB_PASSWORD en .env}"
  [[ -n "$KC_ROLE" ]] || die "Falta KEYCLOAK_DB_USER en .env."
  local stamp out db role pwvar remote_db
  stamp="$(TZ=America/Bogota date +%Y%m%d_%H%M%S)"
  out="$BACKUP_ROOT/neon_$stamp"
  mkdir -p "$out"
  chmod 700 "$out"
  for spec in "$APP_DB:${DATABASE_NAME:-$APP_DB}:$OWNER_ROLE:OWNER_DATABASE_PASSWORD" \
              "$KC_DB:$KC_DB:$KC_ROLE:KEYCLOAK_DB_PASSWORD"; do
    IFS=: read -r db remote_db role pwvar <<< "$spec"
    say "Respaldando '$remote_db' de Neon"
    # Nombre <base>_<fecha>.dump: es el que entiende restore.sh. --no-owner: el restore fija el dueño con --role.
    # --exclude-extension=vector: la extensión la crea bootstrap.sh con superusuario.
    if ! PGPASSWORD="${!pwvar}" "${COMPOSE[@]}" exec -T -e PGPASSWORD -e PGSSLMODE=require -e PGCONNECT_TIMEOUT=30 postgres \
        pg_dump -h "$DATABASE_HOST" -p "${DATABASE_PORT:-5432}" -U "$role" -d "$remote_db" -Fc --no-owner \
        --exclude-extension=vector > "$out/${db}_${stamp}.dump"; then
      rm -rf "$out"
      die "No se pudo respaldar '$remote_db'. ¿Está Neon dentro de su cuota? ¿Son correctos el host y la contraseña del rol $role?"
    fi
    "${COMPOSE[@]}" exec -T postgres pg_restore --list < "$out/${db}_${stamp}.dump" > /dev/null \
      || { rm -rf "$out"; die "El volcado de '$db' no es válido."; }
    echo "  ${out#"$ROOT_DIR"/}/${db}_${stamp}.dump ($(du -h "$out/${db}_${stamp}.dump" | cut -f1))"
  done
  PULL_DIR="$out"
  echo "Respaldo de Neon listo: ${out#"$ROOT_DIR"/}"
}

lpsql() { "${COMPOSE[@]}" exec -T postgres psql -U "$POSTGRES_USER" -v ON_ERROR_STOP=1 -qtA "$@"; }

do_restore() {
  [[ -n "$KC_ROLE" ]] || die "Falta KEYCLOAK_DB_USER en .env."
  local dir="${DIR_ARG:-${PULL_DIR:-}}"
  if [[ -z "$dir" ]]; then
    dir="$(find "$BACKUP_ROOT" -maxdepth 1 -type d -name 'neon_*' 2>/dev/null | sort | tail -1 || true)"
    [[ -n "$dir" ]] || die "No hay respaldos de Neon en database/backups/. Ejecuta primero: $0 pull"
  fi
  [[ "$dir" = /* ]] || dir="$ROOT_DIR/$dir"
  local app_dump kc_dump
  app_dump="$(ls "$dir/${APP_DB}"_*.dump 2>/dev/null | sort | tail -1 || true)"
  kc_dump="$(ls "$dir/${KC_DB}"_*.dump 2>/dev/null | sort | tail -1 || true)"
  [[ -f "$app_dump" && -f "$kc_dump" ]] || die "Faltan los volcados de '$APP_DB' y '$KC_DB' en $dir"

  echo "Se subirán a la base local:"
  echo "  ${app_dump#"$ROOT_DIR"/}"
  echo "  ${kc_dump#"$ROOT_DIR"/}"
  echo "Se BORRARÁN las bases locales '$APP_DB' y '$KC_DB' (antes se hace una copia con backup.sh)."
  if [[ "$YES" -ne 1 ]]; then
    [[ -t 0 ]] || die "sin terminal interactiva; usa --yes para confirmar"
    read -r -p "¿Continuar? Escribe 'si': " answer
    [[ "$answer" == "si" ]] || { echo "Cancelado."; exit 1; }
  fi

  say "1/5 Copia de seguridad de la base local actual"
  "$ROOT_DIR/database/scripts/backup.sh"

  say "2/5 Deteniendo los servicios que usan la base"
  "${COMPOSE[@]}" stop api ai ai-worker keycloak >/dev/null 2>&1 || true

  say "3/5 Barriendo las bases locales"
  for db in "$APP_DB" "$KC_DB"; do
    case "$db" in postgres|template0|template1|smartmentor_test) die "Me niego a borrar '$db'." ;; esac
    lpsql -d postgres -c "DROP DATABASE IF EXISTS \"$db\" WITH (FORCE)"
    echo "  borrada '$db'"
  done

  say "4/5 Recreando bases, roles y pgvector, y restaurando"
  # bootstrap.sh actúa sobre una base REMOTA si ve ADMIN_DATABASE_URL: aquí debe actuar solo sobre la local,
  # así que se le pasa un .env sin esa variable.
  local boot_env
  boot_env="$(mktemp)"
  if [[ -f "$ENV_FILE" ]]; then grep -v '^ADMIN_DATABASE_URL=' "$ENV_FILE" > "$boot_env"; fi
  ADMIN_DATABASE_URL="" ENV_FILE="$boot_env" "$ROOT_DIR/database/scripts/bootstrap.sh" || { rm -f "$boot_env"; die "Falló bootstrap.sh en la base local."; }
  rm -f "$boot_env"
  for pair in "$app_dump:$APP_DB:$OWNER_ROLE" "$kc_dump:$KC_DB:$KC_ROLE"; do
    IFS=: read -r dump db role <<< "$pair"
    echo "  restaurando '$db' (dueño: $role)"
    # Se omiten los «DEFAULT ACL» del volcado: son permisos por defecto de los roles internos de Neon
    # (cloud_admin, neon_superuser) que no existen en local. Los GRANT hacia los roles de la API, IA y métricas se conservan.
    "${COMPOSE[@]}" exec -T postgres pg_restore -l < "$dump" | grep -v 'DEFAULT ACL' \
      | "${COMPOSE[@]}" exec -T postgres sh -c 'cat > /tmp/restore.list'
    "${COMPOSE[@]}" exec -T postgres pg_restore -U "$POSTGRES_USER" -d "$db" -L /tmp/restore.list \
      --no-owner "--role=$role" --single-transaction --exit-on-error < "$dump" \
      || die "Falló la restauración de '$db'. Con --single-transaction no quedó nada a medias. La copia previa está en database/backups/."
  done

  say "5/5 Verificando"
  echo "  tablas en $APP_DB: $(lpsql -d "$APP_DB" -c "select count(*) from information_schema.tables where table_schema = 'public'")"
  echo "  cambios de Liquibase aplicados: $(lpsql -d "$APP_DB" -c "select count(*) from databasechangelog")"
  echo "  usuarios en Keycloak: $(lpsql -d "$KC_DB" -c "select count(*) from user_entity")"
  echo
  echo "Listo. Servicios detenidos: apunta el .env a la base local y ejecuta docker compose up -d."
}

PULL_DIR=""
case "$CMD" in
  pull) do_pull ;;
  restore) do_restore ;;
  sync) do_pull; do_restore ;;
esac
