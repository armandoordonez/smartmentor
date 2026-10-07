#!/usr/bin/env bash
# Copia de seguridad versionada por fecha de la base de datos de SmartMentor.
#
# Uso:
#   ./database/scripts/backup.sh
#   BACKUP_RETENTION_DAYS=30 ./database/scripts/backup.sh   # además borra copias de más de 30 días
#
# Resultado: database/backups/<base>_YYYYMMDD_HHMMSS.dump (formato personalizado de pg_dump,
# con la fecha y hora de Bogotá). Requiere el contenedor smartmentor-postgres en ejecución.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BACKUP_DIR="$ROOT_DIR/database/backups"

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

STAMP="$(TZ=America/Bogota date +%Y%m%d_%H%M%S)"
FILE="$BACKUP_DIR/${POSTGRES_DB}_${STAMP}.dump"
mkdir -p "$BACKUP_DIR"

echo "Generando copia de '$POSTGRES_DB'..."
if ! docker compose -f "$ROOT_DIR/docker-compose.yml" exec -T postgres \
    pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc --no-owner > "$FILE"; then
  rm -f "$FILE"
  echo "Error: no se pudo generar la copia" >&2
  exit 1
fi

# Valida que el archivo sea legible por pg_restore
if ! docker compose -f "$ROOT_DIR/docker-compose.yml" exec -T postgres \
    pg_restore --list < "$FILE" > /dev/null; then
  echo "Error: la copia generada no es válida: $FILE" >&2
  exit 1
fi

echo "Copia creada: ${FILE#"$ROOT_DIR"/} ($(du -h "$FILE" | cut -f1))"

if [[ -n "${BACKUP_RETENTION_DAYS:-}" ]]; then
  echo "Borrando copias de más de ${BACKUP_RETENTION_DAYS} días..."
  find "$BACKUP_DIR" -name "${POSTGRES_DB}_*.dump" -type f -mtime +"${BACKUP_RETENTION_DAYS}" -print -delete
fi
