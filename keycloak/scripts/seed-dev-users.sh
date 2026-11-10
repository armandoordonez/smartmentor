#!/usr/bin/env bash
# Crea en Keycloak los usuarios de DESARROLLO que Liquibase siembra en la base de la aplicación
# (SEED_INSTRUCTOR_EMAIL y SEED_LEARNER_EMAIL; con --with-admin también SEED_ADMIN_EMAIL).
#
# Por qué existe: Liquibase solo crea la fila de la aplicación (tabla users y su rol). Para iniciar sesión
# la persona también debe existir en Keycloak, con el MISMO correo y verificado: la API enlaza ambos
# en el primer ingreso por el `sub` del token y por el correo verificado.
#
# Qué hace: crea cada usuario si no existe (idempotente, no toca los que ya están), con el correo como
# nombre de usuario, correo verificado, el rol de realm correspondiente y la contraseña SEED_USERS_PASSWORD
# del .env (la genera scripts/gen-secrets.sh). El instructor y el administrador configuran su OTP en el
# primer ingreso (el flujo del realm lo exige). No imprime ninguna contraseña.
#
# SOLO DESARROLLO. En producción deja SEED_*_EMAIL vacíos y no ejecutes este script.
#
# Uso:
#   keycloak/scripts/seed-dev-users.sh                # instructor y aprendiz
#   keycloak/scripts/seed-dev-users.sh --with-admin   # además el administrador
#   keycloak/scripts/seed-dev-users.sh --reset-passwords   # vuelve a poner SEED_USERS_PASSWORD a los que ya existen
#
# Credenciales de la consola: por defecto las del arranque (KC_BOOTSTRAP_ADMIN_*). Si cambiaste la
# contraseña en la consola, exporta KCADM_USER y KCADM_PASSWORD antes de ejecutarlo.
# KC_EXEC permite apuntar a otro contenedor (por ejemplo, uno desechable de pruebas).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
REALM="${REALM:-smartmentor}"
WITH_ADMIN=0
RESET_PASSWORDS=0
for arg in "$@"; do
  case "$arg" in
    --with-admin) WITH_ADMIN=1 ;;
    --reset-passwords) RESET_PASSWORDS=1 ;;
    -h|--help) sed -n '2,23p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Argumento desconocido: $arg" >&2; exit 2 ;;
  esac
done

# Variables del .env (se lee como script de shell; los valores con espacios van entre comillas).
if [ -f "$ROOT_DIR/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  . "$ROOT_DIR/.env"
  set +a
fi

if [ -z "${SEED_USERS_PASSWORD:-}" ]; then
  echo "Falta SEED_USERS_PASSWORD en .env. Ejecuta scripts/gen-secrets.sh o defínela (12 caracteres o más," >&2
  echo "con mayúscula, minúscula y dígito: es la política de contraseñas del realm)." >&2
  exit 1
fi

# El comando se arma como arreglo para que las rutas con espacios (este repositorio puede estar en una
# carpeta con espacios) no se partan; KC_EXEC, si existe, se separa por espacios.
if [ -n "${KC_EXEC:-}" ]; then
  read -r -a KC_EXEC_CMD <<< "$KC_EXEC"
else
  KC_EXEC_CMD=(docker compose -f "$ROOT_DIR/docker-compose.yml" exec -T keycloak)
fi

"${KC_EXEC_CMD[@]}" env "TARGET_REALM=$REALM" "WITH_ADMIN=$WITH_ADMIN" "RESET_PASSWORDS=$RESET_PASSWORDS" \
  "SEED_INSTRUCTOR_EMAIL=${SEED_INSTRUCTOR_EMAIL:-}" "SEED_LEARNER_EMAIL=${SEED_LEARNER_EMAIL:-}" \
  "SEED_ADMIN_EMAIL=${SEED_ADMIN_EMAIL:-}" "SEED_USERS_PASSWORD=$SEED_USERS_PASSWORD" \
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

seed_user() {  # seed_user CORREO ROL NOMBRE
  local email="$1" role="$2" first="$3"
  if [ -z "$email" ]; then
    echo "  (omitido) rol $role: la variable de correo está vacía"
    return 0
  fi
  local found
  found="$(kc get users -r "$TARGET_REALM" -q "email=$email" -q exact=true --fields id | grep -c '"id"' || true)"
  if [ "$found" != "0" ]; then
    if [ "$RESET_PASSWORDS" = "1" ]; then
      if kc set-password -r "$TARGET_REALM" --username "$email" --new-password "$SEED_USERS_PASSWORD" 2>/dev/null; then
        echo "  ya existe: $email ($role) — contraseña sincronizada con SEED_USERS_PASSWORD"
      else
        echo "  ERROR: Keycloak rechazó la contraseña de SEED_USERS_PASSWORD (política del realm): $email" >&2
        return 1
      fi
    else
      echo "  ya existe: $email ($role) — sin cambios"
    fi
    return 0
  fi
  kc create users -r "$TARGET_REALM" \
    -s "username=$email" -s "email=$email" -s emailVerified=true -s enabled=true \
    -s "firstName=$first" -s "lastName=Desarrollo" >/dev/null
  if ! kc set-password -r "$TARGET_REALM" --username "$email" --new-password "$SEED_USERS_PASSWORD" 2>/dev/null; then
    echo "  ERROR: Keycloak rechazó la contraseña de SEED_USERS_PASSWORD (política del realm). Se dejó el usuario sin contraseña: $email" >&2
    return 1
  fi
  kc add-roles -r "$TARGET_REALM" --uusername "$email" --rolename "$role" >/dev/null
  echo "  creado: $email ($role)"
}

echo "Realm $TARGET_REALM:"
seed_user "$SEED_INSTRUCTOR_EMAIL" instructor Instructor
seed_user "$SEED_LEARNER_EMAIL" learner Aprendiz
if [ "$WITH_ADMIN" = "1" ]; then
  seed_user "$SEED_ADMIN_EMAIL" admin Administrador
fi
INNER
