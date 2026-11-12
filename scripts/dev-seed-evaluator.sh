#!/usr/bin/env bash
# Crea un segundo instructor de DESARROLLO y lo asigna como evaluador de un curso (DEF-24), para probar
# la calificación humana de respuestas cortas y la anotación de preguntas en local.
#
# Por qué existe: solo califica un instructor asignado como evaluador del curso que NO sea su dueño, y
# lo asigna un admin con POST /courses/{id}/evaluators (todavía no hay pantalla). El instructor de
# prueba (SEED_INSTRUCTOR_EMAIL) suele ser el dueño de los cursos, así que hace falta otro.
#
# Qué hace (idempotente: puedes repetirlo; lo que ya existe no se toca):
#   1. Keycloak: crea el usuario con correo verificado, rol de realm instructor y la contraseña
#      SEED_USERS_PASSWORD del .env.
#   2. Base de la aplicación: crea su fila en users con el rol instructor en user_roles. Hace falta
#      porque el primer ingreso crea a los usuarios nuevos solo como aprendices, y para autorizar
#      cuenta el rol de la base, no el del token. En el primer ingreso la API enlaza ambos por el correo.
#   3. Pide un token del admin (SEED_ADMIN_EMAIL, cliente smartmentor-dev-tools, api/scripts/token.sh)
#      y asigna al evaluador con POST /courses/{id}/evaluators. Así la API aplica sus reglas
#      (no puede ser el dueño, debe ser instructor activo). Si ya era evaluador, lo deja igual.
# No imprime contraseñas ni tokens.
#
# SOLO DESARROLLO. Necesita el stack encendido (scripts/local-up.sh --with-admin) y, para el token del
# admin, REQUIRE_SECOND_FACTOR=false (el flujo de usuario y contraseña no lleva OTP).
#
# Uso:
#   scripts/dev-seed-evaluator.sh                     # lista los cursos para escoger el id
#   scripts/dev-seed-evaluator.sh --course 3          # crea el evaluador y lo asigna al curso 3
#   scripts/dev-seed-evaluator.sh --course 3 --email otro.evaluador@yopmail.com
#
# Variables opcionales: EVALUATOR_EMAIL, ADMIN_EMAIL (por defecto SEED_ADMIN_EMAIL), API_URL
# (por defecto http://localhost:$API_PORT/api/v1), KC_EXEC y PSQL_EXEC (comandos alternativos para
# Keycloak y psql, por ejemplo contenedores desechables de pruebas).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REALM="${REALM:-smartmentor}"
COURSE_ID=""
EMAIL_ARG=""
while [ $# -gt 0 ]; do
  case "$1" in
    --course) COURSE_ID="${2:-}"; shift 2 ;;
    --email) EMAIL_ARG="${2:-}"; shift 2 ;;
    -h|--help) sed -n '2,31p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Argumento desconocido: $1" >&2; exit 2 ;;
  esac
done

die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

# Variables del .env (se lee como script de shell, igual que keycloak/scripts/seed-dev-users.sh).
if [ -f "$ROOT_DIR/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  . "$ROOT_DIR/.env"
  set +a
fi

EMAIL="${EMAIL_ARG:-${EVALUATOR_EMAIL:-evaluador.smartmentor@yopmail.com}}"
EMAIL="$(printf '%s' "$EMAIL" | tr '[:upper:]' '[:lower:]')"
ADMIN_EMAIL="${ADMIN_EMAIL:-${SEED_ADMIN_EMAIL:-}}"
API_URL="${API_URL:-http://localhost:${API_PORT:-8020}/api/v1}"

case "$EMAIL" in
  *@*.*) ;;
  *) die "Correo no válido: $EMAIL" ;;
esac
[[ "$EMAIL" =~ ^[a-z0-9._%+-]+@[a-z0-9.-]+$ ]] || die "Correo no válido: $EMAIL"
if [ -n "$COURSE_ID" ] && ! [[ "$COURSE_ID" =~ ^[1-9][0-9]*$ ]]; then
  die "--course debe ser el id numérico del curso (por ejemplo --course 3)"
fi
[ -n "${SEED_USERS_PASSWORD:-}" ] || die "Falta SEED_USERS_PASSWORD en .env."

# psql dentro del contenedor de postgres (o PSQL_EXEC, que se separa por espacios).
if [ -n "${PSQL_EXEC:-}" ]; then
  read -r -a PSQL_CMD <<< "$PSQL_EXEC"
else
  [ -n "${POSTGRES_USER:-}" ] || die "Falta POSTGRES_USER en .env."
  PSQL_CMD=(docker compose -f "$ROOT_DIR/docker-compose.yml" exec -T postgres
            psql -U "$POSTGRES_USER" -d "${POSTGRES_DB:-smartmentor}")
fi
sql() { "${PSQL_CMD[@]}" -v ON_ERROR_STOP=1 -qAtX "$@"; }

# Sin --course: muestra los cursos y termina.
if [ -z "$COURSE_ID" ]; then
  echo "Cursos (id | estado | nombre | dueño):"
  sql -F ' | ' -c "SELECT c.id, c.status, c.name, u.email FROM courses c JOIN users u ON u.id = c.owner_user_id ORDER BY c.id" \
    | sed 's/^/  /'
  echo
  echo "Escoge uno publicado que NO sea del evaluador y ejecuta:"
  echo "  scripts/dev-seed-evaluator.sh --course <id>"
  exit 0
fi

[ -n "$ADMIN_EMAIL" ] || die "Falta SEED_ADMIN_EMAIL en .env (o exporta ADMIN_EMAIL): hace falta un admin para asignar."

COURSE_ROW="$(sql -F '|' -c "SELECT c.name, c.status, lower(u.email) FROM courses c JOIN users u ON u.id = c.owner_user_id WHERE c.id = $COURSE_ID")"
[ -n "$COURSE_ROW" ] || die "No existe el curso $COURSE_ID. Ejecuta el script sin --course para ver la lista."
IFS='|' read -r COURSE_NAME COURSE_STATUS OWNER_EMAIL <<< "$COURSE_ROW"
[ "$OWNER_EMAIL" != "$EMAIL" ] || die "$EMAIL es el dueño del curso $COURSE_ID: el dueño no puede ser evaluador (DEF-24)."
echo "Curso $COURSE_ID: $COURSE_NAME ($COURSE_STATUS), dueño $OWNER_EMAIL"

# 1) Keycloak
echo "1/3 Keycloak (realm $REALM):"
if [ -n "${KC_EXEC:-}" ]; then
  read -r -a KC_EXEC_CMD <<< "$KC_EXEC"
else
  KC_EXEC_CMD=(docker compose -f "$ROOT_DIR/docker-compose.yml" exec -T keycloak)
fi
"${KC_EXEC_CMD[@]}" env "TARGET_REALM=$REALM" "EVALUATOR_EMAIL=$EMAIL" "SEED_USERS_PASSWORD=$SEED_USERS_PASSWORD" \
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

found="$(kc get users -r "$TARGET_REALM" -q "email=$EVALUATOR_EMAIL" -q exact=true --fields id | grep -c '"id"' || true)"
if [ "$found" = "0" ]; then
  kc create users -r "$TARGET_REALM" \
    -s "username=$EVALUATOR_EMAIL" -s "email=$EVALUATOR_EMAIL" -s emailVerified=true -s enabled=true \
    -s "firstName=Evaluador" -s "lastName=Desarrollo" >/dev/null
  if ! kc set-password -r "$TARGET_REALM" --username "$EVALUATOR_EMAIL" --new-password "$SEED_USERS_PASSWORD" 2>/dev/null; then
    echo "  ERROR: Keycloak rechazó la contraseña de SEED_USERS_PASSWORD (política del realm): $EVALUATOR_EMAIL" >&2
    exit 1
  fi
  echo "  creado: $EVALUATOR_EMAIL"
else
  echo "  ya existe: $EVALUATOR_EMAIL (sin cambiar la contraseña)"
fi
# add-roles no falla si el rol ya está asignado.
kc add-roles -r "$TARGET_REALM" --uusername "$EVALUATOR_EMAIL" --rolename instructor >/dev/null
echo "  rol de realm instructor: listo"
INNER

# 2) Base de la aplicación
echo "2/3 Base de la aplicación:"
USER_ID="$(sql -v "email=$EMAIL" <<'SQL'
INSERT INTO users (full_name, email) VALUES ('Evaluador', :'email') ON CONFLICT DO NOTHING;
UPDATE users SET active = true WHERE lower(email) = :'email' AND NOT active;
INSERT INTO user_roles (user_id, role_id)
SELECT u.id, r.id FROM users u, roles r WHERE lower(u.email) = :'email' AND r.code = 'instructor'
ON CONFLICT DO NOTHING;
UPDATE user_roles SET active = true
WHERE NOT active
  AND user_id = (SELECT id FROM users WHERE lower(email) = :'email')
  AND role_id = (SELECT id FROM roles WHERE code = 'instructor');
SELECT id FROM users WHERE lower(email) = :'email';
SQL
)"
[[ "$USER_ID" =~ ^[0-9]+$ ]] || die "No se pudo crear o encontrar a $EMAIL en la tabla users."
echo "  usuario $USER_ID con rol instructor: listo"

# 3) Asignación por la API, con el token del admin
echo "3/3 Asignar como evaluador del curso $COURSE_ID (como $ADMIN_EMAIL):"
TOKEN="$(TOKEN_PASSWORD="${ADMIN_PASSWORD:-$SEED_USERS_PASSWORD}" "$ROOT_DIR/api/scripts/token.sh" "$ADMIN_EMAIL")" \
  || die "No se obtuvo el token del admin. ¿Está encendido Keycloak y existe $ADMIN_EMAIL (local-up.sh --with-admin)?"
BODY_FILE="$(mktemp)"
trap 'rm -f "$BODY_FILE"' EXIT
api() {  # api MÉTODO RUTA [JSON] -> imprime el código HTTP; el cuerpo queda en BODY_FILE
  local data=()
  [ $# -ge 3 ] && data=(-H "Content-Type: application/json" --data "$3")
  curl -sS -o "$BODY_FILE" -w '%{http_code}' -X "$1" \
    -H @<(printf 'Authorization: Bearer %s\n' "$TOKEN") "${data[@]}" "$API_URL$2"
}
CODE="$(api POST "/courses/$COURSE_ID/evaluators" "{\"user_id\": $USER_ID}")" || die "La API no responde en $API_URL."
case "$CODE" in
  201) echo "  asignado" ;;
  409) echo "  ya era evaluador del curso: sin cambios" ;;
  403) die "La API respondió 403. Si tu .env tiene REQUIRE_SECOND_FACTOR=true, el token sin OTP no sirve para rutas de admin. Respuesta: $(cat "$BODY_FILE")" ;;
  *) die "La API respondió $CODE: $(cat "$BODY_FILE")" ;;
esac

CODE="$(api GET "/courses/$COURSE_ID/evaluators")"
if [ "$CODE" != "200" ] || ! grep -q "\"user_id\":${USER_ID}[,}]" "$BODY_FILE"; then
  die "No aparece en GET /courses/$COURSE_ID/evaluators (HTTP $CODE): $(cat "$BODY_FILE")"
fi

echo
echo "Listo: $EMAIL (usuario $USER_ID) es evaluador del curso $COURSE_ID."
echo "Inicia sesión con ese correo y la contraseña SEED_USERS_PASSWORD del .env (mejor en una ventana de incógnito)."
