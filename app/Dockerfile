# Imagen de la interfaz de SmartMentor (Streamlit). Multi-etapa, igual que la API.

FROM python:3.12-slim-bookworm AS builder
COPY --from=ghcr.io/astral-sh/uv:0.9.30 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

FROM python:3.12-slim-bookworm
ENV TZ=America/Bogota \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --system --uid 10001 --create-home app
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY .streamlit ./.streamlit
COPY src ./src
# Fixtures del modo APP_DATA_SOURCE=fixtures (demostración y pruebas de humo).
COPY tests/fixtures ./tests/fixtures
COPY docker-entrypoint.sh ./docker-entrypoint.sh
RUN chmod 0755 /app/docker-entrypoint.sh
USER app
EXPOSE 8501
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health', timeout=3)"
# El entrypoint genera ~/.streamlit/secrets.toml desde variables de entorno y lanza Streamlit.
CMD ["/app/docker-entrypoint.sh"]
