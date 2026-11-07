# Contrato HTTP del servicio de IA (`ai/`, v1)

Estado: **borrador de la Fase 1** (rama `feature/prompts-and-contracts`). Lo implementa `ai/` en las Fases 4 y 5 y lo consume la API a través del puerto `AiServicePort` (`ai_gateway`, plan 5.3.1). Fuentes: plan 5.3.3, 5.4.2, 5.4.3, 5.4.11 a 5.4.13. Los cuerpos de salida son los contratos de `prompts/schemas/*.v1.json`; los errores, los de `docs/contracts/error-codes.md`.

## 1. Reglas generales

| Tema | Regla |
| --- | --- |
| Base | `http://ai:8030` en la red de compose; en local también `localhost:${AI_PORT}` solo para Swagger. En producción no publica puerto |
| Prefijo | `/v1` para todo menos `GET /health` y `GET /ready` |
| Autenticación | `Authorization: Bearer <token>` obtenido por la API con *client credentials* (cliente `smartmentor-api-service`, audiencia `AI_SERVICE_AUDIENCE` = `smartmentor-ai`). `ai/` lo valida con el JWKS de Keycloak (misma lógica del ADR 0004). Sin token o inválido: `401 MISSING_TOKEN` / `INVALID_TOKEN` |
| Trazabilidad | La API reenvía `X-Request-ID`; `ai/` lo devuelve y lo escribe en sus registros junto con `job_id` |
| Formato | JSON UTF-8. Errores en `application/problem+json` (RFC 9457) con `code` y `request_id` |
| Fechas | ISO 8601 en UTC (`2026-11-07T15:00:00Z`) |
| Identificadores | `job_id` es un UUID. `topic_id`, `outcome_id`, `item_id` en los contratos son cadenas opacas: `ai/` devuelve las que recibió (la API envía el id de la base como texto, `"12"`). Solo `syllabus.structure` inventa claves (`topics.extraction_key`) |
| Datos personales | La API nunca envía nombre, correo ni ids de usuario. El perfil y la hoja de vida llegan seudonimizados en `profile_text` y `resume_text` (DEF-05, plan 5.4.12) |
| Lectura de la base | `ai/` lee por referencia lo que su usuario de base puede leer (`courses`, `topics`, `learning_outcomes`, `syllabus_documents`, sus tablas `ai_*`, `document_chunks`, `source_documents`). Todo lo demás (respuestas, rúbricas, ítems previos, perfil) va en el `input` |
| Escritura | `ai/` solo escribe sus tablas (`ai_jobs`, `ai_generation_cache`, `ai_embeddings`, `document_chunks`, `source_documents`, `llm_call_logs`). Nunca escribe tablas de negocio: la API ingiere el `result` (modelo *pull*, plan 5.3.3) |

## 2. Rutas

| Método y ruta | Uso | Respuestas |
| --- | --- | --- |
| `POST /v1/jobs` | Crea un trabajo asíncrono | `202` nuevo; `200` si la `idempotency_key` ya existía con el mismo cuerpo; `422 UNKNOWN_JOB_TYPE`, `INVALID_JOB_INPUT`, `IDEMPOTENCY_KEY_REUSED` |
| `GET /v1/jobs/{job_id}` | Estado y resultado | `200`; `404 JOB_NOT_FOUND` |
| `POST /v1/jobs/{job_id}/retry` | Reencola un trabajo `failed` con `retryable=true` | `202`; `404`; `409 JOB_NOT_RETRYABLE` |
| `GET /v1/jobs?status=&job_type=&course_id=&limit=&offset=` | Lista para observabilidad (AD2) | `200` paginado |
| `POST /v1/tasks/levels.estimate` | Síncrona (< 3 s): nivel por tema | `200` `diagnostic_result.v1`; `422`; `503 BUDGET_EXCEEDED` |
| `POST /v1/tasks/path.sequence` | Síncrona, sin LLM: pasos de la ruta | `200` `learning_path.v1`; `422 PREREQUISITE_SELF`, `VALIDATION_ERROR` |
| `POST /v1/tasks/video.rank` | Síncrona: reordena candidatos ya caracterizados | `200` `video_resource.v1`; `422` |
| `GET /v1/prompts` | Catálogo con versiones (C4) | `200` |
| `GET /v1/prompts/{prompt_id}` | Un prompt con todas sus versiones | `200`; `404 PROMPT_NOT_FOUND` |
| `GET /health` | Vida del proceso | `200 {"status":"ok"}` |
| `GET /ready` | Base, carga de prompts (hashes de `catalog.yaml`) y precio para cada modelo configurado | `200`; `503 NOT_READY` con `missing` |

### 2.1 `POST /v1/jobs`

Petición:

```json
{
  "job_type": "items.generate_quiz_bank",
  "idempotency_key": "items.generate_quiz_bank:topic:12:v3",
  "input": {
    "topic_id": "12",
    "n_multiple_choice": 4,
    "n_short_answer": 1,
    "previous_stems": []
  },
  "refs": {"course_id": 3, "topic_id": 12, "enrollment_id": null},
  "requested_by": "api"
}
```

| Campo | Tipo | Regla |
| --- | --- | --- |
| `job_type` | cadena | Uno de la tabla 3 |
| `idempotency_key` | cadena ≤ 200 | `<job_type>:<entidad>:<id>:<versión>` (plan 5.3.3). Único en `ai_jobs.idempotency_key` |
| `input` | objeto | Esquema del `job_type` (tabla 3) |
| `refs` | objeto | `course_id`, `topic_id`, `enrollment_id` (enteros o `null`): se guardan en `ai_jobs` para filtrar costos y presupuesto (AD2). No se envían al LLM |
| `requested_by` | cadena | `api` o `eval` |

Respuesta `202` (o `200` si ya existía):

```json
{"job_id": "0b8e3c1e-6a4f-4f51-9a39-7d2a1f0c9e11", "job_type": "items.generate_quiz_bank", "status": "queued", "created_at": "2026-11-07T15:00:00Z"}
```

**Idempotencia.** La misma `idempotency_key` con el mismo `job_type` e `input` devuelve el trabajo existente (cualquiera sea su estado) con `200`; con otro cuerpo, `422 IDEMPOTENCY_KEY_REUSED`. La API incluye la versión de lo que cambia (versión del recurso, número de intento, hash del documento) en la clave, así que una regeneración pedida a propósito usa otra clave. El reintento de un trabajo fallido se pide con `/retry`, no con una clave nueva.

### 2.2 `GET /v1/jobs/{job_id}`

```json
{
  "job_id": "0b8e3c1e-6a4f-4f51-9a39-7d2a1f0c9e11",
  "job_type": "items.generate_quiz_bank",
  "status": "succeeded",
  "contract": "assessment_item_bank.v1",
  "result": {"topic_id": "12", "items": ["…"], "item_reviews": ["…"], "discarded_item_ids": ["q3"], "meta": {"…": "…"}},
  "error": null,
  "attempts": 1,
  "cost_usd": 0.0042,
  "refs": {"course_id": 3, "topic_id": 12, "enrollment_id": null},
  "created_at": "2026-11-07T15:00:00Z",
  "started_at": "2026-11-07T15:00:01Z",
  "finished_at": "2026-11-07T15:00:09Z"
}
```

| Campo | Regla |
| --- | --- |
| `status` | `queued` → `running` → `succeeded` o `failed`; `failed` → `queued` con `/retry` (plan 5.1) |
| `contract` | Nombre y versión del contrato de `result` (tabla 3) |
| `result` | Solo con `succeeded`; cumple `prompts/schemas/<contract>.json`. La API lo vuelve a validar al ingerirlo (`502 AI_RESULT_INVALID` si no cumple) |
| `error` | Solo con `failed`: `{"code": "INVALID_OUTPUT", "message": "…", "retryable": true}` (códigos en `error-codes.md`) |
| `attempts` | Ejecuciones del trabajo (no llamadas al LLM: esas van en `llm_call_logs`) |
| `cost_usd` | Suma de `llm_call_logs.cost_usd` del trabajo; `null` si algún modelo no tiene precio |

La API consulta cada 2 s mientras la pantalla de carga está abierta y un barrido cada 60 s ingiere los trabajos que nadie consultó (plan 5.3.3). La API traduce `failed` a `502 AI_TASK_FAILED` (con `retryable`) y `BUDGET_EXCEEDED` a `503 AI_BUDGET_EXCEEDED`.

### 2.3 Lista paginada

`GET /v1/jobs` devuelve `{"items": [<job sin result>], "total": 42, "limit": 20, "offset": 0}`; `limit` por defecto 20, máximo 100.

## 3. Tipos de trabajo (`job_type`)

Cada entrada lista el `input` y el contrato de `result`. Las tareas que llaman al LLM usan el prompt indicado (ver `prompts/catalog.yaml`).

| `job_type` | Prompt(s) | `input` | `result` (contrato) | Caché | Pantallas |
| --- | --- | --- | --- | --- | --- |
| `syllabus.structure` | `syllabus_structuring` | `{syllabus_document_id: int}` | `syllabus.v1` | SHA-256 del texto | D1c, D2 |
| `course.generate_content` | orquesta los de abajo | `{course_id: int, learning_path_id: int, quiz_items_per_topic: int = 23, final_versions: int = 2}` | `{"jobs": [{"job_id", "job_type", "topic_id"}]}` | por curso y versión | D2 «Aprobar y publicar» |
| `embeddings.index_course` | — | `{course_id: int}` | `{"topics_indexed": int, "chunks_indexed": int, "embedding_model": str}` | por contenido | — |
| `diagnostic.generate_items` | `diagnostic_generation` + `item_review` | `{course_id: int}` | `assessment_item_bank.v1` (`source=diagnostic`) | por curso | E3 |
| `items.generate_quiz_bank` | `topic_quiz` + `item_review` | `{topic_id: str, n_multiple_choice: int, n_short_answer: int, previous_stems: [str]}` | `assessment_item_bank.v1` (`source=topic_quiz`, `topic_id` fijo) | por tema | E6b, E6c, U1b |
| `items.generate_final_bank` | `final_assessment` + `item_review` | `{learning_path_id: int, topic_ids: [str], n_short_answer: int, n_versions: int, previous_stems: [str]}` | `assessment_item_bank.v1` (`f<n>_v1` → `final`, `f<n>_v2…` → `retention`; mismo `equivalence_group`) | por ruta | E8, E14 |
| `items.review` | `item_review` | `{items: [{item_id, item_type, bloom_level, stem, options, correct_option, rubric, outcome}]}` | `item_review.v1` | por ítem | D5 |
| `content.explain_topic` | `topic_explanation` + `rag_faithfulness` | `{topic_id: str}` | `topic_explanation.v1` (`kind=main`, `audience=all_learners`, con `faithfulness`) | **por tema, compartido** | E6, D5 |
| `content.check_faithfulness` | `rag_faithfulness` | `{topic_id: str, text: str, source_ids: [str]}` | `faithfulness_check.v1` | por versión del texto | D5d |
| `content.remedial` | `remedial_explanation` + `rag_faithfulness` | `{topic_id: str, level: float, profile_text: str, failed_items: [{stem: str, learner_answer: str}]}` | `topic_explanation.v1` (`kind=remedial`, `audience=enrollment`) | sin caché entre aprendices | E7b |
| `content.personal_example` | `personalized_example` | `{topic_id: str, profile_text: str}` | `personalized_example.v1` | por inscripción (P2) | E6 |
| `video.collect_candidates` | — | `{topic_id: str, language: "es", instructor_videos: [{youtube_video_id, title}]}` | `video_resource.v1` | por tema | D5e |
| `diagnostic.finalize` | `learning_objective` (si `objective_mode=llm`) | ver 3.1 | `diagnostic_finalization.v1` | por inscripción | U1a, E4 |
| `grading.short_answer` | `short_answer_grading` | `{item_id: str, stem: str, model_answer: str, rubric: [{criterion, points}], answer_text: str, min_criteria_ratio: float}` | `grading.v1` (`grader=llm_judge`) | **sin caché** | U1c, U1d, E7 |
| `badge.compose_text` | `badge_text` | `{course_name: str, objective_statement: str, topic_names: [str], final_pass_threshold: int}` | `badge_text.v1` | por ruta | E10 |
| `eval.run_pipeline` | todos (incluido `simulated_learner`) | `{syllabus_document_id: int, simulated_profiles: [str], live: bool}` | `{"output_dir": str, "metrics": {…}}` (solo evaluación) | — | — |

Reglas de las tareas con LLM (plan 5.4.4): esquema `…LLM` como salida estructurada → `model_validate_json` → `check_*` de `ai/app/domain/contracts/validation.py` → hasta 2 reintentos con los problemas en el prompt → `error.code = INVALID_OUTPUT`. Los ítems sin una sola respuesta correcta según `item_review` van en `discarded_item_ids` y la API los guarda como `auto_rejected` (L-03).

### 3.1 `diagnostic.finalize`

```json
{
  "topic_ids": ["10", "11", "12"],
  "items": [{"item_id": "301", "topic_id": "10", "item_type": "multiple_choice", "difficulty": 1, "correct_option": 1}],
  "answers": [{"item_id": "301", "selected_option": 1, "dont_know": false, "text_answer": null}],
  "profile_text": "Analista de datos en logística; uso Excel, SQL y Power BI…",
  "resume_text": "education_level: undergraduate; job_title: analista de datos; tools: SQL, Excel, Power BI",
  "weights": {"test": 0.8, "profile": 0.1, "resume": 0.1},
  "thresholds": {"mastery_skip_threshold": 80, "reinforce_cutoff": 50},
  "objective_mode": "llm",
  "path_objective": "Construir, evaluar y comparar modelos supervisados básicos…"
}
```

`answers[]` usa la forma de `LearnerAnswer` (`simulated_answers.v1`). «No lo sé» cuenta como no acierto. Si falta `profile_text` o `resume_text`, su peso se redistribuye proporcionalmente entre las señales presentes (`diagnostic_result.v1` → `level_by_topic[].weights`). Con `objective_mode = "path_default"` no se llama al LLM y el objetivo sale de `path_objective` con `origin = path_default` y `meta = null` (en ese caso la API envía además `path_objective_parts: {bloom_verb, content, criterion}`).

## 4. Tareas síncronas

Responden en menos de 3 s y no crean filas en `ai_jobs` (sí en `llm_call_logs` si llaman a un modelo de embeddings).

### 4.1 `POST /v1/tasks/levels.estimate`

Cuerpo: el mismo de 3.1 sin `objective_mode` ni `path_objective`. Respuesta: `diagnostic_result.v1` (ejemplo en `prompts/examples/diagnostic_result.json`).

### 4.2 `POST /v1/tasks/path.sequence`

```json
{
  "topics": [
    {"topic_id": "10", "position": 1, "prerequisites": [], "is_mandatory": false},
    {"topic_id": "11", "position": 2, "prerequisites": ["10"], "is_mandatory": false},
    {"topic_id": "12", "position": 3, "prerequisites": ["10", "11"], "is_mandatory": false}
  ],
  "level_by_topic": [{"topic_id": "10", "level": 95.5}, {"topic_id": "11", "level": 64.4}, {"topic_id": "12", "level": 4.4}],
  "mastery_skip_threshold": 80,
  "focus_topic_ids": ["12"],
  "pilot_arm": "personalized"
}
```

Respuesta: `learning_path.v1`. Reglas (plan 5.4.8): orden topológico que respeta `position` cuando el DAG lo permite; `skipped` (`skipped_mastered`) si nivel ≥ umbral y no es obligatorio; `blocked` si tiene prerrequisitos no completados; el primero disponible queda `pending`; con `pilot_arm = "fixed"` se incluyen todos con `fixed_path`. Motivo de inclusión por prioridad: `mandatory` > `objective_focus` > `weak_prerequisite` (es prerrequisito de un tema incluido) > `required_by_path`.

### 4.3 `POST /v1/tasks/video.rank`

Cuerpo: `{"topic_id": "12", "candidates": [<VideoCandidate de video_resource.v1 sin rank>], "preferences": {"language": "es", "min_duration_seconds": 240, "max_duration_seconds": 1800, "english_allowed": false}}`. Respuesta: `video_resource.v1` con `rank` 1..n, `selected_video_id` y hasta dos `backup_video_ids`.

## 5. Catálogo de prompts (`GET /v1/prompts`)

```json
{
  "schema_version": "v1",
  "prompts": [
    {
      "id": "topic_quiz",
      "name_es": "Banco del quiz del tema",
      "task": "items.generate_quiz_bank",
      "current_version": 1,
      "model_tier": "default",
      "temperature": 0.6,
      "output_schema": "llm/assessment_items_llm.v1.json",
      "contract": "assessment_item_bank.v1.json",
      "screens": ["E6b", "E6c", "U1b", "D5"],
      "versions": [{"version": 1, "sha256": "bc3a91…", "calls": 12, "invalid_output_rate": 0.0}]
    }
  ]
}
```

Sale de `prompts/catalog.yaml` más los agregados de `llm_call_logs`. `GET /v1/prompts/{id}` agrega `system` y `user` de cada versión.

## 6. Presupuesto, caché y registro

- `BudgetGuard` revisa antes de cada llamada `AI_DAILY_BUDGET_USD`, `AI_COURSE_BUDGET_USD` (por `refs.course_id`) y `AI_ENROLLMENT_BUDGET_USD` (por `refs.enrollment_id`). Si se supera, el trabajo termina `failed` con `BUDGET_EXCEEDED` y `retryable=false`.
- Caché: `ai_generation_cache.cache_key` = SHA-256 de modelo + tarea + versión del prompt + system + prompt renderizado + nombre del esquema (notebook v2). No se usa en `grading.short_answer`, `content.remedial` ni `content.personal_example`. Una salida de caché lleva `meta.from_cache = true`.
- Cada intento de llamada deja una fila en `llm_call_logs` (`ai_job_id`, `provider`, `task`, `prompt_id`, `prompt_version`, `input_sha256`, `json_valid`, `call_attempt`, `from_cache`, `cost_usd`, `latency_ms`, `status`).

## 7. Cambios futuros

Un cambio incompatible en un contrato crea `<contrato>.v2.json` y el `job_type` declara qué versión devuelve (`contract`). La API acepta ambas durante la transición. Un prompt nuevo no cambia este contrato.
