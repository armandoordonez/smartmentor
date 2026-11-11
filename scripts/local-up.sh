#!/usr/bin/env bash
# Instala y despliega SmartMentor en local desde cero (Linux, macOS y Windows con WSL2).
#
# Requisito previo: ya existe un .env completo en la raíz (copia el tuyo o parte de .env.example y
# completa lo que falte). Este script NO crea ni cambia valores de tu .env, salvo que uses --gen-secrets.
#
# Qué hace, en orden:
#   1. Comprueba Docker, Docker Compose v2 y el .env (variables obligatorias, coherencia).
#   2. Avisa si algún puerto del .env ya está ocupado por otro programa.
#   3. Levanta postgres → liquibase → api, keycloak, app (+ mailpit y el servicio de IA según opciones).
#   4. Espera a que los contenedores estén sanos.
#   5. Crea en Keycloak a los usuarios de desarrollo (SEED_*_EMAIL con SEED_USERS_PASSWORD).
#   6. Imprime las URLs.
#
# Uso:
#   scripts/local-up.sh                 # stack completo: correo (mailpit) + servicio de IA
#   scripts/local-up.sh --no-ai         # sin servicio de IA
#   scripts/local-up.sh --no-mail       # sin mailpit (usa el SMTP real del .env)
#   scripts/local-up.sh --with-admin    # además crea al administrador en Keycloak
#   scripts/local-up.sh --gen-secrets   # rellena antes las variables secretas vacías (scripts/gen-secrets.sh)
#   scripts/local-up.sh --no-build      # no reconstruye las imágenes
#   scripts/local-up.sh --down          # detiene el stack (conserva los datos)
#
# Es idempotente: puedes repetirlo; los usuarios que ya existen no se tocan.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

AI=1; MAIL=1; ADMIN=0; GEN=0; BUILD=1; DOWN=0
for arg in "$@"; do
  case "$arg" in
    --no-ai) AI=0 ;;
    --no-mail) MAIL=0 ;;
    --with-admin) ADMIN=1 ;;
    --gen-secrets) GEN=1 ;;
    --no-build) BUILD=0 ;;
    --down) DOWN=1 ;;
    -h|--help) sed -n '2,26p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Argumento desconocido: $arg" >&2; exit 2 ;;
  esac
done

say() { printf '\n==> %s\n' "$*"; }
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

PROFILES=()
[ "$MAIL" = 1 ] && PROFILES+=(--profile mail)
[ "$AI" = 1 ] && PROFILES+=(--profile ai)
COMPOSE=(docker compose "${PROFILES[@]}")

if [ "$DOWN" = 1 ]; then
  say "Deteniendo el stack (los datos se conservan en database/data)"
  # Se bajan todos los perfiles para no dejar contenedores sueltos.
  docker compose --profile mail --profile ai down
  exit 0
fi

# 1) Requisitos
say "Comprobando requisitos"
command -v docker >/dev/null 2>&1 || die "Docker no está instalado o no está en el PATH."
docker info >/dev/null 2>&1 || die "Docker no responde: inicia el servicio (Docker Desktop en Windows y macOS) y verifica tu permiso (grupo docker en Linux)."
docker compose version >/dev/null 2>&1 || die "Falta Docker Compose v2 (comando 'docker compose')."
[ -f .env ] || die "No existe .env en $ROOT_DIR. Cópialo de tu equipo o parte de .env.example."
if grep -q $'\r' .env; then
  die ".env tiene saltos de línea de Windows (CRLF). Conviértelo: sed -i 's/\\r\$//' .env"
fi
chmod 600 .env 2>/dev/null || true

if [ "$GEN" = 1 ]; then
  say "Generando los secretos vacíos"
  scripts/gen-secrets.sh
fi

set -a
# shellcheck disable=SC1091
. ./.env
set +a

missing=()
for v in POSTGRES_USER POSTGRES_PASSWORD KEYCLOAK_PORT API_PORT APP_PORT POSTGRES_PORT SEED_USERS_PASSWORD; do
  [ -n "${!v:-}" ] || missing+=("$v")
done
if [ "${#missing[@]}" -gt 0 ]; then
  die "Faltan valores en .env: ${missing[*]} (usa --gen-secrets para los secretos)."
fi
if [ "$AI" = 1 ]; then
  if [ "${AI_LLM_PROVIDER:-}" = "gemini" ] && [ -z "${GEMINI_API_KEY:-}" ]; then
    die "AI_LLM_PROVIDER=gemini pero GEMINI_API_KEY está vacía. Defínela o usa AI_LLM_PROVIDER=fake, o --no-ai."
  fi
fi
if command -v python3 >/dev/null 2>&1 && [ -f scripts/check-env-coherence.py ]; then
  python3 -I scripts/check-env-coherence.py >/dev/null 2>&1 \
    || echo "Aviso: scripts/check-env-coherence.py reporta diferencias entre .env.example y el código (no bloquea)."
fi

# 2) Puertos (solo si no es nuestro propio stack el que los usa)
say "Revisando puertos"
if docker ps --format '{{.Names}}' | grep -q '^smartmentor-'; then
  echo "  Ya hay contenedores smartmentor-* en marcha: se actualizarán en su sitio."
else
  busy=()
  for pair in POSTGRES_PORT API_PORT KEYCLOAK_PORT APP_PORT AI_PORT MAILPIT_UI_PORT; do
    port="${!pair:-}"
    [ -n "$port" ] || continue
    if (exec 3<>"/dev/tcp/127.0.0.1/$port") 2>/dev/null; then busy+=("$pair=$port"); fi
  done
  if [ "${#busy[@]}" -gt 0 ]; then
    die "Puertos ocupados por otro programa: ${busy[*]}. Cámbialos en .env o libéralos."
  fi
  echo "  Libres."
fi

# 3) Arranque
say "Levantando los contenedores (la primera vez descarga imágenes y tarda varios minutos)"
mkdir -p database/data/postgres
UP=(up -d)
[ "$BUILD" = 1 ] && UP+=(--build)
"${COMPOSE[@]}" "${UP[@]}"

# 4) Espera a que estén sanos
say "Esperando a que los servicios estén sanos (máximo 10 minutos)"
wait_healthy() {
  local name="$1" deadline=$((SECONDS + 600)) state
  while [ "$SECONDS" -lt "$deadline" ]; do
    state="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$name" 2>/dev/null || echo missing)"
    case "$state" in
      healthy|running) echo "  OK   $name"; return 0 ;;
      exited|dead) docker logs --tail 30 "$name" >&2 || true; die "$name terminó con error (logs arriba)." ;;
    esac
    sleep 5
  done
  docker logs --tail 30 "$name" >&2 || true
  die "$name no quedó sano a tiempo."
}
liq="$(docker inspect -f '{{.State.ExitCode}}' smartmentor-liquibase 2>/dev/null || echo 1)"
[ "$liq" = "0" ] || { docker logs --tail 30 smartmentor-liquibase >&2 || true; die "Liquibase (migraciones de la base) falló."; }
echo "  OK   smartmentor-liquibase (migraciones aplicadas)"
for c in smartmentor-postgres smartmentor-keycloak smartmentor-api smartmentor-app; do wait_healthy "$c"; done
[ "$AI" = 1 ] && for c in smartmentor-ai smartmentor-ai-worker; do wait_healthy "$c"; done
[ "$MAIL" = 1 ] && wait_healthy smartmentor-mailpit

# 5) Usuarios de desarrollo en Keycloak
if [ -n "${SEED_INSTRUCTOR_EMAIL:-}${SEED_LEARNER_EMAIL:-}${SEED_ADMIN_EMAIL:-}" ]; then
  say "Creando los usuarios de desarrollo en Keycloak"
  SEED_ARGS=()
  [ "$ADMIN" = 1 ] && SEED_ARGS+=(--with-admin)
  keycloak/scripts/seed-dev-users.sh "${SEED_ARGS[@]}"
else
  echo "SEED_*_EMAIL vacíos: no se crean usuarios de desarrollo."
fi

# 6) Resumen
say "Listo"
cat <<OUT
  Interfaz     http://localhost:${APP_PORT}
  API (docs)   http://localhost:${API_PORT}/docs
  Keycloak     http://localhost:${KEYCLOAK_PORT}
  PostgreSQL   localhost:${POSTGRES_PORT}
OUT
[ "$AI" = 1 ] && echo "  Servicio IA  localhost:${AI_PORT:-8030} (proveedor: ${AI_LLM_PROVIDER:-?})"
[ "$MAIL" = 1 ] && echo "  Mailpit      http://localhost:${MAILPIT_UI_PORT:-8025}"
cat <<'OUT'

Inicia sesión con los correos SEED_*_EMAIL de tu .env y la contraseña SEED_USERS_PASSWORD.
El instructor y el administrador configuran su OTP en el primer ingreso.
Detener: scripts/local-up.sh --down   |   Ver logs: docker compose logs -f <servicio>
OUT
