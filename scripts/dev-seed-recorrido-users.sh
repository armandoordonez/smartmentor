#!/usr/bin/env bash
# Crea ocho usuarios de DESARROLLO para los recorridos de prueba manuales (A3b, intentos del quiz,
# intentos del examen final y evaluación humana) y para los experimentos R-005 (prefijo experimento_):
#
#   Aprendiz A3b             aprendiz    SEED_A3B_LEARNER_EMAIL
#   Aprendiz Intentos quiz   aprendiz    SEED_QUIZ_ATTEMPTS_LEARNER_EMAIL
#   Aprendiz Intentos final  aprendiz    SEED_FINAL_ATTEMPTS_LEARNER_EMAIL
#   Instructor Evaluador     instructor  SEED_EVALUATOR_INSTRUCTOR_EMAIL
#   experimento_estudiante   aprendiz    SEED_EXPERIMENT_LEARNER_EMAIL
#   experimento_instructor   instructor  SEED_EXPERIMENT_INSTRUCTOR_EMAIL
#   experimento_evaluador_1  instructor  SEED_EXPERIMENT_EVALUATOR_1_EMAIL
#   experimento_evaluador_2  instructor  SEED_EXPERIMENT_EVALUATOR_2_EMAIL
#
# Por qué existe: para iniciar sesión la persona debe existir en Keycloak y en la base de la
# aplicación, con el MISMO correo verificado. En su primer ingreso la API enlaza ambos por el `sub`
# del token y por el correo verificado (users.identity_subject).
#
# Qué hace (idempotente: lo que ya existe no se toca, ni la contraseña ni los roles):
#   1. Keycloak (kcadm dentro del contenedor, como keycloak/scripts/seed-dev-users.sh): crea el
#      usuario con el correo como nombre de usuario, correo verificado, el rol de realm que
#      corresponde y la contraseña SEED_USERS_PASSWORD, sin acciones requeridas ni OTP.
#   2. Base de la aplicación, SOLO por la API como administrador (SEED_ADMIN_EMAIL, cliente
#      smartmentor-dev-tools, patrón de api/scripts/token.sh): POST /users y PUT /users/{id}/roles.
#      No escribe SQL.
#   3. Verifica con GET: pide el token de cada usuario y consulta /me (rol y enlace). Con
#      --no-verify se omite este paso (GET /me enlaza el `sub` en el primer acceso a la API).
# No imprime contraseñas ni tokens.
#
# SOLO DESARROLLO. Necesita el stack encendido (scripts/local-up.sh --with-admin) y, para el token
# del administrador, REQUIRE_SECOND_FACTOR=false (el flujo de usuario y contraseña no lleva OTP).
#
# Uso:
#   scripts/dev-seed-recorrido-users.sh               # crea lo que falte y verifica
#   scripts/dev-seed-recorrido-users.sh --no-verify   # crea lo que falte, sin consultar /me
#
# Variables opcionales: ENV_FILE (ruta del .env; por defecto el de la raíz del repositorio o, desde
# un worktree, el del repositorio principal), API_URL (por defecto http://localhost:$API_PORT/api/v1),
# KC_EXEC (comando alterno para Keycloak) y KCADM_USER/KCADM_PASSWORD (consola de Keycloak).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REALM="${REALM:-smartmentor}"
VERIFY=1
for arg in "$@"; do
  case "$arg" in
    --no-verify) VERIFY=0 ;;
    -h|--help) sed -n '2,38p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Argumento desconocido: $arg" >&2; exit 2 ;;
  esac
done

die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

# .env: el de la raíz; en un worktree git no lo trae (está ignorado), así que se busca en el
# repositorio principal.
if [ -z "${ENV_FILE:-}" ]; then
  ENV_FILE="$ROOT_DIR/.env"
  if [ ! -f "$ENV_FILE" ]; then
    COMMON_DIR="$(git -C "$ROOT_DIR" rev-parse --path-format=absolute --git-common-dir 2>/dev/null || true)"
    [ -z "$COMMON_DIR" ] || ENV_FILE="$(dirname "$COMMON_DIR")/.env"
  fi
fi
[ -f "$ENV_FILE" ] || die "No se encontró el .env ($ENV_FILE). Créalo desde .env.example o exporta ENV_FILE."
set -a
# shellcheck disable=SC1090
. "$ENV_FILE"
set +a

[ -n "${SEED_USERS_PASSWORD:-}" ] || die "Falta SEED_USERS_PASSWORD en el .env (la genera scripts/gen-secrets.sh)."
ADMIN_EMAIL="${SEED_ADMIN_EMAIL:-}"
[ -n "$ADMIN_EMAIL" ] || die "Falta SEED_ADMIN_EMAIL en el .env: hace falta un administrador para crear usuarios por la API."
API_URL="${API_URL:-http://localhost:${API_PORT:-8020}/api/v1}"
command -v curl >/dev/null || die "Falta curl."
command -v jq >/dev/null || die "Falta jq."

# Cada entrada: «CORREO|ROL|NOMBRE COMPLETO|NOMBRE|APELLIDO». Los correos salen de las variables.
USERS=()
# El valor se pasa como "${VARIABLE:-}" (no por nombre) para que scripts/check-env-coherence.py vea que
# el script usa cada variable documentada en .env.example.
add_user() {  # add_user VARIABLE VALOR ROL NOMBRE_COMPLETO NOMBRE APELLIDO
  local var="$1" email
  email="$(printf '%s' "$2" | tr '[:upper:]' '[:lower:]')"
  [ -n "$email" ] || die "Falta $var en el .env (valor de ejemplo en .env.example)."
  [[ "$email" =~ ^[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]+$ ]] || die "Correo no válido en $var."
  USERS+=("$email|$3|$4|$5|$6")
}
add_user SEED_A3B_LEARNER_EMAIL "${SEED_A3B_LEARNER_EMAIL:-}" learner "Aprendiz A3b" Aprendiz A3b
add_user SEED_QUIZ_ATTEMPTS_LEARNER_EMAIL "${SEED_QUIZ_ATTEMPTS_LEARNER_EMAIL:-}" learner "Aprendiz Intentos quiz" Aprendiz "Intentos quiz"
add_user SEED_FINAL_ATTEMPTS_LEARNER_EMAIL "${SEED_FINAL_ATTEMPTS_LEARNER_EMAIL:-}" learner "Aprendiz Intentos final" Aprendiz "Intentos final"
add_user SEED_EVALUATOR_INSTRUCTOR_EMAIL "${SEED_EVALUATOR_INSTRUCTOR_EMAIL:-}" instructor "Instructor Evaluador" Instructor Evaluador
add_user SEED_EXPERIMENT_LEARNER_EMAIL "${SEED_EXPERIMENT_LEARNER_EMAIL:-}" learner experimento_estudiante experimento estudiante
add_user SEED_EXPERIMENT_INSTRUCTOR_EMAIL "${SEED_EXPERIMENT_INSTRUCTOR_EMAIL:-}" instructor experimento_instructor experimento instructor
add_user SEED_EXPERIMENT_EVALUATOR_1_EMAIL "${SEED_EXPERIMENT_EVALUATOR_1_EMAIL:-}" instructor experimento_evaluador_1 experimento evaluador_1
add_user SEED_EXPERIMENT_EVALUATOR_2_EMAIL "${SEED_EXPERIMENT_EVALUATOR_2_EMAIL:-}" instructor experimento_evaluador_2 experimento evaluador_2

# 1) Keycloak
echo "1/3 Keycloak (realm $REALM):"
if [ -n "${KC_EXEC:-}" ]; then
  read -r -a KC_EXEC_CMD <<< "$KC_EXEC"
else
  KC_EXEC_CMD=(docker compose -f "$ROOT_DIR/docker-compose.yml" exec -T keycloak)
fi
# La lista viaja por el entorno (una línea por usuario); la contraseña, también por el entorno.
KC_USERS="$(printf '%s\n' "${USERS[@]}")"
"${KC_EXEC_CMD[@]}" env "TARGET_REALM=$REALM" "KC_USERS=$KC_USERS" "SEED_USERS_PASSWORD=$SEED_USERS_PASSWORD" \
  ${KCADM_USER:+"KCADM_USER=$KCADM_USER"} ${KCADM_PASSWORD:+"KCADM_PASSWORD=$KCADM_PASSWORD"} \
  bash -s <<'INNER'
set -euo pipefail
KCADM=/opt/keycloak/bin/kcadm.sh
CFG="$(mktemp)"
trap 'rm -f "$CFG"' EXIT
kc() { "$KCADM" "$@" --config "$CFG"; }   # la sesión de kcadm vive solo en un archivo temporal

kc config credentials --server http://localhost:8080 --realm master \
  --user "${KCADM_USER:-$KC_BOOTSTRAP_ADMIN_USERNAME}" \
  --password "${KCADM_PASSWORD:-$KC_BOOTSTRAP_ADMIN_PASSWORD}" >/dev/null

while IFS='|' read -r email role _full first last; do
  [ -n "$email" ] || continue
  found="$(kc get users -r "$TARGET_REALM" -q "email=$email" -q exact=true --fields id | grep -c '"id"' || true)"
  if [ "$found" != "0" ]; then
    echo "  ya existe: $email ($role) — sin cambios"
    continue
  fi
  kc create users -r "$TARGET_REALM" \
    -s "username=$email" -s "email=$email" -s emailVerified=true -s enabled=true \
    -s "firstName=$first" -s "lastName=$last" >/dev/null
  if ! kc set-password -r "$TARGET_REALM" --username "$email" --new-password "$SEED_USERS_PASSWORD" 2>/dev/null; then
    echo "  ERROR: Keycloak rechazó la contraseña de SEED_USERS_PASSWORD (política del realm): $email" >&2
    exit 1
  fi
  kc add-roles -r "$TARGET_REALM" --uusername "$email" --rolename "$role" >/dev/null
  echo "  creado: $email ($role)"
done <<< "$KC_USERS"
INNER

# 2) Base de la aplicación, por la API como administrador
echo "2/3 Base de la aplicación (API como $ADMIN_EMAIL):"
get_token() {  # get_token CORREO -> token por la salida estándar (api/scripts/token.sh)
  TOKEN_PASSWORD="$SEED_USERS_PASSWORD" "$ROOT_DIR/api/scripts/token.sh" "$1"
}
ADMIN_TOKEN="$(get_token "$ADMIN_EMAIL")" \
  || die "No se obtuvo el token del administrador. ¿Está encendido Keycloak y existe $ADMIN_EMAIL (local-up.sh --with-admin)?"

BODY_FILE="$(mktemp)"
trap 'rm -f "$BODY_FILE"' EXIT
api() {  # api TOKEN MÉTODO RUTA [JSON] -> imprime el código HTTP; el cuerpo queda en BODY_FILE
  local token="$1" method="$2" path="$3" data=()
  [ $# -ge 4 ] && data=(-H "Content-Type: application/json" --data "$4")
  curl -sS -o "$BODY_FILE" -w '%{http_code}' -X "$method" \
    -H @<(printf 'Authorization: Bearer %s\n' "$token") "${data[@]}" "$API_URL$path"
}

# Imprime el id del usuario con ese correo en la base de la aplicación (nada si no existe).
find_user_id() {
  local email="$1" offset=0 code total found
  while :; do
    code="$(api "$ADMIN_TOKEN" GET "/users?limit=100&offset=$offset")" || die "La API no responde en $API_URL."
    [ "$code" = "200" ] || die "GET /users respondió $code: $(cat "$BODY_FILE")"
    found="$(jq -r --arg e "$email" '[.items[] | select((.email | ascii_downcase) == $e) | .id][0] // empty' "$BODY_FILE")"
    if [ -n "$found" ]; then
      printf '%s\n' "$found"
      return 0
    fi
    total="$(jq -r '.total' "$BODY_FILE")"
    offset=$((offset + 100))
    [ "$offset" -lt "$total" ] || return 0
  done
}

for entry in "${USERS[@]}"; do
  IFS='|' read -r email role full _first _last <<< "$entry"
  existing="$(find_user_id "$email")"
  if [ -n "$existing" ]; then
    echo "  ya existe: $email (usuario $existing) — sin cambios"
    continue
  fi
  code="$(api "$ADMIN_TOKEN" POST /users "$(jq -nc --arg e "$email" --arg n "$full" '{email: $e, full_name: $n}')")"
  [ "$code" = "201" ] || die "POST /users respondió $code para $email: $(cat "$BODY_FILE")"
  uid="$(jq -r '.id' "$BODY_FILE")"
  code="$(api "$ADMIN_TOKEN" PUT "/users/$uid/roles" "$(jq -nc --arg r "$role" '{roles: [$r]}')")"
  [ "$code" = "200" ] || die "PUT /users/$uid/roles respondió $code para $email: $(cat "$BODY_FILE")"
  echo "  creado: $email (usuario $uid, rol $role)"
done

# 3) Verificación (solo GET)
if [ "$VERIFY" = "1" ]; then
  echo "3/3 Verificación (GET /me con el token de cada usuario):"
  STATUS=0
  for entry in "${USERS[@]}"; do
    IFS='|' read -r email role _full _first _last <<< "$entry"
    if ! token="$(get_token "$email" 2>/dev/null)"; then
      echo "  FALLA: no se obtuvo token de $email (Keycloak)" >&2
      STATUS=1
      continue
    fi
    code="$(api "$token" GET /me)" || die "La API no responde en $API_URL."
    if [ "$code" = "200" ] && jq -e --arg r "$role" '.roles | index($r)' "$BODY_FILE" >/dev/null; then
      echo "  ok: $email — «$(jq -r '.full_name' "$BODY_FILE")», roles $(jq -c '.roles' "$BODY_FILE")"
    else
      echo "  FALLA: $email — GET /me respondió $code" >&2
      STATUS=1
    fi
  done
  [ "$STATUS" = "0" ] || exit 1
else
  echo "3/3 Verificación omitida (--no-verify)."
fi

echo
echo "Listo. Inicia sesión con cada correo y la contraseña SEED_USERS_PASSWORD del .env (mejor en una ventana de incógnito)."
