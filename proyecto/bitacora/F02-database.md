# Bitácora F02 · Base de datos `v2.0.0`

Rama: `feature/database-v2-rebase` (desde `origin/dev`). Agente: `database` (Ola 1). Fase 2 del plan (sección 7).

## Hecho

Entregado en cuatro commits (con `push` en cada grupo, como pidió el dueño; el grupo A salió primero para la API):

| Commit | Contenido |
| --- | --- |
| `0ab0d53` | Grupo A (identidad y cursos): retira `v1.0.0` y `v1.0.1`, funciones comunes (`audit_row_change`, `set_updated_at`), tablas `roles`, `users`, `user_roles`, `user_profiles`, `consents`, `data_subject_requests`, `courses`, `syllabus_documents`, `topics`, `learning_outcomes`, `topic_prerequisites`, `course_evaluators`, `ai_jobs`, `syllabus_extractions`, y las semillas de roles y del administrador |
| `103a0df` | Grupo B: `learning_paths`, `enrollments`, `diagnostics`, `path_steps`, `attempt_grants`, `assessment_items`, `assessment_attempts`, `attempt_answers`, `item_annotations`, `human_gradings` |
| `29813be` | Grupo C: `video_candidates`, `resources`, `video_relevance_judgments`, `video_feedback`, `badges`, `pilots`, `survey_responses`, `alerts`, `interaction_events`, `study_goals` |
| `26c121b` | Grupo D: `ai_generation_cache`, `ai_embeddings` (`vector(768)` + HNSW), `source_documents`, `document_chunks`, `llm_call_logs`; las tres vistas; permisos de `smartmentor_api` y `smartmentor_ai`; etiqueta `v2.0.0`; bootstrap con roles |
| (último commit de la rama) | `reset-app-schema.sh`, `database/README.md` (modelo y ER en Mermaid), `liquibase/README.md`, esta bitácora |

- 39 tablas (34 con `_audit`), 3 vistas, 50 changesets, etiqueta `v2.0.0`. Etiqueta git **local** `schema-v1-final` sobre `8bb1828` (último commit con v1); no se publicó.
- Los archivos de tablas se generaron con un script desechable (no se versiona) para mantener el estilo uniforme del changelog `v1.0.0` (ids `v2.0.0-NNN-<accion>`, `logicalFilePath`, `remarks` en inglés, rollback explícito).

## Validación (resultados reales)

Entorno: PostgreSQL desechable `pgvector/pgvector:0.8.7-pg17-bookworm` (contenedor `sm-database-pg`, red `sm-database-net`, puerto 15421) e imagen de Liquibase construida de `database/liquibase/Dockerfile`. No se usó `smartmentor-postgres` ni el `.env` del dueño.

| Comprobación | Resultado |
| --- | --- |
| `liquibase validate` | Sin errores (también con cada estado intermedio A, B y C) |
| `liquibase update` | 50 changesets aplicados; `SELECT tag ... WHERE tag IS NOT NULL` devuelve `v2.0.0` |
| `update-testing-rollback` | Correcto, con roles ausentes (permisos omitidos con aviso) y con roles presentes y Liquibase como `smartmentor_owner` |
| Rollback completo (`rollback-count --count=50`) | Deja solo `databasechangelog` y `databasechangeloglock` |
| `\dt` | 39 tablas esperadas + 34 `_audit` + 2 de control = 75 relaciones |
| Auditoría | Script con INSERT, UPDATE y DELETE sobre las 34 tablas con `_audit`: las 34 registran las tres operaciones, con `app_user_id` |
| Semillas | `learner`, `instructor`, `admin`; con `SEED_ADMIN_EMAIL=seed-admin@example.test` se crea el usuario con rol `admin`; sin la variable no se crea ninguno |
| CHECK, UNIQUE y trigger | 88 comprobaciones (CHECK de enumerados y de forma, únicos, trigger de `course_evaluators`, vector de dimensión incorrecta rechazado, HNSW presente, `updated_at` en 35 tablas, 22 `public_id`): 88 correctas, 0 fallidas |
| Permisos de `smartmentor_api` | Escribe tablas de negocio (y el trigger de auditoría funciona); lee `ai_jobs`, `llm_call_logs` y las vistas; **no puede** insertar ni actualizar `ai_jobs`, insertar ni borrar `llm_call_logs`, ni escribir `ai_generation_cache`, `document_chunks`, `source_documents`; no lee `ai_embeddings` ni `_audit`; no crea ni borra tablas |
| Permisos de `smartmentor_ai` | Escribe `ai_jobs`, `ai_embeddings`, `ai_generation_cache`, `source_documents`, `llm_call_logs` (solo inserción); lee `topics`, `learning_outcomes`, `courses`, `syllabus_documents`; **no puede** escribir `users`, `topics`, `courses`, `assessment_items`, leer `enrollments`, `users` ni `_audit`; no crea tablas |
| Bootstrap | Crea los tres roles, deja a `smartmentor_owner` como dueño de la base y crea `vector`; ejecutado dos veces sin error (idempotente) |
| `reset-app-schema.sh` | Con `--yes` recreó `smartmentor` y `smartmentor_test` (50 changesets en cada una, etiqueta `v2.0.0`, administrador sembrado); la base `keycloak` de prueba conservó su tabla marcadora; se niega (código 1) con `--db keycloak`, `--db postgres` y `--db <otra>`; sin terminal y sin `--yes` cancela con código 1 |
| `bash -n` sobre `reset-app-schema.sh` | Sintaxis correcta (no se corrió `shellcheck`: no está instalado) |

Las **148 pruebas actuales de la API van a fallar** con este esquema (usan `student`/`teacher`, `raw_syllabus`, columnas que salen, etc.): es lo esperado. Las reemplaza el agente de la API (Fase 3).

## Desviaciones frente al plan o al brief

- **`audit_row_change()` pasa a `SECURITY DEFINER`** (con `search_path` fijo) y registra `session_user` en lugar de `current_user`. Motivo: el ADR 0019 exige que los usuarios de servicio no escriban las tablas `_audit` fuera del trigger; sin esto habría que darles permisos sobre ellas.
- **`ai_embeddings` y las tablas sin `_audit`** llevan `active` y `created_at` aunque sean de solo inserción (regla común); solo `interaction_events`, `ai_generation_cache`, `document_chunks` y `llm_call_logs` omiten `updated_at`.
- **`llm_call_logs` conserva `model`, `input_tokens`, `output_tokens`, `error_message` y `enrollment_id`** de v1, además de las columnas nuevas del plan.
- **`ai_jobs.public_id`** es el `job_id` UUID del contrato de `ai/` (el contrato lo llama `job_id`). Se agregó `input_sha256` (detectar reutilización de la clave de idempotencia con otro cuerpo, contrato 2).
- **Dimensión del vector 768** (G-09, ADR 0012), no el 1024 del Anexo D. El compose tiene hoy `EMBEDDING_DIMENSION:-1024`.
- **Rol de solo lectura para el notebook de métricas** (cuarto usuario del ADR 0019): no se creó; la tarea pedía tres. Queda pendiente.
- **El grupo A incluyó las semillas** (rol y administrador) en su lista de inclusión; en el estado final están al final, después de permisos y antes de la etiqueta. Liquibase no se ve afectado (los ids no cambian de lugar entre estados).

## Decisiones

- **Generar los XML con un script** en lugar de escribir 39 archivos a mano: mismo estilo, menos errores. El script no se versiona (los XML son la fuente).
- **`public_id uuid`** en 22 tablas que la API puede exponer por id: `users`, `consents`, `data_subject_requests`, `courses`, `syllabus_documents`, `topics`, `learning_outcomes`, `ai_jobs`, `learning_paths`, `enrollments`, `diagnostics`, `path_steps`, `attempt_grants`, `assessment_items`, `assessment_attempts`, `attempt_answers`, `video_candidates`, `resources`, `badges`, `pilots`, `survey_responses`, `alerts`. Opción más simple: es barato y evita decidir tabla por tabla; si la API no lo usa, queda inerte. Quedan sin `public_id` las tablas puente o internas (`user_roles`, `topic_prerequisites`, `item_annotations`, `human_gradings`, etc.).
- **`ai_jobs.job_type` e `interaction_events.event_type` sin `CHECK`**: son listas abiertas (las define el contrato de `ai/` y la telemetría); un `CHECK` exigiría un changeset por cada tipo nuevo.
- **Estados que el plan no enumeraba** (se tomaron de 5.1 y de los contratos): `diagnostics.status` (`created`, `in_progress`, `submitted`, `scoring`, `scored`, `scoring_failed`), `data_subject_requests.status` (`pending`, `in_progress`, `resolved`, `rejected`), `video_candidates.status` y `origin` (de la tabla 5.2.1).
- **Valores por defecto de `learning_paths`**: umbrales 70/80/80 y 3 intentos (los del brief y de v1; se corrigió el 70/70/85 de la primera entrega del grupo B, que obliga a rehacer la base con `reset-app-schema.sh` a quien ya la haya aplicado); `level_weights = {"test": 80, "resume": 10, "profile": 10}`; `short_answer_min_ratio = 0.200` (C-09 no define el valor). La API o el administrador los fijan por ruta.
- **`difficulty` de 1 a 3** (la valida el contrato `ai/app/domain/contracts`).
- **`course_evaluators`**: el trigger rechaza asignar al dueño; que el usuario tenga rol `instructor` lo valida la API.
- **`validCheckSum ANY` en el administrador sembrado** y propiedad con valor por defecto vacío: un cambio posterior de `SEED_ADMIN_EMAIL` no rompe `update`. La variable se probó con el mismo nombre (`SEED_ADMIN_EMAIL`), sin prefijo `LIQUIBASE_`.
- **Reset con contenedor ajeno**: `reset-app-schema.sh` usa `docker compose` por defecto y, con `RESET_PG_CONTAINER` (+ `RESET_DOCKER_NETWORK`, `RESET_LIQUIBASE_IMAGE`), un Postgres aislado; así se pudo probar sin tocar el del dueño.
- **Vistas con filtro `active`** (sin borrar lógico no hay datos que contar).

## Problemas y lecciones

- `DROP EXTENSION vector` en el rollback de `001` falla si Liquibase corre como `smartmentor_owner` (la extensión es del administrador, pgvector no es de confianza). Corregido: el rollback atrapa `insufficient_privilege` y la deja en su sitio con un aviso.
- El rollback de las semillas fallaba si quedaba el administrador sembrado (clave foránea de `user_roles`) o si se hacía sin `SEED_ADMIN_EMAIL`. Se corrigió el de `046` (borra antes `user_roles` de esos roles); el de `047` sigue necesitando la misma variable (documentado).
- `now()` devuelve la hora de inicio de la transacción: dentro de una misma transacción `updated_at = created_at` aunque el trigger funcione. Se comprobó con transacciones separadas.
- En psql, `\gset` de un booleano deja `t`/`f`; hay que convertirlo con `::boolean` en el `WHERE`.
- El aislamiento del worktree impide ciertas construcciones de shell (sustituciones con `docker`); se usaron `--env-file` y scripts auxiliares.

## Métricas

- 50 changesets (48 archivos de changeset + versión) en `database/liquibase/changelog/v2.0.0/`, unas 3.800 líneas de XML; 39 tablas + 34 de auditoría + 3 vistas.
- 88 comprobaciones de restricciones y permisos, todas correctas; auditoría 34/34.
- Esfuerzo: una sesión; los 4 push del esquema se hicieron en el orden pedido (A primero).

## Impacto en el brief

- **Modelo de datos principal** (14 entidades): ahora son 39 tablas; el brief v2 debe sustituir el cuadro por el modelo de 5.2.1 y mencionar `ai_embeddings` con `vector(768)` y el banco de ítems.
- **Esquema evolutivo / un solo usuario de base**: ahora hay re-base `v2.0.0` (B-05, B-06) y tres usuarios de base de datos con mínimo privilegio (ADR 0019).
- **Roles**: `learner`, `instructor`, `admin`; «evaluador» es una asignación por curso (`course_evaluators`).
- **Datos personales**: tablas `consents` y `data_subject_requests`; `user_profiles` con campos neutros.

## Cambios pedidos a archivos compartidos

Para el agente `infra` (`docker-compose.yml` y `.env.example`; yo no los toqué):

1. **Servicio `postgres` del compose**: pasar al contenedor `OWNER_DATABASE_USER`, `OWNER_DATABASE_PASSWORD`, `API_DATABASE_USER`, `API_DATABASE_PASSWORD`, `AI_DATABASE_USER`, `AI_DATABASE_PASSWORD` (el bootstrap los lee con `\getenv`). Sin contraseña, el rol no se crea y el changeset de permisos lo omite con un aviso.
2. **Servicio `liquibase`**: usar `LIQUIBASE_COMMAND_USERNAME`/`PASSWORD` = `OWNER_DATABASE_USER`/`PASSWORD` (para que las tablas queden a nombre de `smartmentor_owner`), y agregar `SEED_ADMIN_EMAIL: ${SEED_ADMIN_EMAIL:-}`. `liquibase update` con otro usuario también funciona, pero los objetos quedan a nombre de ese usuario.
3. **Servicio `api`**: conectarse con `API_DATABASE_USER`/`API_DATABASE_PASSWORD` (hoy usa `DATABASE_USER`/`DATABASE_PASSWORD`). El servicio `ai` usará `AI_DATABASE_USER`/`AI_DATABASE_PASSWORD`.
4. **`EMBEDDING_DIMENSION`**: el compose tiene `:-1024` y el Anexo D del plan dice 1024; el esquema es **768** (ADR 0012, G-09). Cambiar ambos a 768.
5. **`.env.example`**: agregar `OWNER_DATABASE_USER=smartmentor_owner`, `OWNER_DATABASE_PASSWORD=` (vacía); ya existen `API_DATABASE_*`, `AI_DATABASE_*` y `SEED_ADMIN_EMAIL`. Los nombres de usuario por defecto deben seguir siendo `smartmentor_owner`, `smartmentor_api` y `smartmentor_ai` (el changeset 045 los usa fijos).
6. **Bases ya creadas** (volumen existente): los roles solo se crean con `./database/scripts/bootstrap.sh` (con las variables definidas) o con `./database/scripts/reset-app-schema.sh`; la imagen de Postgres no vuelve a correr `bootstrap/` con datos existentes.
7. **README raíz / HANDOFF / CHANGELOG** (los editan otros): mencionar `reset-app-schema.sh`, la etiqueta `schema-v1-final` y el paso v1 → v2.0.0 (las bases existentes se rehacen, no se migran).

Para el agente de la API: usar `public_id` (uuid) en las rutas públicas (badge) y, donde convenga, en las demás; `ai_jobs.public_id` es el `job_id` de `ai/`; las sesiones deben fijar `smartmentor.current_user_id` para la auditoría; `smartmentor_api` no tiene permiso sobre `_audit` ni sobre las tablas `ai_*` (salvo lectura de `ai_jobs` y `llm_call_logs`).

## Adenda: usuario `smartmentor_metrics` y notebook de métricas

- **Cuarto usuario del ADR 0019** (`smartmentor_metrics`, solo lectura). Se crea en el bootstrap con `METRICS_DATABASE_USER` (por defecto `smartmentor_metrics`) y `METRICS_DATABASE_PASSWORD` (sin contraseña, no se crea). El changeset `v2.0.0-049-db-role-metrics-grants` (incluido antes de la etiqueta, aunque su número sea posterior a 048 porque se agregó después de publicar 045) da `SELECT` solo sobre las 18 tablas que lee `notebooks/metrics_data.py` (`syllabus_extractions`, `topics`, `topic_prerequisites`, `item_annotations`, `attempt_answers`, `assessment_attempts`, `enrollments`, `human_gradings`, `video_relevance_judgments`, `video_candidates`, `user_profiles`, `badges`, `path_steps`, `diagnostics`, `survey_responses`, `llm_call_logs`, `ai_jobs`, `resources`) y las 3 vistas. Sin acceso a `users`, `consents`, `data_subject_requests` ni `_audit`.
- **Para `infra`**: agregar `METRICS_DATABASE_USER=smartmentor_metrics` y `METRICS_DATABASE_PASSWORD=` a `.env.example` y pasarlas al servicio `postgres` del compose. La URL del notebook (`METRICS_DATABASE_URL`) usa ese usuario.
- **Prueba**: cada consulta de `QUERIES` se ejecutó como `smartmentor_metrics` en transacción de solo lectura; 10 de 11 pasan (falla `path_steps`, ver abajo). INSERT, UPDATE, DDL y `SELECT` sobre `users`, `consents` y `users_audit` son rechazados.

### Los seis `SUPUESTO` del notebook frente al esquema real

| Supuesto del notebook | Esquema `v2.0.0` | Diferencia |
| --- | --- | --- |
| `path_steps.first_attempt_passed` | **No existe** | Hay `attempts_used`, `best_score`, `last_score`, `status`. El primer intento se calcula desde `assessment_attempts` (`attempt_number = 1`, `passed`) |
| `assessment_attempts.assessment_type` | Existe; valores `topic`, `final`, `retention` | Ninguna (`'final'` es correcto) |
| `video_candidates.rank` | Existe (`smallint`, nulo) | Ninguna |
| `ai_jobs.enrollment_id` | Existe, nulo, con FK a `enrollments` | Ninguna |
| Claves de `survey_responses.likert` (`satisfaction`, `usefulness`, `self_efficacy`) | `likert` es `jsonb` libre, sin esquema ni CHECK | El esquema no fija las claves; las define la API. A confirmar con su dueño |
| Forma de `diagnostics.level_by_topic` (objeto por tema con `test_score` de 0 a 1) | `jsonb` libre; el plan 5.2.1 describe `test_score`, `resume_prior`, `profile_prior`, `weights`, `level`, `classification` | Sin CHECK; el notebook usa `jsonb_each`, así que debe ser un objeto con el id del tema como clave. A confirmar con la API |

Diferencias adicionales (no marcadas como `SUPUESTO`) que hacen fallar la consulta `path_steps`:

- `ps.position`: **no existe**; en `path_steps` la posición es `step_order` (`topics.position` es la posición del tema en el curso).
- `ps.status = 'approved'`: el estado real es **`passed`** (valores: `skipped`, `blocked`, `pending`, `in_progress`, `passed`, `attempts_exhausted`, `on_hold`).

Todo lo demás coincide (`item_annotations`, `attempt_answers.is_correct/score/grader`, `human_gradings`, `user_profiles.languages` con `code` y `cefr_level`, `enrollments.analysis_included`, `badges.active`, `topics.review_status/extraction_key`, `resources.faithfulness`, `syllabus_extractions.is_current`; la forma de `raw_output->'topics'` depende del contrato `syllabus.v1`).

### Pruebas adicionales

- `reset-app-schema.sh` con `SEED_ADMIN_EMAIL=` (definida y vacía) y la imagen de Liquibase del repositorio: 51 changesets, 0 usuarios, 3 roles, etiqueta `v2.0.0`. `liquibase update` con la variable vacía también pasa.
- Rollback total (`rollback-count --count=51`) con la variable vacía y con una definida: pasa y deja solo las tablas de control; `update-testing-rollback` pasa en ambos casos. Tras agregar 049: 88 de 88 comprobaciones de CHECK y permisos correctas.

## Adenda 2: `purge_user_audit(bigint)` (rama `feature/database-purge-user-audit`)

- Pedido de `api-content` (bitácora F03c): la API respondía `503` a la supresión de datos porque faltaba la función. Changeset `database/liquibase/changelog/v2.0.1/002-purge-user-audit.xml`, incluido en el maestro tras `001-seed-dev-users`. Detalle y límites en `database/README.md`, sección «Supresión de datos».
- **Diseño**: `SECURITY DEFINER` con `search_path` fijo; `EXECUTE` revocado a `PUBLIC` y otorgado solo a `smartmentor_api` (omitido con aviso si el rol no existe). Devuelve el número de filas borradas y deja un `RAISE LOG` sin datos personales. Rollback: `DROP FUNCTION`.
- **Criterio de purga** (decisión): se borran las filas del titular y las que cuelgan de él por `user_id`, `enrollment_id`, `assessment_attempt_id` y `attempt_answer_id`, más cualquier fila que contenga uno de sus correos. No se borran las filas donde solo aparece como actor por id (`owner_user_id`, `annotator_user_id`...): sin nombre ni correo no lo identifican y borrarlas destruiría la trazabilidad de otros. El nombre en texto libre de terceros no se detecta (límite documentado).
- **Validación** (PostgreSQL desechable pgvector 0.8.7-pg17 + Liquibase del repositorio): `validate`, `update` y `update-testing-rollback` correctos. Prueba con tres usuarios (titular, otro aprendiz e instructor) y datos en perfiles, autorizaciones, solicitudes, inscripciones, pasos, intentos, respuestas, calificaciones y encuestas, con seudonimización previa: la función, ejecutada como `smartmentor_api`, borró 12 filas; **0 filas** de cualquier `_audit` con el correo o el nombre del titular; las filas del otro aprendiz y del instructor quedaron intactas; el trigger siguió auditando; `smartmentor_ai` y `PUBLIC` no pueden ejecutarla.
- **Nota para `api-content`**: `SELECT purge_user_audit(:u)` ya devuelve `bigint` (la versión de prueba devolvía `void`); la API detecta la función con `to_regprocedure` y deja de responder `503`.
