# ai/

Capa de IA, núcleo de la tesis: generación, RAG, motor de ruta y calificador.

## Estado

Por ahora solo contiene los **contratos** (Fase 1 del plan): `app/domain/contracts/` define los modelos Pydantic `…LLM` (lo que se pide al proveedor) y los contratos (lo que `ai/` entrega a la API), con las validaciones de código del plan 5.4.4. De ahí salen los esquemas versionados de `prompts/schemas/`. El servicio HTTP, el *worker* y los adaptadores llegan en las Fases 4 y 5. El contrato HTTP está en `docs/contracts/ai-service-v1.md`.

## Comandos

Con la imagen de `uv`, sin `.env` (los contratos no leen variables de entorno):

```bash
docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp -e UV_CACHE_DIR=/tmp/uv-cache \
  -e UV_LINK_MODE=copy -e UV_PROJECT_ENVIRONMENT=/tmp/venv \
  -v "$PWD:/repo" -w /repo/ai ghcr.io/astral-sh/uv:0.9.30-python3.12-bookworm \
  sh -c "uv sync && uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest"
```

Se monta la raíz del repositorio (no solo `ai/`) porque las pruebas leen `prompts/`. Para regenerar los esquemas: `uv run python -m scripts.export_schemas` (con `--check` solo compara).

| Carpeta | Contenido |
| --- | --- |
| `app/domain/contracts/` | Modelos, validaciones (`validation.py`), grafo de prerrequisitos (`graph.py`) y registro de esquemas (`registry.py`) |
| `scripts/export_schemas.py` | Exporta los modelos a `prompts/schemas/*.v1.json` de forma determinista |
| `tests/contract/` | Ejemplos contra esquemas, esquemas al día, catálogo de prompts (hashes, marcadores, delimitadores, vocabulario) |
| `tests/unit/` | Validaciones de código y reglas de los contratos |
