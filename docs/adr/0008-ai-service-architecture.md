# ADR 0008: Microservicio de IA (`ai/`): arquitectura, contrato y puertos

* **Estado:** Propuesto. Lo cierra la aprobación del dueño de los contratos de la Ola 0 (cambio moderado B-03 del plan) antes de la Fase 4
* **Fecha:** 2026-11-07
* **Autor:** eduar.troyano
* **Fuente:** [plan de implementación v3](../../PLAN_IMPLEMENTACION_V3.md), secciones 5.4.1 a 5.4.15 y 15.1 (B-03)
* **Relacionados:** [ADR 0003](0003-api-domain-first-layout.md), [ADR 0009](0009-data-ownership-api-and-ai.md), [ADR 0010](0010-async-jobs-postgres-pull-ingestion.md), [ADR 0011](0011-llm-provider.md), [ADR 0014](0014-service-to-service-auth-client-credentials.md), [estándar del microservicio](../../api/microservice-development-standard.md)

---

## 1. Contexto

El brief ubica la «capa de IA» dentro del backend. La prueba «Mago de Oz» (notebook v2) define 13 prompts, 11 contratos, algoritmos deterministas (orden topológico, nivel, secuenciación, re-ranking de videos) y reglas de validación y caché. Llevar eso a producción plantea:

- tareas lentas (estructurar un syllabus, generar un banco de ítems) que no caben en una petición HTTP;
- un proveedor de LLM que debe poder cambiarse ([ADR 0011](0011-llm-provider.md));
- la regla del estándar de la API (§34): la API no llama a un SDK de LLM;
- pruebas sin claves reales (CI con un proveedor simulado).

## 2. Decisión

1. **`ai/` es un servicio FastAPI aparte**, con el mismo estándar de la API: Ruff, mypy estricto, RFC 9457, logs JSON, `/health` y `/ready`, Docker multietapa, usuario no root y `uv`.
2. **Dos procesos con la misma imagen:** `ai` (HTTP, puerto `AI_PORT=8030`) y `ai-worker` (trabajos asíncronos, [ADR 0010](0010-async-jobs-postgres-pull-ingestion.md)).
3. **Organización por capas, no por dominio** (`core/`, `api/`, `application/`, `domain/`, `ports/`, `adapters/`, `worker/`). Es una excepción justificada al ADR 0003: `ai/` tiene un solo contexto, «generar y evaluar contenido». `import-linter` verifica que `domain` no importe `adapters` ni `api`.
4. **Puertos intercambiables:** `LlmProvider`, `EmbeddingProvider`, `VideoSearchProvider`, `TranscriptProvider`, `PromptStore`, `GenerationCache`, `JobRepository`, `LlmCallLogRepository` y `BudgetGuard`. El SDK del proveedor solo vive dentro de su adaptador.
5. **Contrato HTTP interno (prefijo `/v1`):** `POST /v1/jobs` (202 con `job_id`, idempotente por `idempotency_key`), `GET /v1/jobs/{job_id}`, `POST /v1/jobs/{job_id}/retry`, tareas síncronas `POST /v1/tasks/levels.estimate`, `path.sequence` y `video.rank`, y `GET /v1/prompts`. `/ready` verifica la base, la carga de prompts y que cada modelo configurado tenga precio.
6. **Dominio determinista sin LLM:** `sequencing.py`, `leveling.py`, `video_ranking.py` y `metrics.py` (κ, QWK, F1, P@k, nDCG@k, Hake, SUS), probados con `hypothesis`.
7. **Validación de salidas:** esquema `…LLM` como salida estructurada → `model_validate_json` → validaciones de código → hasta 2 reintentos con el error → `status=invalid_output`. Cada intento queda en `llm_call_logs` con `json_valid`.
8. **Prompts versionados** en `prompts/` (front matter y un archivo por versión) con `catalog.yaml`; los esquemas se exportan desde `ai/app/domain/contracts/` a `prompts/schemas/*.v1.json` y la CI compara sus hashes.
9. **Caché y presupuesto:** caché por `cache_key` en `ai_generation_cache` (salvo calificación y contenido personal) y `BudgetGuard` con topes diario, por curso y por inscripción; si se supera, `budget_exceeded`.
10. **En la API**, el puerto `AiServicePort` (`ai_gateway/repository.py`) con los adaptadores `HttpAiService` y `FakeAiService`.
11. **Red:** `ai` no publica puerto en producción; en local publica 8030 solo para Swagger.

## 3. Alternativas descartadas

- **Un módulo de IA dentro de la API:** un servicio menos que operar, pero mezcla tareas lentas con peticiones de usuario, rompe la regla §34 del estándar y no permite probar, escalar o apagar la IA sin tocar la API.
- **Organizar `ai/` por dominio como la API:** con un solo contexto, la carpeta por dominio solo agrega niveles.
- **LlamaIndex como orquestador:** crearía tablas propias fuera de Liquibase ([ADR 0013](0013-rag-chunks-in-liquibase-tables.md)).

## 4. Consecuencias

- **Positivas:** la IA se prueba sola con `FakeLlmProvider` (unitarias, contrato, integración) y solo la evaluación usa el LLM real (`AI_EVAL_LIVE=1`, nunca en CI); un único escritor por tabla ([ADR 0009](0009-data-ownership-api-and-ai.md)); el proveedor cambia por configuración.
- **Negativas y pendientes:**
  - Un servicio y un proceso más que levantar, depurar y monitorear.
  - La comunicación necesita autenticación entre servicios ([ADR 0014](0014-service-to-service-auth-client-credentials.md)).
  - El brief habla de una capa dentro del backend: el cambio se registra en el brief v2 (B-03).
  - El estándar de la API (§34) se actualiza para describir la IA como servicio aparte (Fase 4).
