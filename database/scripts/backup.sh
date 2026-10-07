#!/usr/bin/env bash
# Copia de seguridad versionada por fecha de las bases de datos de SmartMentor:
# la de la aplicación (POSTGRES_DB) y la de Keycloak (KEYCLOAK_DB_NAME, con sus usuarios).
#
# Uso:
#   ./database/scripts/backup.sh
#   BACKUP_RETENTION_DAYS=30 ./database/scripts/backup.sh   # además borra copias de más de 30 días
#
# Resultado: database/backups/<base>_YYYYMMDD_HHMMSS.dump por cada base (formato personalizado de
# pg_dump, con la fecha y hora de Bogotá). Requiere el contenedor smartmentor-postgres en ejecución.
# Para recuperar una copia: ./database/scripts/restore.sh <archivo.dump>
# Los respaldos de Keycloak contienen hashes de contraseñas y llaves: trátalos como secretos.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BACKUP_DIR="$ROOT_DIR/database/backups"
COMPOSE=(docker compose -f "$ROOT_DIR/docker-compose.yml")

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
: "${POSTGRES_USER:?Define POSTGRES_USER (en .env o en el entorno)}"

DATABASES=("$POSTGRES_DB")
[[ -n "${KEYCLOAK_DB_NAME:-}" ]] && DATABASES+=("$KEYCLOAK_DB_NAME")

STAMP="$(TZ=America/Bogota date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

for DB in "${DATABASES[@]}"; do
  FILE="$BACKUP_DIR/${DB}_${STAMP}.dump"
  echo "Generando copia de '$DB'..."
  if ! "${COMPOSE[@]}" exec -T postgres \
      pg_dump -U "$POSTGRES_USER" -d "$DB" -Fc --no-owner > "$FILE"; then
    rm -f "$FILE"
    echo "Error: no se pudo generar la copia de '$DB'" >&2
    exit 1
  fi

  # Valida que el archivo sea legible por pg_restore
  if ! "${COMPOSE[@]}" exec -T postgres pg_restore --list < "$FILE" > /dev/null; then
    echo "Error: la copia generada no es válida: $FILE" >&2
    exit 1
  fi
  echo "Copia creada: ${FILE#"$ROOT_DIR"/} ($(du -h "$FILE" | cut -f1))"

  if [[ -n "${BACKUP_RETENTION_DAYS:-}" ]]; then
    find "$BACKUP_DIR" -name "${DB}_*.dump" -type f -mtime +"${BACKUP_RETENTION_DAYS}" -print -delete
  fi
done
