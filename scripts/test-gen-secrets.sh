#!/usr/bin/env bash
# Prueba de scripts/gen-secrets.sh sobre una copia de .env.example en una carpeta temporal.
# Comprueba: no pisa un valor existente, rellena todos los secretos vacíos con la longitud pedida, la segunda
# ejecución no cambia el archivo, el archivo queda con permisos 600 y la salida nunca contiene un valor generado.
# Uso: scripts/test-gen-secrets.sh        (lo ejecuta la CI)
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
fail() { echo "FALLA: $1" >&2; exit 1; }

cp "$ROOT_DIR/.env.example" "$WORK/.env"
sed -i 's/^POSTGRES_PASSWORD=$/POSTGRES_PASSWORD=valor-existente-no-se-toca/' "$WORK/.env"

"$ROOT_DIR/scripts/gen-secrets.sh" --env-file "$WORK/.env" --dry-run > /dev/null
cmp -s "$ROOT_DIR/.env.example" "$WORK/.env" && fail "el simulacro no debía cambiar nada pero el archivo coincide con el ejemplo"
grep -q '^POSTGRES_PASSWORD=valor-existente-no-se-toca$' "$WORK/.env" || fail "--dry-run modificó el archivo"
grep -q '^API_DATABASE_PASSWORD=$' "$WORK/.env" || fail "--dry-run escribió un secreto"

"$ROOT_DIR/scripts/gen-secrets.sh" --env-file "$WORK/.env" > "$WORK/salida.txt"
grep -q '^POSTGRES_PASSWORD=valor-existente-no-se-toca$' "$WORK/.env" || fail "pisó un valor existente"
for pair in OWNER_DATABASE_PASSWORD:32 API_DATABASE_PASSWORD:32 AI_DATABASE_PASSWORD:32 KEYCLOAK_DB_PASSWORD:32 KEYCLOAK_ADMIN_PASSWORD:24 \
            APP_COOKIE_SECRET:48 OIDC_UI_CLIENT_SECRET:40 AI_CLIENT_SECRET:40; do
  name="${pair%%:*}"; length="${pair##*:}"
  value="$(grep -E "^$name=" "$WORK/.env" | cut -d= -f2-)"
  [ "${#value}" -eq "$length" ] || fail "$name no tiene $length caracteres"
  [[ "$value" =~ ^[A-Za-z0-9]+$ ]] || fail "$name tiene caracteres no alfanuméricos"
  grep -qF -- "$value" "$WORK/salida.txt" && fail "la salida imprimió el valor de $name"
done
grep -q '^POSTGRES_USER=$' "$WORK/.env" || fail "rellenó un nombre de usuario, que debe definir el dueño"
[ "$(stat -c '%a' "$WORK/.env")" = "600" ] || fail "el archivo no quedó con permisos 600"

before="$(sha256sum "$WORK/.env")"
"$ROOT_DIR/scripts/gen-secrets.sh" --env-file "$WORK/.env" > /dev/null
[ "$before" = "$(sha256sum "$WORK/.env")" ] || fail "la segunda ejecución cambió el archivo (no es idempotente)"

echo "gen-secrets.sh: correcto"
