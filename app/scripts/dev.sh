#!/usr/bin/env bash
# Herramientas de desarrollo de la interfaz, ejecutadas en contenedores (no hace falta instalar
# Python ni uv).
#
# Uso (desde cualquier carpeta):
#   app/scripts/dev.sh lock          genera/actualiza uv.lock
#   app/scripts/dev.sh format        ordena imports y formatea el código con Ruff
#   app/scripts/dev.sh lint          ruff check + ruff format --check
#   app/scripts/dev.sh typecheck     mypy (modo estricto)
#   app/scripts/dev.sh test [args]   pytest (unitarias y de páginas con AppTest)
#   app/scripts/dev.sh run           levanta la interfaz en http://localhost:8501 (datos de ejemplo)
#   app/scripts/dev.sh all           lint + typecheck + test
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UV_IMAGE="ghcr.io/astral-sh/uv:0.9.30-python3.12-bookworm"
APP_PORT="${APP_PORT:-8501}"

uv_run() {
  docker run --rm --user "$(id -u):$(id -g)" \
    -e HOME=/tmp -e UV_CACHE_DIR=/tmp/uv-cache -e UV_LINK_MODE=copy -e UV_PYTHON_DOWNLOADS=never \
    -e APP_DATA_SOURCE=sample \
    -v "$APP_DIR:/app" -w /app "$@"
}

case "${1:-}" in
  lock)      uv_run "$UV_IMAGE" uv lock ;;
  format)    uv_run "$UV_IMAGE" sh -c "uv run ruff check --fix --select I . && uv run ruff format ." ;;
  lint)      uv_run "$UV_IMAGE" sh -c "uv run ruff check . && uv run ruff format --check ." ;;
  typecheck) uv_run "$UV_IMAGE" uv run mypy ;;
  test)      shift; uv_run "$UV_IMAGE" uv run pytest "$@" ;;
  run)       uv_run -it -p "$APP_PORT:8501" "$UV_IMAGE" \
               uv run streamlit run src/main.py --server.port 8501 --server.address 0.0.0.0 ;;
  all)
    uv_run "$UV_IMAGE" sh -c "uv run ruff check . && uv run ruff format --check . && uv run mypy"
    uv_run "$UV_IMAGE" uv run pytest
    ;;
  *) sed -n '2,13p' "${BASH_SOURCE[0]}"; exit 1 ;;
esac
