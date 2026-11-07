# ADR 0010: Trabajos asíncronos en PostgreSQL sin broker e ingesta por consulta

* **Estado:** Propuesto. Lo cierra la Fase 4 (`ai/` base), con la aprobación de los contratos de la Ola 0
* **Fecha:** 2026-11-07
* **Autor:** eduar.troyano
* **Fuente:** [plan de implementación v3](../../PLAN_IMPLEMENTACION_V3.md), secciones 5.2.1 (`ai_jobs`), 5.3.3, 5.4.1 a 5.4.3
* **Relacionados:** [ADR 0001](0001-postgres-pgvector.md), [ADR 0008](0008-ai-service-architecture.md), [ADR 0009](0009-data-ownership-api-and-ai.md)

---

## 1. Contexto

Las tareas de IA tardan desde segundos hasta minutos (estructurar un syllabus, generar el contenido de un curso, calificar respuestas cortas). Las pantallas de v3 ya prevén estados de carga y de error (U1x, D1c) con el mensaje «tu avance está guardado». Hace falta:

- encolar trabajos y no repetirlos si el usuario reintenta;
- un proceso que los ejecute con reintentos;
- una forma de que el resultado llegue a las tablas de negocio, que solo escribe la API ([ADR 0009](0009-data-ownership-api-and-ai.md)).

El proyecto ya tiene PostgreSQL; un piloto de 15 a 30 aprendices no justifica más infraestructura.

## 2. Decisión

1. **La cola es la tabla `ai_jobs`** (`job_type`, `status`, `idempotency_key` único, `input`, `result`, `error_code`, `error_message`, `attempts`, `requested_by`, referencias a curso, tema e inscripción, `started_at`, `finished_at`, `locked_until`). **Sin broker** (ni Redis, ni RabbitMQ, ni Celery).
2. **El proceso `ai-worker`** toma trabajos con `SELECT … FOR UPDATE SKIP LOCKED` y un bloqueo con vencimiento (`locked_until`).
3. **Idempotencia:** la API crea el trabajo con `idempotency_key = <tarea>:<entidad>:<id>:<versión>`; la misma clave devuelve el mismo trabajo.
4. **Síncrono solo lo rápido** (menos de 3 s, sin LLM o con uno pequeño): `levels.estimate`, `path.sequence` y `video.rank`. Todo lo demás es asíncrono y la API responde 202 con el `job_id`.
5. **Ingesta por consulta (pull):** la pantalla de carga consulta `GET /api/v1/jobs/{id}` cada 2 s; si el trabajo terminó, la API valida el resultado contra el contrato y lo escribe en una transacción idempotente (si ya se ingirió, no repite). Un barrido en el `lifespan` de la API, cada 60 s, ingiere los trabajos terminados que nadie consultó (por ejemplo, la generación del contenido de un curso).
6. **Errores:** `ai/` responde RFC 9457; la API traduce `failed` a 502 `AI_TASK_FAILED` con `retryable` y `budget_exceeded` a 503 `AI_BUDGET_EXCEEDED`. `POST /v1/jobs/{id}/retry` solo aplica a trabajos `failed` y reintentables.

## 3. Alternativas descartadas

- **Broker de mensajes (Redis, RabbitMQ) con Celery:** más piezas que operar y respaldar, sin beneficio con el volumen del piloto.
- **Ingesta por empuje (push o webhook de `ai/` a la API):** `ai/` necesitaría credenciales para llamar a la API, y la ingesta quedaría fuera del flujo de reglas de la API.
- **Tareas en segundo plano dentro de la API** (`BackgroundTasks`): se pierden si el proceso se reinicia y no tienen reintentos ni estado consultable.

## 4. Consecuencias

- **Positivas:** una sola tecnología de datos; los trabajos sobreviven a reinicios y se respaldan con la base; el estado se consulta y se audita; la API no necesita exponer endpoints internos.
- **Negativas y pendientes:**
  - La consulta periódica agrega carga; con 15 a 30 aprendices es despreciable, pero no escala sin ajustes.
  - Un trabajo terminado que nadie consulta tarda hasta 60 s en verse.
  - Si el volumen crece en cohortes posteriores, se reconsidera un broker sin cambiar el contrato HTTP.
