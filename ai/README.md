# ai/

Servicio de IA de SmartMentor (ADR 0008): genera y evalúa contenido con un LLM detrás de puertos intercambiables. Un servicio FastAPI aparte, con dos procesos de la misma imagen: `ai` (HTTP) y `ai-worker` (trabajos). El contrato HTTP está en [`docs/contracts/ai-service-v1.md`](../docs/contracts/ai-service-v1.md) y los códigos de error en [`docs/contracts/error-codes.md`](../docs/contracts/error-codes.md).

## Estado (Fase 4)

| Pieza | Estado |
| --- | --- |
| Trabajos `syllabus.structure`, `diagnostic.generate_items`, `items.review`, `diagnostic.finalize` | Hechos |
| Tareas síncronas `levels.estimate` y `path.sequence` | Hechas (`video.rank` responde `404 UNKNOWN_TASK` hasta la Fase 5) |
| Proveedores | `fake` (pruebas y CI), `gemini` (SDK `google-genai`), `anthropic` solo interfaz |
| Persistencia | PostgreSQL (`ai_jobs`, `llm_call_logs`, `ai_generation_cache`; lectura de `courses`, `topics`, `learning_outcomes`, `syllabus_documents`) o memoria en pruebas |
| Fase 5 | Contenido, bancos de quiz y final, calificación, videos y badge: se agregan como `JobHandler` en `app/container.py` (`build_handlers`) |

## Estructura (por capas)

| Carpeta | Contenido |
| --- | --- |
| `app/core/` | Configuración (`pydantic-settings`), logs JSON con `request_id` y `job_id`, errores RFC 9457, JWT de servicio (JWKS, audiencia `smartmentor-ai`), motor de base |
| `app/ports/` | `LlmProvider`, `EmbeddingProvider`, `VideoSearchProvider`, `TranscriptProvider`, `PromptStore`, `GenerationCache`, `JobRepository`, `LlmCallLogRepository`, `BudgetGuard`, `CatalogReader` |
| `app/adapters/` | `fake_llm.py`, `fake_embedding.py`, `memory.py`, `prompt_files.py`, `gemini.py`, `anthropic.py`, `budget.py`, `postgres/` |
| `app/application/` | `llm_runner.py` (validación, reintentos, caché, presupuesto, registro), `jobs.py` (tipos de trabajo e idempotencia), un módulo por tarea, `pricing.py` |
| `app/domain/` | `contracts/` (fuente de `prompts/schemas/`), `leveling.py`, `sequencing.py`, `pseudonymize.py`, `errors.py` |
| `app/api/` | Routers `/health`, `/ready`, `/v1/jobs`, `/v1/tasks`, `/v1/prompts` |
| `app/worker/` | Bucle con `SELECT … FOR UPDATE SKIP LOCKED`, arriendo `locked_until` y reencolado de errores transitorios |
| `config/prices.yaml` | USD por millón de tokens por modelo. **Lo llena el dueño**; sin precio para un modelo configurado, `/ready` falla |
| `tests/` | `unit/` (incluye propiedades con `hypothesis`), `contract/`, `integration/` (HTTP + worker en memoria y contra PostgreSQL) |

## Configuración

Todo sale de variables de entorno (raíz `.env.example`); **el código no trae proveedores ni modelos por defecto** (ADR 0011 y 0012). Sin ellos el servicio arranca, `/health` responde, `/ready` devuelve `503 NOT_READY` con la lista `missing` y el *worker* sale con código 1.

| Variable | Uso |
| --- | --- |
| `AI_LLM_PROVIDER` | `gemini`, `anthropic` o `fake` |
| `AI_LLM_MODEL_DEFAULT`, `AI_LLM_MODEL_SMALL` | Modelo de generación y modelo pequeño (revisión de ítems, calificación, badge) |
| `AI_EMBEDDING_PROVIDER`, `AI_EMBEDDING_MODEL`, `EMBEDDING_DIMENSION` | Embeddings (`gemini` o `fake`) |
| `GEMINI_API_KEY`, `ANTHROPIC_API_KEY` | Claves; solo en `.env` |
| `AI_DAILY_BUDGET_USD`, `AI_MONTHLY_BUDGET_USD`, `AI_COURSE_BUDGET_USD`, `AI_ENROLLMENT_BUDGET_USD` | Topes; obligatorios con proveedor real |
| `DATABASE_HOST`, `DATABASE_PORT`, `DATABASE_NAME`, `AI_DATABASE_USER`, `AI_DATABASE_PASSWORD` | Base con el usuario `smartmentor_ai` (ADR 0019) |
| `OIDC_ISSUER_URL`, `OIDC_JWKS_URL`, `AI_SERVICE_AUDIENCE` | Validación del token de servicio (ADR 0014) |
| `AI_PROMPTS_DIR`, `AI_PRICES_FILE` | Rutas (la imagen las fija en `/app/prompts` y `/app/config/prices.yaml`) |
| `AI_LLM_TIMEOUT_SECONDS`, `AI_WORKER_POLL_SECONDS`, `AI_JOB_LOCK_SECONDS`, `AI_JOB_MAX_ATTEMPTS`, `AI_JOB_RETRY_BACKOFF_SECONDS` | Ajustes con valor por defecto (120, 2, 900, 3, 30) |

## Comandos

```bash
ai/scripts/dev.sh all             # lint + typecheck + pruebas + esquemas al día (sin .env ni red)
ai/scripts/dev.sh test -k syllabus
ai/scripts/dev.sh export-schemas  # regenera prompts/schemas/ desde app/domain/contracts/
```

Equivalentes en la CI (desde `ai/`): `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy`, `uv run pytest`.

Pruebas contra PostgreSQL: con la base migrada por Liquibase y el rol `smartmentor_ai` creado por `database/bootstrap/`, exporta `AI_TEST_DATABASE_URL=postgresql+asyncpg://smartmentor_ai:…@host:5432/db`, `AI_TEST_OWNER_DATABASE_URL` (dueño, solo para sembrar) y `AI_TEST_NETWORK` si la base está en una red de Docker. Sin ellas, esas pruebas se omiten.

## Imagen y procesos

```bash
docker build -f ai/Dockerfile -t smartmentor-ai .   # contexto: raíz del repositorio (copia prompts/)
# HTTP:   uvicorn app.main:app --host 0.0.0.0 --port 8030   (CMD por defecto, HEALTHCHECK a /health)
# Worker: python -m app.worker
```

Usuario no root (`uid 10001`). En producción `ai` no publica puerto; en local, 8030 solo para Swagger (`/docs`).
