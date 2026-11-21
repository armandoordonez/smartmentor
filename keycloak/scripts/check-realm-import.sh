#!/usr/bin/env bash
# Importa keycloak/realm/*.json en un Keycloak DESECHABLE (H2, puerto libre, valores de prueba) y comprueba el
# resultado con verify-realm.py. No toca el Keycloak ni el .env de nadie: el contenedor se elimina al terminar.
#
# Uso:  keycloak/scripts/check-realm-import.sh [--functional]
#   --functional  además comprueba el login (OTP por rol) y la pantalla de registro con usuarios de prueba.
# Variables opcionales: KEYCLOAK_IMAGE (por defecto la del compose), CHECK_PORT (por defecto, uno libre).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
IMAGE="${KEYCLOAK_IMAGE:-$(sed -n 's|^ *image: \(quay.io/keycloak/keycloak:[^ ]*\)$|\1|p' "$ROOT_DIR/docker-compose.yml" | head -n 1)}"
PORT="${CHECK_PORT:-$(python3 -I -c 'import socket; s = socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1]); s.close()')}"
NAME="sm-realm-check-$$"
ADMIN_USER="check-admin"
ADMIN_PASSWORD="$(head -c 24 /dev/urandom | base64 -w0 | tr -d '+/=\n')"   # solo vive en este proceso

cleanup() { docker rm -f "$NAME" > /dev/null 2>&1 || true; }
trap cleanup EXIT

echo "Keycloak desechable: $IMAGE en 127.0.0.1:$PORT"
# Valores de prueba para los marcadores del realm; ninguno es un secreto real.
docker run -d --name "$NAME" -p "127.0.0.1:$PORT:8080" \
  -e KC_BOOTSTRAP_ADMIN_USERNAME="$ADMIN_USER" -e KC_BOOTSTRAP_ADMIN_PASSWORD="$ADMIN_PASSWORD" \
  -e KC_HOSTNAME="http://localhost:$PORT" -e KC_HOSTNAME_BACKCHANNEL_DYNAMIC=true \
  -e OIDC_UI_CLIENT_SECRET=test-only-not-a-secret-ui -e AI_CLIENT_SECRET=test-only-not-a-secret-svc \
  -e SMTP_HOST=smtp.test.invalid -e SMTP_PORT=587 -e SMTP_STARTTLS=true -e SMTP_USER=test-user \
  -e SMTP_PASSWORD=test-only-not-a-secret-smtp -e SMTP_FROM=test@test.invalid \
  -e SMTP_FROM_DISPLAY_NAME=SmartMentor \
  -v "$ROOT_DIR/keycloak/realm:/opt/keycloak/data/import:ro" \
  "$IMAGE" start-dev --import-realm > /dev/null

echo "Esperando a que importe el realm..."
for _ in $(seq 1 90); do
  if curl -fs -o /dev/null "http://localhost:$PORT/realms/smartmentor"; then break; fi
  if [ "$(docker inspect -f '{{.State.Running}}' "$NAME")" != "true" ]; then
    docker logs "$NAME" 2>&1 | tail -n 20 >&2
    echo "Keycloak se detuvo al importar el realm." >&2
    exit 1
  fi
  sleep 2
done
curl -fs -o /dev/null "http://localhost:$PORT/realms/smartmentor" || { docker logs "$NAME" 2>&1 | tail -n 20 >&2; exit 1; }
docker logs "$NAME" 2>&1 | grep -E "Realm 'smartmentor' imported" || { echo "No se importó el realm." >&2; exit 1; }
if docker logs "$NAME" 2>&1 | grep -E ' ERROR '; then
  echo "Hubo errores en el registro de Keycloak." >&2
  exit 1
fi

python3 -I "$ROOT_DIR/keycloak/scripts/verify-realm.py" "http://localhost:$PORT" "$ADMIN_USER" "$ADMIN_PASSWORD" "$@"
