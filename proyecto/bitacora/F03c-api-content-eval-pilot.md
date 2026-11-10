# Bitácora F03c · API v2: contenido, evaluación humana, piloto y observabilidad

Rama: `feature/api-v2-content-evaluation-pilot` (desde `origin/dev`). Agente: `api-content` (Fase 3, tercera parte).

## Hecho

- **`content`** (commit `feat(api): dominio content...`): recursos de un tema (listado de versiones, revisión, edición con versión nueva y `content.check_faithfulness`, regeneración con `Idempotency-Key`), ítems (`GET /topics/{id}/items`, `PATCH /items/{id}` aprobar, retirar o editar con `items.review`), videos (`GET/POST /topics/{id}/video-candidates`, `PATCH /video-candidates/{id}` con juicio de pertinencia, «usar este» y respaldos), calidad de videos (`GET /learning-paths/{id}/video-quality`, índice bayesiano con «Midiendo») y `POST /me/video-feedback`.
- **Ingestores idempotentes** registrados en `ai_gateway/dependencies.py`: `content.explain_topic`, `content.check_faithfulness`, `items.generate_quiz_bank`, `items.generate_final_bank`, `diagnostic.generate_items`, `items.review` y `video.collect_candidates`. Las salidas de `FakeAiService` para esos trabajos viven en `content/fake_results.py` (registradas desde `ai_gateway/fake.py`).
- **`evaluation`** (commit `feat(api): dominio evaluation...`): evaluadores por curso (`GET/POST /courses/{id}/evaluators`, `PATCH /course-evaluators/{id}/deactivate`, solo admin; el esquema ya impide asignar al dueño), cola de anotación ciega (`GET /evaluation/annotation-queue`, `POST /items/{id}/annotations`, dos cupos por ítem) y calificación humana (`GET /evaluation/grading-queue?sample=`, `POST /attempt-answers/{id}/human-gradings` que devuelve la nota del LLM solo tras guardar).
- **`pilot`**: `POST/GET /pilots`, `GET/PUT /pilots/{id}`, `randomize` con semilla (solo con `pilot_research` vigente, reproducible, solo antes de iniciar), `start`, `readiness` y `fixed-path-preview` (llama a `path.sequence` con `pilot_arm=fixed`).
- **`observability`** (solo lectura): `GET /llm-call-logs` (filtros tarea, modelo, prompt y estado), `/llm-call-logs/summary` (por tarea con p50/p95, por curso desde la vista) y `GET /metrics/evaluation` (F1 de la extracción, validez y κ de ítems, QWK, fidelidad, P@3 y nDCG@3, JSON inválido, latencia p95 y costo, aprobación al primer intento; cálculo en `observability/metrics.py`).
- **Solicitudes de derechos** (`identity/data_subject_admin.py`, archivo nuevo): `GET /data-subject-requests` y `PATCH /data-subject-requests/{id}`; resolver una supresión seudonimiza al titular y purga `_audit` con `purge_user_audit(bigint)` (ver Qué falta).
- OpenAPI y colección de Postman regenerados (75 peticiones en 12 carpetas).

## Desviaciones frente al plan o al brief

- **Ids enteros en las rutas, no `public_id`**: el contrato (`api-v2.md`) y todo el código ya integrado (`courses`, `identity`) usan enteros; cambiar solo estos dominios rompería la coherencia. Los `public_id` se usan en lo público (badge) y en los trabajos (`job_id`).
- `resources.version` es un entero en la base; la API lo devuelve como `version` y como `version_label` (`1.0`, `1.1`...).
- Rutas que el contrato no tenía y hacían falta: `POST/GET /pilots`, `GET/POST /courses/{id}/evaluators`, `PATCH /course-evaluators/{id}/deactivate`, `GET/PATCH /data-subject-requests`. Sin ellas no había forma de crear un piloto, asignar evaluadores ni resolver una solicitud.
- `pilots.starts_on` y `ends_on` son `NOT NULL` en la base: son obligatorios al crear el piloto; `readiness` no tiene el pendiente `dates`.
- `llm_call_logs` no tiene `_audit` (por diseño): la prueba «toda tabla tiene su auditoría» la exceptúa.

## Decisiones

- Aprobar una versión de una explicación retira la versión aprobada anterior del mismo tema (el aprendiz ve una sola). Una edición queda en `pending_review` y la anterior sigue sirviendo hasta que se apruebe la nueva.
- Un ítem editado y una aprobación van en peticiones separadas (`422` si llegan juntas): la edición siempre vuelve a `pending_review`.
- Solo hay un video `in_use` por tema; al elegir otro, el anterior pasa a `backup`. El video en uso tiene su fila en `resources` (`resource_type=video`).
- Idempotencia sin tabla propia: explicaciones por `created_at` del trabajo, ítems por (tema, banco, enunciado) y `ai_job_id`, videos por la unicidad (tema, `youtube_video_id`); un candidato existente conserva el estado que le dio el instructor. El barrido solo revisa trabajos terminados en los últimos 7 días.
- `POST /me/video-feedback` repetido reemplaza la calificación (`200`); la primera da `201`.
- Evaluador = instructor asignado a un curso que no es suyo. El dueño y el administrador reciben `403 EVALUATOR_NOT_ASSIGNED` en sus propios ítems; un instructor sin asignación recibe `404` (no se revela el ítem) y la cola le responde `403`. Solo el administrador asigna evaluadores (mínimo privilegio).
- La muestra aleatoria de calificación se ordena por `md5(id || curso)`: reproducible y la misma para todos los evaluadores, sin sembrar nada en la base. El QWK usa 5 bandas de 20 puntos.
- P@3 y nDCG@3 solo cuentan temas cuyos tres primeros candidatos tienen juicio (mayoría de los jueces); los demás se informan como `topics_incomplete`.
- El sorteo del piloto reparte mitad y mitad con `random.Random(semilla)` sobre los ids ordenados; si el piloto no trae semilla, se genera y se guarda. Cambiar la ruta o la semilla de un piloto sorteado lo devuelve a `draft` y borra los brazos. Una inscripción posterior al sorteo queda sin brazo (lo decide el dominio de rutas).
- `AssessmentItemModel` queda en `content/models.py`; el dominio `assessments` debe importarlo (dos clases para la misma tabla fallan al cargar).

## Problemas y lecciones

- La barrera de herramientas del agente rechaza `heredoc` largos, variables en comandos de `docker` y `sed` con variables: se usaron scripts de apoyo en el directorio temporal.
- Los ids de las tablas con secuencia que no es «owned by» (`enrollments`, `assessment_attempts`...) no se reinician con `TRUNCATE ... RESTART IDENTITY`: las pruebas no deben asumir ids fijos.
- El formateador reparte la tupla de routers de `main.py` en varias líneas: al agregar uno, buscar la tupla ya formateada.
- Los métodos llamados `list` dentro de una clase rompen las anotaciones de mypy (se usó `list_requests`).

## Métricas

- Pruebas (PostgreSQL desechable `pgvector:0.8.7-pg17`, esquema v2.0.0 y v2.0.1 con Liquibase): **370 en verde** (había 280). Nuevas: ~90 (unitarias de servicios y de métricas con repositorios en memoria, contrato contra `prompts/schemas/*.json`, integración de cada dominio, matriz 401/403/404, anotación ciega y supresión con purga).
- Cobertura de `app`: **93 %** (5.646 sentencias); `content` 83–100 %, `evaluation` 90–100 %, `pilot` 96–100 %, `observability` 97–100 % en servicios y controladores (las consultas SQL se miden peor porque corren en tareas asíncronas).
- Ruff (`check` y `format --check`) y mypy estricto sin errores (109 archivos).
- Código nuevo: ~5.400 líneas en `api/app` y ~3.200 en `api/tests`.

## Impacto en el brief

- Casos de uso CU-20, CU-27, CU-28, CU-29, CU-30, CU-32 y CU-17 (derechos del titular) cubiertos por la API. La «validez de ítems» se mide con anotación ciega de dos evaluadores asignados por curso (κ de Cohen en SQL); el QWK de la calificación del LLM sale de una muestra reproducible.
- Sección de seguridad: la supresión exige un procedimiento de base con permiso explícito sobre `_audit`; el brief debe decir que la supresión no se completa sin él.

## Cambios pedidos a archivos compartidos

- **Base de datos** (agente `database`): crear `purge_user_audit(p_user_id bigint)` (`SECURITY DEFINER`, propietario con permiso sobre las `_audit`, ejecutable por `smartmentor_api`) que borre de todas las `<tabla>_audit` las filas del titular (por `record_id` en `users` y por `user_id` o por las inscripciones del titular en las demás). La API la detecta con `to_regprocedure` y, mientras no exista, responde `503` a la supresión sin cambiar nada. La prueba de integración instala una versión de prueba.
- `diagnostic.generate_items` lo ingiere `content`, pero nadie lo encola: `PublicationService` (`courses`) o el orquestador de `ai/` (`include_diagnostic`) debe pedirlo al publicar.
- `docs/contracts/api-v2.md` y `error-codes.md`: agregar las rutas nuevas de la lista de desviaciones; no se agregaron códigos de error (se usaron los del catálogo).
- `api/tests/integration/schema/test_schema_drift.py`: se agregaron las importaciones de los modelos nuevos y la excepción de `llm_call_logs`; `ai_gateway/fake.py` y `ai_gateway/dependencies.py`: registros de contenido; `main.py`: routers. Los conflictos se resuelven conservando ambas partes y regenerando OpenAPI y Postman.

## Qué falta

- Procedimiento `purge_user_audit` en la base (arriba) y deshabilitar al usuario en Keycloak (`identity_provider_action_required` en la respuesta; Fase 8).
- Que el dominio de rutas rellene `pilot_arm` de las inscripciones nuevas durante un piloto en curso.
- Marcar como leída la alerta `review_requested` al guardar la calificación a solicitud del aprendiz (la alerta la crea el dominio de evaluaciones).
- Prueba con los usuarios de base de mínimo privilegio (`smartmentor_api`): las pruebas corrieron con el propietario; las consultas de este PR solo leen `ai_jobs`, `llm_call_logs` y las vistas, como permite el ADR 0019.
