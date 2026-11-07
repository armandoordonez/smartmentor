#!/usr/bin/env bash
# Genera contraseñas y secretos aleatorios SOLO para las variables vacías de un .env existente.
#
#   * Idempotente: nunca pisa una variable que ya tiene valor; una segunda ejecución no cambia nada.
#   * Nunca imprime, registra ni pasa por la línea de comandos un valor generado: solo escribe en el archivo
#     (con permisos 600) y muestra los NOMBRES de las variables que rellenó o que faltan.
#   * Solo toca los secretos de SECRET_VARIABLES. Los nombres de usuario, el correo, los modelos y las claves de
#     proveedores externos (GEMINI_API_KEY, SMTP_PASSWORD...) los define quien despliega: se listan al final.
#
# Uso:
#   scripts/gen-secrets.sh                  # sobre ./.env
#   scripts/gen-secrets.sh --env-file RUTA  # sobre otro archivo
#   scripts/gen-secrets.sh --dry-run        # dice qué rellenaría, sin escribir
#
# Aviso: PostgreSQL ignora los cambios de POSTGRES_PASSWORD y de las contraseñas de los roles cuando
# database/data/postgres ya existe. Genera los secretos ANTES del primer arranque (ver database/README.md).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/.env"
DRY_RUN=0

while [ $# -gt 0 ]; do
  case "$1" in
    --env-file) ENV_FILE="${2:?Falta la ruta tras --env-file}"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) sed -n '2,17p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Argumento desconocido: $1" >&2; exit 2 ;;
  esac
done

# Secretos que genera el script: VARIABLE:longitud (caracteres alfanuméricos, seguros en .env, JDBC y URL).
SECRET_VARIABLES=(
  POSTGRES_PASSWORD:32
  API_DATABASE_PASSWORD:32
  AI_DATABASE_PASSWORD:32
  KEYCLOAK_DB_PASSWORD:32
  KEYCLOAK_ADMIN_PASSWORD:24
  APP_COOKIE_SECRET:48
  OIDC_UI_CLIENT_SECRET:40
  AI_CLIENT_SECRET:40
)
# Variables obligatorias que el script NO genera: las define el dueño.
MANUAL_VARIABLES=(
  POSTGRES_USER API_DATABASE_USER AI_DATABASE_USER KEYCLOAK_ADMIN KEYCLOAK_DB_USER SMTP_FROM
)

if [ ! -f "$ENV_FILE" ]; then
  echo "No existe $ENV_FILE. Créalo primero: cp .env.example .env" >&2
  exit 1
fi

# Valor de una variable en el archivo: vacío si no existe o está vacía (la salida no se imprime).
is_empty() {
  local line
  line="$(grep -E "^$1=" "$ENV_FILE" | tail -n 1 || true)"
  [ -z "$line" ] || [ -z "${line#*=}" ]
}

has_line() {
  grep -qE "^$1=" "$ENV_FILE"
}

random_string() {
  # Todos los consumidores de la tubería leen hasta el final (sin SIGPIPE); 96 bytes dan >= 120 caracteres.
  local raw
  raw="$(head -c 96 /dev/urandom | base64 -w0 | tr -d '+/=\n')"
  printf '%s' "${raw:0:$1}"
}

TMP_FILE="$(mktemp "$ENV_FILE.XXXXXX")"
trap 'rm -f "$TMP_FILE"' EXIT
chmod 600 "$TMP_FILE"
cp "$ENV_FILE" "$TMP_FILE"

filled=()
kept=()
for entry in "${SECRET_VARIABLES[@]}"; do
  name="${entry%%:*}"
  length="${entry##*:}"
  if ! is_empty "$name"; then
    kept+=("$name")
    continue
  fi
  filled+=("$name")
  [ "$DRY_RUN" -eq 1 ] && continue
  value="$(random_string "$length")"
  if has_line "$name"; then
    # El valor viaja por el entorno de awk, no por la línea de comandos (que otros usuarios pueden ver).
    NEW_SECRET="$value" awk -v key="$name" '
      BEGIN { prefix = key "=" }
      index($0, prefix) == 1 && substr($0, length(prefix) + 1) == "" { print prefix ENVIRON["NEW_SECRET"]; next }
      { print }
    ' "$TMP_FILE" > "$TMP_FILE.next"
    mv "$TMP_FILE.next" "$TMP_FILE"
  else
    printf '%s=%s\n' "$name" "$value" >> "$TMP_FILE"
  fi
  unset value
done

if [ "$DRY_RUN" -eq 0 ] && [ "${#filled[@]}" -gt 0 ]; then
  chmod 600 "$TMP_FILE"
  mv "$TMP_FILE" "$ENV_FILE"
  trap - EXIT
fi

echo "Archivo: $ENV_FILE"
if [ "${#filled[@]}" -gt 0 ]; then
  [ "$DRY_RUN" -eq 1 ] && echo "Rellenaría (simulacro):" || echo "Rellenadas con valores aleatorios:"
  printf '  %s\n' "${filled[@]}"
else
  echo "No había secretos vacíos: no se cambió nada."
fi
[ "${#kept[@]}" -gt 0 ] && echo "Ya tenían valor (sin tocar): ${#kept[@]}"

missing=()
for name in "${MANUAL_VARIABLES[@]}"; do
  is_empty "$name" && missing+=("$name")
done
if [ "${#missing[@]}" -gt 0 ]; then
  echo "Faltan por definir a mano (el compose no arrancará sin ellas):"
  printf '  %s\n' "${missing[@]}"
fi
