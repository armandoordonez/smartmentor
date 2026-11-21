#!/usr/bin/env bash
# Pide a Keycloak un access token con usuario y contraseña, sin navegador. SOLO DESARROLLO.
#
# Usa el cliente smartmentor-dev-tools (flujo "password"), que no debe existir en producción.
# Imprime únicamente el token en la salida estándar, listo para usarlo en cada petición:
#
#   curl -H "Authorization: Bearer $(api/scripts/token.sh usuario@correo.com)" localhost:8020/api/v1/me
#
# Uso:
#   api/scripts/token.sh <usuario> [contraseña]
#   api/scripts/token.sh --claims <usuario> [contraseña]    # muestra el contenido del token (iss, aud, exp...)
#
# La contraseña se toma, en este orden, de: el segundo argumento, la variable TOKEN_PASSWORD, o se
# pide sin eco en la terminal. Evita escribirla en la línea de comandos: queda en el historial.
#
# Variables opcionales: KEYCLOAK_URL (por defecto http://localhost:$KEYCLOAK_PORT de .env, o 8180),
# KEYCLOAK_REALM (smartmentor) y KEYCLOAK_CLIENT_ID (smartmentor-dev-tools).
set -euo pipefail

SHOW_CLAIMS=0
if [[ "${1:-}" == "--claims" ]]; then SHOW_CLAIMS=1; shift; fi
USERNAME="${1:-}"
[[ -n "$USERNAME" ]] || { sed -n '2,19p' "${BASH_SOURCE[0]}" >&2; exit 1; }
PASSWORD="${2:-${TOKEN_PASSWORD:-}}"
if [[ -z "$PASSWORD" ]]; then
  [[ -t 0 ]] || { echo "Error: sin contraseña (usa el segundo argumento o TOKEN_PASSWORD)" >&2; exit 1; }
  read -r -s -p "Contraseña de $USERNAME: " PASSWORD >&2
  echo >&2
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
if [[ -z "${KEYCLOAK_URL:-}" && -f "$ROOT_DIR/.env" ]]; then
  PORT="$(sed -n 's/^KEYCLOAK_PORT=//p' "$ROOT_DIR/.env" | tail -1)"
fi
KEYCLOAK_URL="${KEYCLOAK_URL:-http://localhost:${PORT:-8180}}"
REALM="${KEYCLOAK_REALM:-smartmentor}"
CLIENT_ID="${KEYCLOAK_CLIENT_ID:-smartmentor-dev-tools}"

RESPONSE="$(curl -sS --fail-with-body \
  --data-urlencode "grant_type=password" \
  --data-urlencode "client_id=$CLIENT_ID" \
  --data-urlencode "username=$USERNAME" \
  --data-urlencode "password=$PASSWORD" \
  --data-urlencode "scope=openid profile email" \
  "$KEYCLOAK_URL/realms/$REALM/protocol/openid-connect/token" 2>&1)" || {
  DETAIL="$(printf '%s' "$RESPONSE" | sed -n 's/.*"error_description":"\([^"]*\)".*/\1/p')"
  echo "Error: no se pudo obtener el token${DETAIL:+ ($DETAIL)}." >&2
  [[ -n "$DETAIL" ]] || echo "$RESPONSE" >&2
  exit 1
}

TOKEN="$(printf '%s' "$RESPONSE" | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p')"
[[ -n "$TOKEN" ]] || { echo "Error: la respuesta de Keycloak no trae access_token" >&2; exit 1; }

if [[ "$SHOW_CLAIMS" -eq 1 ]]; then
  python3 - "$TOKEN" <<'PY'
import base64, json, sys
payload = sys.argv[1].split(".")[1]
payload += "=" * (-len(payload) % 4)
claims = json.loads(base64.urlsafe_b64decode(payload))
for key in ("iss", "aud", "azp", "sub", "email", "email_verified", "name", "iat", "exp"):
    if key in claims:
        print(f"{key}: {claims[key]}")
print(f"vence en: {claims['exp'] - claims['iat']} segundos")
PY
else
  printf '%s\n' "$TOKEN"
fi
