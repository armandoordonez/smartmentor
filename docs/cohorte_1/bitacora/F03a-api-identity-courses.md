# Bitácora F03a · API v2: identidad, cursos e integración con `ai/`

Rama: `feature/api-v2-identity-courses` (desde `origin/dev`, con `origin/feature/database-v2-rebase` fusionada). Agente: `api-core` (Fase 3, primera parte, Ola 1).

## Hecho

- **Dominios nuevos** (`api/app/domains/`): `identity` (usuarios, roles, perfil y hoja de vida, consentimientos, solicitudes de derechos, primer ingreso, administración de roles), `courses` (cursos, syllabus con `pypdf`, temas, resultados, prerrequisitos con detección de ciclos, revisión, publicación, métricas de extracción, ingestores), `ai_gateway` (puerto `AiServicePort`, `FakeAiService`, `HttpAiService`, `GET /jobs/{id}`, barrido en el `lifespan`) y el modelo mínimo de `learning_paths`.
- **Comunes**: errores RFC 9457 con extensiones permitidas, `X-Request-ID` saneado, `Idempotency-Key` (428 / 422 / repetición 24 h), `auth/policies.py` por rol leyendo `user_roles`, segundo factor opcional (`REQUIRE_SECOND_FACTOR`), fechas en UTC con `Z`.
- **CU-34 / CU-35 / CU-14**: primer `GET /me` crea usuario y rol `learner` con `UPDATE ... WHERE identity_subject IS NULL` e `INSERT ... ON CONFLICT DO NOTHING` (probado con 8 llamadas simultáneas contra la base); `GET /me` con `roles`, `role_labels`, `role_short_labels`, `default_role`; `PUT /users/{id}/roles` con `LAST_ADMIN` (bloqueo asesor `pg_advisory_xact_lock`) y auditoría por el trigger.
- **Eliminado**: `learning_paths` (CRUD), `assessments`, `content`, `observability`, `student` y sus pruebas; `pgvector` sale de las dependencias (los embeddings los escribe `ai/`).
- **OpenAPI** publicado en `docs/contracts/openapi-api.json` (`api/scripts/dev.sh openapi`) con prueba que falla si cambia; **Postman** regenerada (44 peticiones, 7 carpetas; `dev.sh postman`).
- **Pruebas**: unitarias con repositorios en memoria y `FakeAiService`, de contrato (salidas del fake contra `prompts/schemas/*.json` y contra los modelos de ingesta), de integración contra el esquema real v2.0.0 (50 changesets aplicados con Liquibase), matriz de propiedad y alineación modelos-esquema.
- Commits: `wip(api): dominios identity, courses y ai_gateway...`, `feat(api)!: reemplaza los dominios por el modelo v2.0.0...` y el cierre de esta bitácora (ver `git log`).

## Desviaciones frente al plan o al brief

- **Un `Idempotency-Key` en memoria** (un solo proceso) en vez de una tabla: el esquema v2.0.0 no tiene tabla de claves. La garantía fuerte contra duplicar trabajos es la `idempotency_key` de `ai/`.
- **`ai_jobs` solo se lee** (`smartmentor_api` no la escribe): la API consulta el estado por HTTP (`AiServicePort`) y solo resuelve el `id` interno para `syllabus_extractions.ai_job_id`. No hay tabla propia de ingestas: la idempotencia está en el estado del curso (fila bloqueada, curso aún `extracting` / `generating_content` y trabajo más reciente).
- `syllabus_extractions` exige `raw_output NOT NULL`: la fila se crea al **ingerir**, no al subir el syllabus. El `job_id` en curso se obtiene de `ai/` (`list_jobs`).
- `learning_paths`: la API crea la ruta al crear el curso con un modelo mínimo (todas las columnas del esquema); el dominio lo completa el agente de rutas.
- `AI_SERVICE_MODE` por defecto `fake` (la Fase 4 aún no entrega `ai/`).

## Decisiones

- Un curso creado por un administrador sin rol instructor queda «Sin asignar» (`owner_user_id` nulo); si quien crea es instructor, es el dueño.
- La re-extracción reemplaza los temas solo cuando el nuevo trabajo termina bien (si falla se conserva la revisión). Los temas viejos se inactivan y se les libera `extraction_key` (índice único incluso para inactivos).
- Un trabajo superado por otro más reciente del mismo curso se ignora al ingerir.
- `review_status` pasa a `corrected` solo si el instructor cambia algo de un tema del LLM; un `PUT` idéntico no lo cambia.
- `resume_completed_at` se fija cuando `education_level` y `experience_band` están presentes.
- El grafo del curso se expone con `from` = prerrequisito y `to` = tema que lo requiere.
- `recalculated_enrollment_ids` devuelve `[]` hasta que el agente de rutas enchufe `ProfileChangeListener`.

## Problemas y lecciones

- FastAPI reciente envuelve los routers en `_IncludedRouter`: no se pueden recorrer las `APIRoute`; la prueba de protección de rutas recorre el OpenAPI y exige 401 sin token.
- `topics_course_extraction_key_uq` y `learning_outcomes_topic_code_uq` cuentan filas inactivas: hubo que liberar la clave y calcular el siguiente código contando inactivos.
- `request.form()` devuelve `starlette.datastructures.UploadFile`, no el de FastAPI.
- Los métodos llamados `list` dentro de una clase rompen las anotaciones de mypy; se renombraron.

## Métricas

- Pruebas (esta máquina, PostgreSQL desechable `pgvector:0.8.7-pg17`): **280 en verde** (155 unitarias + 125 de integración, contrato y propiedad), cobertura de `app` **94 %** (3.075 sentencias). Ruff (`check` y `format --check`) y mypy estricto sin errores (68 archivos).
- Código: ~6.700 líneas en `api/app`, ~4.100 en `api/tests`; el diff frente a `origin/dev` en `api/` es +8.774 / −3.830.

## Impacto en el brief

- Casos de uso de la API: roles `learner` / `instructor` / `admin`; CU-34, CU-35 y CU-14 ampliado implementados. Sección de seguridad: correo verificado obligatorio para crear o enlazar, segundo factor opcional por configuración, auditoría con `app_user_id`.

## Qué falta / pendiente

- Dominios de otras partes: rutas de aprendizaje, evaluaciones, contenido, evaluación humana, piloto, observabilidad (agentes posteriores).
- Endpoint del administrador para resolver `data_subject_requests` (el contrato no lo define).
- `Idempotency-Key` compartido entre procesos (tabla) y reflejo real de roles en Keycloak (`RoleSyncPort` solo tiene el adaptador nulo; Fase 8).
- Prueba de integración con los usuarios de base de mínimo privilegio (`smartmentor_api`): las pruebas corrieron con el propietario de la base de pruebas, así que los permisos no se ejercitaron.
- Validar `course_evaluators` (rol `instructor` del evaluado) cuando se implemente la evaluación humana.

## Cambios pedidos a archivos compartidos

- `.env.example` / `docker-compose.yml` (agente `infra`): variables nuevas de la API `APP_CONTEXT_PROFILE`, `REQUIRE_SECOND_FACTOR`, `AI_SERVICE_MODE`, `AI_SERVICE_URL`, `AI_SERVICE_CLIENT_ID`, `AI_SERVICE_CLIENT_SECRET`, `AI_SERVICE_TOKEN_URL` (opcional), `AI_SERVICE_TIMEOUT_SECONDS`, `AI_SWEEP_INTERVAL_SECONDS`. La API ya no usa `EMBEDDING_DIMENSION`. Debe conectarse con `API_DATABASE_USER` / `API_DATABASE_PASSWORD`.
- `docs/contracts/api-v2.md`: el borrador queda reemplazado por el OpenAPI; `data_subject_requests` usa `details` (no `comment`) en la base.
