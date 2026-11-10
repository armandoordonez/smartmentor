# Bitácora F03b · API v2: rutas, evaluaciones y rutas del aprendiz

Rama: `feature/api-v2-paths-assessments` (desde `origin/dev`, con `origin/dev` fusionada después de integrar `api-content`). Agente: `api-paths` (Fase 3, segunda parte).

## Hecho

- **`learning_paths`**: modelos y repositorios de `enrollments`, `path_steps`, `attempt_grants` y `alerts`; máquinas de estados puras (`states.py`: inscripción, paso con `on_hold`, intento, disponibilidad no lineal y `next_action`); catálogo de rutas publicadas; inscripción con consentimiento obligatorio; `path.sequence` síncrono; ajustes de la ruta con `409 PILOT_RUNNING`; tablero (KPI, aprendices, matriz de dominio, temas críticos); detalle del aprendiz (perfil reducido A3c); intentos extra de tema y de final; alertas; administración de inscripciones (AD5: listar, inscribir, retirar, mover). Una inscripción posterior al sorteo del piloto recibe brazo (el de menos inscripciones) si tiene consentimiento del piloto.
- **`assessments`**: diagnóstico desde el banco aprobado (hasta 3 ítems por tema), guardado parcial, entrega `202` con `diagnostic.finalize`, resultado; objetivo en tres partes (`422 OBJECTIVE_NOT_MEASURABLE` con `missing`); contenido del paso (explicación aprobada, video en uso o respaldo, reglas, intentos); intentos con ítems no vistos (5 por intento, a lo sumo una respuesta corta) y `202` con `items.generate_quiz_bank` si se agota el banco; opción múltiple por regla; respuesta corta con `grading.short_answer` y aprobación por proporción de criterios; resultado con rúbrica y `next_action`; revisión humana (alerta); final (solo con todos los pasos `passed`/`skipped`, ítems repartidos por tema); plan de repaso; badge Open Badges 2.0 «hosted» (receptor `sha256(correo+sal)`, imagen PNG generada sin dependencias, URL por `public_id`); `ProfileChangeListener` enchufado (devuelve los ids reales en `recalculated_enrollment_ids`); ingestores idempotentes de `diagnostic.finalize`, `grading.short_answer` e `items.generate_quiz_bank` (bajo demanda).
- **`learner`**: todas las rutas `/me` del aprendiz, encuesta final con `sus_score`, eventos de tiempo en tarea (`interaction_events`, SQL explícito), y las rutas que pidió la app (F07b): historial de intentos de tema y de final, metas personales (`GET`/`PUT /me/study-goals`) y los campos `topic_name`, `bloom_level` y `rubric_summary` de los ítems.
- **Pendientes de F03c resueltos**: brazo del piloto tras el sorteo; la alerta `review_requested` queda leída al guardar la calificación humana a solicitud (puerto opcional `ReviewAlerts` en `evaluation.GradingService`); `PublicationService` encola `diagnostic.generate_items` al publicar.
- **Comunes (cambio mínimo)**: `IdempotencyRunner.run(status_of=…)` (200/201/202 según el resultado), registro de routers e ingestores, `FakeAiService` con `levels.estimate`, `path.sequence`, `diagnostic.finalize` y `grading.short_answer` deterministas (`ai_gateway/fake_learning.py`), `Settings.badge_issuer_*`, `JobType.DIAGNOSTIC_GENERATE_ITEMS`, cobertura con `concurrency = greenlet`, `scripts/check-env-coherence.py` (las variables del badge ya se usan).
- **Contratos**: `docs/contracts/api-v2.md` (rutas y esquemas nuevos), OpenAPI y Postman regenerados (116 peticiones, 16 carpetas).
- Commits en la rama: `wip(api)…` ×2, `feat(api): agrega las rutas del aprendiz…`, `test(api)…` ×4, `feat(api): integra dev…` y el cierre (ver `git log`).

## Desviaciones frente al plan o al brief

- **Ids enteros en las rutas** (como F03a y el contrato `api-v2.md`): «`public_id` en rutas» se aplicó a lo público (la verificación del badge). El resto se protege con la matriz de propiedad (404, nunca 403).
- **Sin columna para el `job_id`**: `diagnostics` y `attempt_answers` no guardan el trabajo. Cada trabajo usa una `idempotency_key` determinista y una entrada reconstruible (la de `diagnostic.finalize` se guarda en `enrollments.profile_snapshot`); para recuperar el `job_id` se repite el envío, que `ai/` resuelve como el mismo trabajo. Esto hace un `POST /v1/jobs` idempotente al leer una inscripción que espera un trabajo.
- **Banco bajo demanda aprobado**: los ítems de `items.generate_quiz_bank` pedidos por un aprendiz (U1b) entran `approved` (marcados `on_demand` en `auto_review`) para no dejarlo esperando la revisión; los generados al publicar los ingiere `content` como `pending_review`.
- **Final sin ítems no vistos**: `409 CONFLICT` (no se genera la final bajo demanda; `items.generate_final_bank` lo encola el contenido).
- **Reintento de `grading_failed`**: no hay ruta en el contrato; el intento queda `grading_failed` y el reintento queda para la Fase 6 (`POST /v1/jobs/{id}/retry` no está en el puerto).
- **Intentos de `retention`** en un paso: `422` (P2; además el `CHECK` de la base exige `path_step_id` nulo para `retention`).
- `view_attempt_result` de `next_action` no se emite: no hay dónde guardar «resultado visto».
- `GET /jobs/{id}` sigue devolviendo `next_action: null` (lo arma `ai_gateway`; la app usa `GET /me/enrollments/{id}`).
- `POST /me/video-feedback` lo entregó `content` (F03c).

## Decisiones

- `next_action` se calcula con una función pura sobre `ProgressFacts`; el dominio de evaluaciones los arma (puertos `ProgressReader` y `AssessmentHistory`) para no crear dependencias circulares.
- Una inscripción nueva pasa de `enrolled` a `profiling` (sin descripción) o a `diagnosing` (con descripción) en la misma operación; guardar la descripción mueve las `profiling` a `diagnosing` (vía `ProfileChangeListener`).
- Recalcular por cambio de perfil solo toca pasos sin empezar (`skipped`, `blocked`, `pending`, `on_hold` con 0 intentos); lo cursado no cambia.
- `short_answer_min_ratio` se usa como la proporción de aprobación del contrato (2/3); la entidad la siembra en 0,667 al crear la ruta (la base trae 0,200 por defecto con otra semántica: ver cambios pedidos). Se compara con tolerancia de 0,001 porque la base guarda 3 decimales.
- Los pesos del nivel se normalizan a fracciones (la base los siembra en porcentaje 80/10/10).
- Destinatario de las alertas: el dueño del curso; si está «Sin asignar», el primer administrador activo.
- Brazo tras el sorteo: el de menos inscripciones (empate: `personalized`); sin consentimiento del piloto, sin brazo y fuera del análisis.
- El `FakeAiService` responde `failed` (`INPUT_REFERENCE_NOT_FOUND`) a `diagnostic.generate_items` sin `topic_ids`: el fake no lee la base y el contrato solo manda `course_id`.
- Los modelos de tablas compartidas: `assessment_items` se importa de `content`; `survey_responses` se declara aquí con `extend_existing`; `resources`, `video_candidates`, `pilots` e `interaction_events` se leen o escriben con SQL explícito.

## Problemas y lecciones

- La cobertura de `pytest-cov` no contaba el código después de cada `await` sobre la base (SQLAlchemy asíncrono corre en greenlets): `assessments/service.py` aparecía al 41 %. Con `concurrency = ["greenlet", "thread"]` sube al 87 % y el total al 96 %.
- `numeric(4,3)` redondea 2/3 a 0,667 y `2/3 >= 0,667` es falso: hizo falta tolerancia.
- El ingestor de bancos de `content` y el mío compiten por `items.generate_quiz_bank`: el registro es un diccionario por tipo; el mío se registra después y delega en el de contenido los trabajos sin `enrollment_id`.
- El aislamiento del worktree rechaza comandos con `$(...)`, bucles o `sh -c`: los comandos van en scripts de la carpeta temporal.
- La máquina se reinició a mitad del trabajo (contenedor detenido, carpeta temporal borrada): el script de la base ahora hace `docker start` y es idempotente.

## Métricas

- Suite completa de `api` contra el esquema real (PostgreSQL desechable `pgvector:0.8.7-pg17`, 51 changesets con Liquibase), tras fusionar `dev`: **641 en verde**, cobertura de `app` **96 %** (8.805 sentencias). Del alcance de esta parte: `learning_paths/service.py` 92 %, `assessments/service.py` 87 %, `learner/controller.py` 98 %, `states.py` 99 %.
- Pruebas nuevas: 7 unitarias de servicios en memoria, ~200 de máquinas de estados (todos los caminos y todas las transiciones prohibidas), 20 de calificación y badge, 16 de contrato del fake, 43 de integración (flujo completo inscripción → badge → encuesta, matriz de propiedad de 19 rutas del aprendiz y 5 del instructor, tablero, ajustes, alertas, AD5, banco bajo demanda, barrido, fallo de calificación, rutas de la app y pendientes de F03c).
- **Mínimo privilegio**: con la API conectada como `smartmentor_api` (y la limpieza con otro usuario, `TEST_SETUP_DATABASE_USER`), las 39 pruebas de la ruta que había entonces pasan; de toda la integración fallan solo 2 de F03a que leen tablas `_audit` desde la prueba (el usuario de la API no puede, por diseño).
- Ruff (`check` y `format --check`) y mypy estricto sin errores (140 archivos). Código propio: ~7.000 líneas en `app/domains/{learning_paths,assessments,learner}` y `fake_learning.py`; ~2.200 en pruebas.

## Impacto en el brief

- Ruta del aprendiz: el banco revisado reemplaza «preguntas regeneradas en cada intento» (B-02); el aprendiz nunca repite una pregunta y, si se agota el banco, se genera bajo demanda (U1b).
- Reglas medibles: aprobación de respuesta corta por proporción de criterios (2 de 3), intentos extra reportados aparte, avance no lineal (`on_hold`), final solo con la ruta completa, badge verificable sin datos personales.
- Métricas del brief: tiempo en tarea (`interaction_events`), SUS en la encuesta final, tablero del instructor con aprobación al primer intento y temas críticos.

## Qué falta / pendiente

- Reintento de una calificación `grading_failed` (necesita `POST /v1/jobs/{id}/retry` en el puerto).
- `content.remedial` y `content.personal_example` no se encolan desde el intento (la ruta lee el recurso si existe).
- La nota del retiro (`withdraw`) y el comentario de la revisión no se guardan (sin columna).
- Política de inactividad que pasa a `abandoned` (decisión del piloto); no hay ruta para que el aprendiz abandone.
- `next_action` del `GET /jobs/{id}`.

## Cambios pedidos a archivos compartidos

- **Base (`database/`)**: `learning_paths.short_answer_min_ratio` trae `DEFAULT 0.200` y el comentario dice «proporción mínima de ítems de respuesta corta», pero el contrato la usa como proporción de criterios para aprobar (DEF-21): cambiar el default a `0.667` y el comentario. `level_weights` se siembra en porcentaje (80/10/10) y `ai/` espera fracciones (la API normaliza). Columnas útiles: `diagnostics.ai_job_id` y `attempt_answers.ai_job_id` (o una tabla de trabajos por entidad) para no repetir envíos, `alerts.note` y `enrollments.withdrawal_note`.
- **`.env.example` / `docker-compose.yml`**: pasar `BADGE_ISSUER_NAME` y `BADGE_ISSUER_URL` al servicio `api`.
- **`ai/`**: aceptar `include_diagnostic` sigue apagado; la API encola `diagnostic.generate_items` con `{course_id}`.
- **Pruebas de F03a** (`test_first_login_is_audited_as_the_identity`, `test_the_admin_assigns_several_roles_and_the_change_is_audited`): leen `_audit` con el motor de la API; para correr toda la suite como `smartmentor_api` deberían usar `setup_engine`.
