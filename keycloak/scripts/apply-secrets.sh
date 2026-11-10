#!/usr/bin/env bash
# Aplica a un Keycloak YA importado los secretos y el correo que hoy están en .env (rotación).
#
# Por qué existe: el realm versionado usa marcadores ${VARIABLE} que Keycloak sustituye SOLO al importar,
# y la importación se omite si el realm ya existe. Si cambias OIDC_UI_CLIENT_SECRET, AI_CLIENT_SECRET o las
# SMTP_* en .env, el Keycloak existente no se entera: este script las aplica con kcadm.sh (dentro del
# contenedor, que ya tiene esas variables) sin imprimir ningún valor.
#
# Uso (después de editar .env y de recrear el contenedor para que reciba los valores nuevos):
#   docker compose up -d keycloak && keycloak/scripts/apply-secrets.sh
#
# Credenciales de la consola: por defecto las del arranque (KC_BOOTSTRAP_ADMIN_*). Si cambiaste la
# contraseña en la consola, exporta KCADM_USER y KCADM_PASSWORD antes de ejecutarlo.
# KC_EXEC permite apuntar a otro contenedor (por ejemplo, uno desechable de pruebas).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
REALM="${REALM:-smartmentor}"
# El comando se arma como arreglo para que las rutas con espacios (este repositorio puede estar en una
# carpeta con espacios) no se partan; KC_EXEC, si existe, se separa por espacios.
if [ -n "${KC_EXEC:-}" ]; then
  read -r -a KC_EXEC_CMD <<< "$KC_EXEC"
else
  KC_EXEC_CMD=(docker compose -f "$ROOT_DIR/docker-compose.yml" exec -T keycloak)
fi

"${KC_EXEC_CMD[@]}" env "TARGET_REALM=$REALM" \
  ${KCADM_USER:+"KCADM_USER=$KCADM_USER"} ${KCADM_PASSWORD:+"KCADM_PASSWORD=$KCADM_PASSWORD"} \
  bash -s <<'INNER'
set -euo pipefail
KCADM=/opt/keycloak/bin/kcadm.sh
CFG="$(mktemp)"
trap 'rm -f "$CFG"' EXIT
kc() { "$KCADM" "$@" --config "$CFG"; }   # la sesión de kcadm vive solo en un archivo temporal

require() {
  local name
  for name in "$@"; do
    if [ -z "${!name:-}" ]; then
      echo "Falta la variable $name en el contenedor de Keycloak (revisa .env y recrea el servicio)." >&2
      exit 1
    fi
  done
}
require OIDC_UI_CLIENT_SECRET AI_CLIENT_SECRET SMTP_HOST SMTP_PORT SMTP_FROM SMTP_STARTTLS

kc config credentials --server http://localhost:8080 --realm master \
  --user "${KCADM_USER:-$KC_BOOTSTRAP_ADMIN_USERNAME}" \
  --password "${KCADM_PASSWORD:-$KC_BOOTSTRAP_ADMIN_PASSWORD}" > /dev/null

client_id() {
  kc get clients -r "$TARGET_REALM" -q "clientId=$1" --fields id --format csv --noquotes
}

for pair in "smartmentor-ui:OIDC_UI_CLIENT_SECRET" "smartmentor-api-service:AI_CLIENT_SECRET"; do
  client="${pair%%:*}"
  variable="${pair##*:}"
  id="$(client_id "$client")"
  if [ -z "$id" ]; then
    echo "No existe el cliente $client en el realm $TARGET_REALM." >&2
    exit 1
  fi
  kc update "clients/$id" -r "$TARGET_REALM" -s "secret=${!variable}"
  echo "Secreto del cliente $client actualizado (desde $variable)."
done

kc update "realms/$TARGET_REALM" \
  -s "smtpServer.host=$SMTP_HOST" -s "smtpServer.port=$SMTP_PORT" \
  -s "smtpServer.from=$SMTP_FROM" -s "smtpServer.fromDisplayName=${SMTP_FROM_DISPLAY_NAME:-SmartMentor}" \
  -s "smtpServer.starttls=$SMTP_STARTTLS" -s "smtpServer.ssl=false" -s "smtpServer.auth=true" \
  -s "smtpServer.user=${SMTP_USER:-}" -s "smtpServer.password=${SMTP_PASSWORD:-}"
echo "Correo del realm $TARGET_REALM actualizado (desde SMTP_*)."
INNER
