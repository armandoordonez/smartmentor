# Bitácora F04 · `ai/` base, syllabus y diagnóstico (agente `ai-base`, Ola 1)

Rama: `feature/ai-service-base` (sale de `origin/dev`; fusiona `origin/feature/database-v2-rebase` en `bf0f237` para usar las tablas `ai_*`). Publicada en `origin` al cerrar cada bloque.
Fuentes: `PLAN_IMPLEMENTACION_V3.md` (5.4 completa, 16.2, 18.5 y Fase 4 de la sección 7), ADR 0008, 0009, 0010, 0011, 0012, 0014 y 0019, `docs/contracts/ai-service-v1.md`, `docs/contracts/error-codes.md`, `prompts/` y `ai/app/domain/contracts/`.

## Hecho

| Bloque | Qué | Commit |
| --- | --- | --- |
| 1 | Esqueleto para `ai-content`: `app/ports/` (los 9 puertos del plan más `CatalogReader`), `app/core/` (configuración sin modelos por defecto, logs JSON con `request_id` y `job_id`, errores RFC 9457, JWT de servicio por JWKS con audiencia `smartmentor-ai`, motor de base), `fake_llm.py`, `fake_embedding.py`, `memory.py`, `prompt_files.py` (hashes de `catalog.yaml`), `application/llm_runner.py`, `application/pricing.py`, `adapters/budget.py`, `config/prices.yaml` sin precios, `domain/leveling.py`, `domain/sequencing.py`, `domain/pseudonymize.py`. `pyproject.toml` hereda `../ruff.toml` | `63a4c36` |
| — | Fusión de `origin/feature/database-v2-rebase` (esquema v2.0.0 con `ai_*`, `llm_call_logs`, permisos de `smartmentor_ai`) | `bf0f237` |
| 2 | `JobService` (idempotencia), *worker* (`SELECT … FOR UPDATE SKIP LOCKED`, `locked_until`, reencolado), tareas `syllabus.structure`, `diagnostic.generate_items`, `items.review`, `diagnostic.finalize`, síncronas `levels.estimate` y `path.sequence`; routers `/v1/jobs`, `/v1/tasks`, `/v1/prompts`, `/health`, `/ready`; `GeminiProvider` y `GeminiEmbeddingProvider`; interfaz de `AnthropicProvider`; adaptadores PostgreSQL; `container.py`; `main.py`; `python -m app.worker` | `88c9ed1` |
| 3 | Pruebas: propiedades con `hypothesis` (nivel y secuenciación sobre DAG aleatorios), *runner*, Gemini con cliente falso, flujos HTTP + *worker* | `dd42f6b` |
| 4 | Pruebas de integración contra PostgreSQL con el usuario `smartmentor_ai`, `Dockerfile`, `scripts/dev.sh`, `README.md`, `.gitignore` de `ai/`, esta bitácora | ver `git log` |

### Puntos de entrada y comandos para el agente `infra`

- Imagen: `docker build -f ai/Dockerfile .` (**contexto = raíz**, copia `prompts/`). Usuario `10001`, `HEALTHCHECK` a `/health`, puerto 8030.
- HTTP: `uvicorn app.main:app --host 0.0.0.0 --port 8030` (CMD por defecto). Worker: `python -m app.worker` (sale con 1 si `/ready` fallaría).
- CI desde `ai/`: `uv sync --frozen`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy`, `uv run pytest`, `uv run python -m scripts.export_schemas --check`. Sin claves ni `.env`: todo usa `FakeLlmProvider`.
- Pruebas de PostgreSQL en CI (opcional): base efímera migrada con Liquibase, rol creado por `database/bootstrap/01-create-database.sql` con `AI_DATABASE_USER`/`AI_DATABASE_PASSWORD`, y las variables `AI_TEST_DATABASE_URL` (usuario `smartmentor_ai`) y `AI_TEST_OWNER_DATABASE_URL` (dueño). Sin ellas se omiten (5 pruebas).

## Desviaciones frente al plan o al brief

| # | Plan o contrato | Lo que se hizo | Motivo |
| --- | --- | --- | --- |
| DV-01 | 5.4.6: `generate_structured(prompt, schema, model, temperature)` | `generate_structured(LlmRequest)` con `prompt_id`, versión, `system`, `user`, esquema, modelo y temperatura | El falso necesita saber qué prompt responde (varios comparten esquema) y el registro necesita el id |
| DV-02 | 5.4.1: puertos listados | Se agrega `CatalogReader` | Los trabajos reciben ids y deben leer texto y temas (lectura permitida por ADR 0009) |
| DV-03 | 5.4.1: `adapters/pricing` implícito | `PriceTable` en `app/application/pricing.py` | La aplicación no importa adaptadores |
| DV-04 | Contrato 2.2: `error.retryable` y `contract` | `ai_jobs` no tiene esas columnas: `retryable` se deriva del código (`domain/errors.py`) y `contract` del `job_type` | No se cambia el esquema de otro agente; resultado idéntico |
| DV-05 | Contrato 3: caché de `items.review` «por ítem» | Caché por lote (clave = prompt renderizado) | Una llamada por ítem multiplicaría el costo; el lote del mismo banco se repite igual |
| DV-06 | Contrato 3: caché de `diagnostic.finalize` «por inscripción» | El objetivo con LLM no usa caché | Contiene el perfil (dato personal, plan 5.4.11: sin caché de contenido personal) |
| DV-07 | `levels.estimate` | Embebe los textos de los temas en cada llamada (no lee `ai_embeddings`) | `embeddings.index_course` es de la Fase 5; cuando exista, se leen de ahí |
| DV-08 | `error-codes.md`: `INPUT_REFERENCE_NOT_FOUND` solo como código de trabajo | Las tareas síncronas lo devuelven también como HTTP 422; otros fallos del proveedor en síncronas → `503 SERVICE_UNAVAILABLE` | El catálogo HTTP de `ai/` no tenía código para «tema inexistente» |
| DV-09 | `video.rank` en 5.4.2 | `404 UNKNOWN_TASK` hasta la Fase 5 (agente `ai-content`) | Fuera del alcance de la Fase 4 |
| DV-10 | `AnthropicProvider` | Solo interfaz: falla con `LlmProviderError` y `/ready` lo informa | El SDK `anthropic` no es dependencia todavía; Gemini es el proveedor por defecto (ADR 0011) |

## Decisiones

| # | Decisión | Opciones | Motivo |
| --- | --- | --- | --- |
| DC-01 | Sin modelos ni proveedores por defecto: el servicio arranca, `/health` responde, `/ready` falla con `missing` y el *worker* sale con 1 | Fallar al importar la configuración | `/ready` puede explicar qué falta (ADR 0011, plan 16.2) |
| DC-02 | Con proveedor real los cuatro topes `AI_*_BUDGET_USD` son obligatorios para `/ready`; con `fake` un tope vacío no limita | Topes por defecto en código | `.env.example`: «vacío = el servicio no arranca con LLM real» |
| DC-03 | Con `AI_LLM_PROVIDER=fake` un modelo sin precio cuesta 0 y no bloquea `/ready` | Exigir precio siempre | CI y compose de desarrollo corren sin precios ficticios |
| DC-04 | `json_valid` = pasó el esquema; validaciones de código fallidas quedan `status=invalid_output` con `json_valid=true` | Marcar `false` también | Distingue «JSON inválido» (L-07) de «JSON que no cumple las reglas» |
| DC-05 | Reintentos en dos niveles: el *runner* reintenta errores transitorios del proveedor (2) y salidas inválidas (2, con los problemas en el prompt); el *worker* reencola solo `LLM_PROVIDER_*`, `INTERNAL_ERROR` y `VIDEO_SEARCH_UNAVAILABLE` hasta `AI_JOB_MAX_ATTEMPTS`, usando `locked_until` como «no antes de» | Reencolar también `INVALID_OUTPUT` | `INVALID_OUTPUT` ya gastó sus reintentos; queda reintentable a pedido (`/retry`) |
| DC-06 | Un trabajo reclamado tras vencer su arriendo (worker caído) falla con `INTERNAL_ERROR` si supera `AI_JOB_MAX_ATTEMPTS`; un `/retry` manual siempre concede una ejecución | Reiniciar `attempts` | `attempts` cuenta ejecuciones (contrato) |
| DC-07 | La caché guarda la salida `…LLM` validada (`ai_generation_cache.task` = id del prompt); un acierto deja fila en `llm_call_logs` con `from_cache=true` y costo 0 | No registrar aciertos | AD2 puede medir la tasa de acierto |
| DC-08 | Presupuesto = suma de `llm_call_logs.cost_usd` (día y mes en `APP_TIMEZONE`; curso por `ai_jobs.course_id`; inscripción por `enrollment_id`) revisada antes de cada intento | Contadores aparte | Una fuente de verdad; volumen del piloto pequeño |
| DC-09 | `pseudonymize()` quita correos, enlaces y números largos; nombres propios no | Heurística de mayúsculas | Falsos positivos en español; la API nunca envía el nombre (DEF-05) |
| DC-10 | Secuenciación: `blocked` si algún prerrequisito incluido no está completado (un omitido cuenta como completado); si no, `pending` (puede haber varios) | Solo el primero `pending` | Regla literal del contrato 4.2 |
| DC-11 | Nivel: tema sin ítems → `test_score=null` y su peso se redistribuye; sin ninguna señal con peso, la prueba cuenta sola con 0; *priors* recortados a 0..100 | Error | El contrato prohíbe peso en señales ausentes; el redondeo flotante daba 100,00000000000001 |
| DC-12 | El falso de `item_review` aprueba exactamente los ítems recibidos; los demás prompts responden con `prompts/examples/llm/<id>.json` | Respuestas fijas para todo | Cualquier lote generado se puede revisar en pruebas |
| DC-13 | SQL a mano con `text()` y parámetros enlazados en `adapters/postgres/` (excepción `S608` justificada en `pyproject.toml`) | Modelos ORM | Las tablas son de Liquibase; no se duplican definiciones |
| DC-14 | La imagen se construye con contexto en la raíz (`-f ai/Dockerfile .`) | Copiar `prompts/` dentro de `ai/` | `prompts/` es fuente única compartida con la API |

## Problemas y lecciones

- El sandbox del agente rechaza comandos con variables en la ruta de `docker`/`git`: se usan guiones en el *scratchpad* con rutas escritas.
- Un directorio de caché de uv creado por otro proceso como `root` impidió usar `/tmp/uv-cache-ai-base`; se usa `/tmp/uv-cache-ai-base2`.
- La ejecución se cortó por el límite de uso de la cuenta tras el bloque 2; se retomó desde el último *push* sin pérdidas.
- `google-genai` 3.0.0 emite `SyntaxWarning` por sus *docstrings*; se filtra en `pytest`.
- Hallazgo: `.env.example` aún trae `EMBEDDING_DIMENSION=1024` mientras el ADR 0012 fija 768 (ver «Cambios pedidos»).

## Métricas

| Momento | Ruff | mypy (estricto) | pytest |
| --- | --- | --- | --- |
| Bloque 1 | sin errores | sin errores (58 archivos) | 218 pasan en 1,8 s |
| Bloque 3 | sin errores | sin errores (90 archivos) | 272 pasan en 3,4 s |
| Bloque 4, con PostgreSQL desechable (pgvector 0.8.7 / PG 17, Liquibase: 50 *changesets*, usuario `smartmentor_ai`) | sin errores | sin errores (91 archivos) | **277 pasan en 5,8 s** (incluye 5 de integración PostgreSQL) |
| `ai/scripts/dev.sh all` sin red ni `.env` | sin errores | sin errores | 272 pasan, 5 omitidas (sin URL de base); esquemas: 26, 0 por actualizar; 20 s en total |

- Imagen: construida en 9 s (con caché), 250 MB; *smoke test*: `healthy`, `uid 10001`, `/ready` = `ready` con el falso y la base, `/v1/prompts` sin token = `401 MISSING_TOKEN`, *worker* corriendo; sin `AI_LLM_MODEL_DEFAULT` el *worker* sale con 1 y el log dice `worker not ready: env:AI_LLM_MODEL_DEFAULT`.
- Pruebas de integración en PostgreSQL: `syllabus.structure` llega a `succeeded` y su fila de `llm_call_logs` tiene `json_valid=true`; JSON inválido → 3 intentos `invalid_output` y `INVALID_OUTPUT` reintentable; caché (`from_cache=true`, costo 0); presupuesto agotado (`BUDGET_EXCEEDED`, fila `budget_exceeded`); idempotencia (202 y luego 200 con el mismo `job_id`); `SKIP LOCKED` con 4 reclamos concurrentes; `smartmentor_ai` no puede escribir `courses` (`permission denied`).
- Código nuevo: ≈ 4.300 líneas en `ai/app` y `ai/tests` (sin contar `uv.lock`).
- Limpieza: contenedores `sm-aibase-*`, red `sm-aibase-net` e imágenes de prueba eliminados.

## Impacto en el brief

| Sección del brief | Cambio sugerido |
| --- | --- |
| Arquitectura (capa de IA dentro del backend) | Ya previsto en B-03: servicio aparte con dos procesos; agregar que la API y la IA se comunican por trabajos en PostgreSQL con token de servicio |
| Métricas (costo por aprendiz y ruta) | El costo sale de `llm_call_logs` con precios de `ai/config/prices.yaml`; el presupuesto corta con `BUDGET_EXCEEDED` |
| Nivel previo (P1) y ruta (P2) | Documentar la redistribución de pesos cuando falta una señal y que un tema dominado se omite salvo que sea obligatorio |

## Cambios pedidos a archivos compartidos

| Archivo | Cambio |
| --- | --- |
| `docker-compose.yml` (agente `infra`) | Servicios `ai` y `ai-worker` con `build: {context: ., dockerfile: ai/Dockerfile}`; `ai-worker` con `command: ["python", "-m", "app.worker"]`; `depends_on` de `postgres` (sano) y `liquibase` (completado); variables `DATABASE_HOST/PORT/NAME`, `AI_DATABASE_USER`, `AI_DATABASE_PASSWORD`, `OIDC_ISSUER_URL`, `OIDC_JWKS_URL`, `AI_SERVICE_AUDIENCE`, `AI_LLM_*`, `AI_EMBEDDING_*`, `EMBEDDING_DIMENSION`, `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`, `AI_*_BUDGET_USD`, `APP_ENV`, `LOG_LEVEL`, `APP_TIMEZONE`; `ai` publica `${AI_PORT:-8030}:8030` solo en local |
| `.github/workflows/ci.yml` (agente `infra`) | Trabajo `ai` en `ai/` con los comandos de arriba (y, si se quiere, la base efímera con `AI_TEST_DATABASE_URL` y `AI_TEST_OWNER_DATABASE_URL`) |
| `.env.example` | `EMBEDDING_DIMENSION=1024` contradice el ADR 0012 (768); opcionales nuevas con valor por defecto: `AI_LLM_TIMEOUT_SECONDS`, `AI_WORKER_POLL_SECONDS`, `AI_JOB_LOCK_SECONDS`, `AI_JOB_MAX_ATTEMPTS`, `AI_JOB_RETRY_BACKOFF_SECONDS` (documentarlas si la prueba de coherencia del plan 16.2 lo exige) |
| `docs/contracts/error-codes.md` | Añadir `INPUT_REFERENCE_NOT_FOUND` (422) a la tabla HTTP de `ai/` para las tareas síncronas (DV-08) |
| `docs/contracts/ai-service-v1.md` | Anotar que `retryable` se deriva del código y que `ai_jobs` no guarda `contract` (DV-04); caché de `items.review` por lote (DV-05) |

## Pendiente

- `GeminiProvider` no se ha probado con la API real (requiere `GEMINI_API_KEY`, precios en `prices.yaml` y `AI_EVAL_LIVE=1`; fuera de la CI). La salida verificable «el syllabus del notebook produce un DAG válido con el proveedor real» queda para el dueño.
- `AnthropicProvider`: solo interfaz.
- `import-linter` (ADR 0008, punto 3) no se agregó; la regla «`domain` no importa `adapters` ni `api`» se cumple hoy por revisión.
- Fase 5 (agente `ai-content`): `video.rank`, `embeddings.index_course` (y leer de `ai_embeddings` en `levels.estimate`), contenido, bancos, calificación, badge, `eval/`.
