#!/usr/bin/env bash
# Exporta las dos bases locales (aplicación y Keycloak) y las sube a una base PostgreSQL remota
# (Neon u otra), para compartir datos de prueba con el equipo. SOLO datos de prueba.
#
# Uso:
#   database/scripts/remote-sync.sh export            # solo genera los archivos en database/backups/remote_<fecha>/
#   database/scripts/remote-sync.sh import [CARPETA]  # sube una exportación (la más reciente si no das carpeta)
#   database/scripts/remote-sync.sh push              # export + import
#   database/scripts/remote-sync.sh import --replace --yes   # reemplaza lo que ya haya en la base remota
#
# Requisitos:
#   * Origen (export): el contenedor smartmentor-postgres en marcha (stack local arriba).
#   * Destino (import): ADMIN_DATABASE_URL en .env (URL del administrador de la base remota) y la base remota
#     ya preparada: database/scripts/bootstrap.sh crea las bases, los roles y pgvector. NO ejecutes Liquibase
#     antes: el volcado trae el esquema completo y la tabla databasechangelog, así que un `liquibase update`
#     posterior sigue funcionando.
#   * Docker (las herramientas pg_dump y pg_restore 17 corren en la imagen de PostgreSQL; no hace falta
#     instalar nada más, sirve igual en Linux, macOS y Windows con WSL2).
#
# Qué hace el import: restaura cada base con los dueños de siempre (OWNER_DATABASE_USER y KEYCLOAK_DB_USER) y
# conserva los permisos (GRANT) hacia los roles de la API, de IA y de métricas. Por eso esos roles deben
# existir en la base remota: define sus contraseñas en el .env antes de ejecutar bootstrap.sh.
# Se niega a escribir sobre una base remota que ya tiene tablas, salvo con --replace --yes.
#
# Los volcados de Keycloak traen hashes de contraseñas y llaves: son secretos, no los subas al repositorio
# (database/backups/ está ignorado por git). Las contraseñas de la URL se pasan por variables de entorno del
# contenedor, nunca por la línea de comandos.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BACKUP_ROOT="$ROOT_DIR/database/backups"
IMAGE="${BOOTSTRAP_PSQL_IMAGE:-pgvector/pgvector:0.8.7-pg17-bookworm}"
COMPOSE=(docker compose -f "$ROOT_DIR/docker-compose.yml")

die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
say() { printf '\n==> %s\n' "$*"; }

CMD="${1:-}"; [ $# -gt 0 ] && shift || true
REPLACE=0; YES=0; DIR_ARG=""
for arg in "$@"; do
  case "$arg" in
    --replace) REPLACE=1 ;;
    --yes) YES=1 ;;
    -h|--help) sed -n '2,29p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    -*) die "Argumento desconocido: $arg" ;;
    *) DIR_ARG="$arg" ;;
  esac
done
case "$CMD" in export|import|push) ;; -h|--help|"") sed -n '2,29p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;; *) die "Comando desconocido: $CMD (usa export, import o push)" ;; esac

ENV_FILE="${ENV_FILE:-$ROOT_DIR/.env}"
if [ -f "$ENV_FILE" ]; then
  set -a
  # shellcheck disable=SC1091
  . "$ENV_FILE"
  set +a
fi
: "${POSTGRES_DB:=smartmentor}"
APP_DB="$POSTGRES_DB"
KC_DB="${KEYCLOAK_DB_NAME:-keycloak}"
OWNER_ROLE="${OWNER_DATABASE_USER:-smartmentor_owner}"
KC_ROLE="${KEYCLOAK_DB_USER:-}"

command -v docker >/dev/null 2>&1 || die "Docker no está instalado o no está en el PATH."

# ---------------------------------------------------------------------------------------------
do_export() {
  : "${POSTGRES_USER:?Define POSTGRES_USER en .env}"
  docker ps --format '{{.Names}}' | grep -qx smartmentor-postgres \
    || die "El contenedor smartmentor-postgres no está en marcha. Levanta el stack local primero (scripts/local-up.sh)."
  local stamp out
  stamp="$(TZ=America/Bogota date +%Y%m%d_%H%M%S)"
  out="$BACKUP_ROOT/remote_$stamp"
  mkdir -p "$out"
  for db in "$APP_DB" "$KC_DB"; do
    say "Exportando '$db'"
    # --no-owner: el import fija el dueño con --role. --exclude-extension=vector: la extensión ya la crea el
    # bootstrap en la base remota (allí no es superusuario quien restaura).
    if ! "${COMPOSE[@]}" exec -T postgres pg_dump -U "$POSTGRES_USER" -d "$db" -Fc --no-owner \
        --exclude-extension=vector > "$out/$db.dump"; then
      rm -rf "$out"; die "No se pudo exportar '$db'."
    fi
    "${COMPOSE[@]}" exec -T postgres pg_restore --list < "$out/$db.dump" > /dev/null \
      || { rm -rf "$out"; die "El volcado de '$db' no es válido."; }
    echo "  ${out#"$ROOT_DIR"/}/$db.dump ($(du -h "$out/$db.dump" | cut -f1))"
  done
  EXPORT_DIR="$out"
  echo "Exportación lista: ${out#"$ROOT_DIR"/}"
}

# URL del administrador apuntando a otra base: cambia solo el nombre de la base, conserva los parámetros.
url_for_db() {  # url_for_db NOMBRE
  local base="${ADMIN_DATABASE_URL%%\?*}" query=""
  [[ "$ADMIN_DATABASE_URL" == *\?* ]] && query="?${ADMIN_DATABASE_URL#*\?}"
  printf '%s/%s%s' "${base%/*}" "$1" "$query"
}

remote_psql() {  # remote_psql URL SQL  → imprime el resultado sin cabeceras
  docker run --rm ${BOOTSTRAP_DOCKER_NETWORK:+--network "$BOOTSTRAP_DOCKER_NETWORK"} -e REMOTE_URL="$1" "$IMAGE" sh -c 'psql "$REMOTE_URL" -v ON_ERROR_STOP=1 -Atc "$0"' "$2"
}

do_import() {
  [ -n "${ADMIN_DATABASE_URL:-}" ] || die "Falta ADMIN_DATABASE_URL en .env (ver .env.example)."
  [ -n "$KC_ROLE" ] || die "Falta KEYCLOAK_DB_USER en .env."
  local dir="${DIR_ARG:-${EXPORT_DIR:-}}"
  if [ -z "$dir" ]; then
    dir="$(ls -d "$BACKUP_ROOT"/remote_* 2>/dev/null | sort | tail -1 || true)"
    [ -n "$dir" ] || die "No hay exportaciones en database/backups/. Ejecuta primero: $0 export"
  fi
  [[ "$dir" = /* ]] || dir="$ROOT_DIR/$dir"
  for db in "$APP_DB" "$KC_DB"; do [ -f "$dir/$db.dump" ] || die "Falta $dir/$db.dump"; done
  if [ "$REPLACE" = 1 ] && [ "$YES" != 1 ]; then
    die "--replace borra lo que haya en la base remota; confírmalo con --yes."
  fi

  say "Comprobando la conexión con la base remota"
  remote_psql "$(url_for_db "$APP_DB")" "select 'conectado a ' || current_database() || ' como ' || current_user" \
    || die "No se pudo conectar a la base '$APP_DB' remota. ¿Ejecutaste database/scripts/bootstrap.sh? ¿Es correcta ADMIN_DATABASE_URL?"
  remote_psql "$(url_for_db "$KC_DB")" "select 'conectado a ' || current_database()" \
    || die "No se pudo conectar a la base '$KC_DB' remota. ¿Ejecutaste database/scripts/bootstrap.sh?"

  for pair in "$APP_DB:$OWNER_ROLE" "$KC_DB:$KC_ROLE"; do
    db="${pair%%:*}"; role="${pair#*:}"
    tables="$(remote_psql "$(url_for_db "$db")" "select count(*) from information_schema.tables where table_schema = 'public'")"
    if [ "$tables" != "0" ] && [ "$REPLACE" != 1 ]; then
      die "La base remota '$db' ya tiene $tables tablas. Para reemplazarlas: $0 import --replace --yes"
    fi
    say "Subiendo '$db' (dueño: $role)"
    flags=(--no-owner "--role=$role" --single-transaction --exit-on-error)
    [ "$REPLACE" = 1 ] && flags+=(--clean --if-exists)
    docker run --rm -i ${BOOTSTRAP_DOCKER_NETWORK:+--network "$BOOTSTRAP_DOCKER_NETWORK"} -e REMOTE_URL="$(url_for_db "$db")" -v "$dir:/dump:ro" "$IMAGE" \
      sh -c 'pg_restore --dbname="$REMOTE_URL" "$@" /dump/'"$db"'.dump' sh "${flags[@]}" \
      || die "Falló la restauración de '$db'. Con --single-transaction no quedó nada a medias: corrige y repite. Pistas: los roles de la API, de IA y de métricas deben existir en la base remota (bootstrap.sh con sus contraseñas definidas)."
  done

  say "Verificando"
  remote_psql "$(url_for_db "$APP_DB")" "select 'tablas en $APP_DB: ' || count(*) from information_schema.tables where table_schema = 'public'"
  remote_psql "$(url_for_db "$APP_DB")" "select 'cambios de Liquibase aplicados: ' || count(*) from databasechangelog"
  remote_psql "$(url_for_db "$KC_DB")" "select 'usuarios en Keycloak: ' || count(*) from user_entity"
  echo
  echo "Listo. Para usar la base remota, cada integrante pone en su .env DATABASE_HOST, DATABASE_PORT,"
  echo "DATABASE_SSL=true y DATABASE_JDBC_PARAMS=?sslmode=require (ver database/README.md) y ejecuta scripts/local-up.sh."
}

EXPORT_DIR=""
case "$CMD" in
  export) do_export ;;
  import) do_import ;;
  push) do_export; do_import ;;
esac
