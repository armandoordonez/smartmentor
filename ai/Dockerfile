# Imagen del servicio de IA de SmartMentor (ADR 0008). Una sola imagen, dos procesos:
#   ai         uvicorn app.main:app --host 0.0.0.0 --port 8030   (CMD por defecto)
#   ai-worker  python -m app.worker
#
# El contexto de construcción es la RAÍZ del repositorio (necesita prompts/):
#   docker build -f ai/Dockerfile -t smartmentor-ai .
# El .dockerignore de la raíz excluye .env, .git y cachés.

FROM python:3.12-slim-bookworm AS builder
COPY --from=ghcr.io/astral-sh/uv:0.9.30 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY ai/pyproject.toml ai/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

FROM python:3.12-slim-bookworm
ENV TZ=America/Bogota \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH" \
    AI_PROMPTS_DIR=/app/prompts \
    AI_PRICES_FILE=/app/config/prices.yaml
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --system --uid 10001 --no-create-home app
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY ai/app ./app
COPY ai/config ./config
COPY prompts ./prompts
USER app
EXPOSE 8030
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8030/health', timeout=3)"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8030"]
