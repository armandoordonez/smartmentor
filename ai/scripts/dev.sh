#!/usr/bin/env bash
# Herramientas de desarrollo de ai/, en contenedores (no hace falta instalar Python ni uv).
# No lee .env: las pruebas usan el proveedor falso y valores desechables.
#
# Uso (desde cualquier carpeta):
#   ai/scripts/dev.sh lock             genera/actualiza uv.lock
#   ai/scripts/dev.sh format           ordena imports y formatea con Ruff
#   ai/scripts/dev.sh lint             ruff check + ruff format --check
#   ai/scripts/dev.sh typecheck        mypy estricto
#   ai/scripts/dev.sh test [args]      pytest (las de PostgreSQL se omiten sin AI_TEST_DATABASE_URL)
#   ai/scripts/dev.sh export-schemas   regenera prompts/schemas/ desde los contratos
#   ai/scripts/dev.sh all              lint + typecheck + test + export-schemas --check
#
# Pruebas de integración con PostgreSQL: exporta AI_TEST_DATABASE_URL (usuario smartmentor_ai) y
# AI_TEST_OWNER_DATABASE_URL (dueño, solo para sembrar), y opcionalmente AI_TEST_NETWORK con la red
# de Docker donde está la base.
set -euo pipefail

AI_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT_DIR="$(cd "$AI_DIR/.." && pwd)"
UV_IMAGE="ghcr.io/astral-sh/uv:0.9.30-python3.12-bookworm"

uv_run() {
  local extra=()
  [[ -n "${AI_TEST_NETWORK:-}" ]] && extra+=(--network "$AI_TEST_NETWORK")
  [[ -n "${AI_TEST_DATABASE_URL:-}" ]] && extra+=(-e AI_TEST_DATABASE_URL -e AI_TEST_OWNER_DATABASE_URL)
  docker run --rm --user "$(id -u):$(id -g)" "${extra[@]}" \
    -e HOME=/tmp -e UV_CACHE_DIR=/tmp/uv-cache -e UV_LINK_MODE=copy \
    -e UV_PROJECT_ENVIRONMENT=/tmp/venv -e UV_PYTHON_DOWNLOADS=never \
    -v "$ROOT_DIR:/repo" -w /repo/ai "$UV_IMAGE" sh -c "$*"
}

case "${1:-}" in
  lock)           uv_run "uv lock" ;;
  format)         uv_run "uv run ruff check --fix --select I . && uv run ruff format ." ;;
  lint)           uv_run "uv run ruff check . && uv run ruff format --check ." ;;
  typecheck)      uv_run "uv run mypy" ;;
  test)           shift; uv_run "uv run pytest $*" ;;
  export-schemas) uv_run "uv run python -m scripts.export_schemas" ;;
  all)
    uv_run "uv run ruff check . && uv run ruff format --check . && uv run mypy \
      && uv run pytest && uv run python -m scripts.export_schemas --check"
    ;;
  *) sed -n '2,17p' "${BASH_SOURCE[0]}"; exit 1 ;;
esac
