# Catálogo de códigos de error (v1)

Estado: **borrador de la Fase 1** (rama `feature/prompts-and-contracts`). Fuente única de los códigos de error de la API (`api/`) y del servicio de IA (`ai/`). Lo pide la sección 18.2 del plan: en la Fase 3 se agrega una prueba que falla si el código usa un `code` que no está en esta tabla.

## Formato (RFC 9457)

Toda respuesta de error usa `Content-Type: application/problem+json`, igual que hoy en `api/app/core/exceptions.py`:

```json
{
  "type": "https://smartmentor/errors/consent-required",
  "title": "Consent required",
  "status": 403,
  "detail": "You must accept the data processing consent before enrolling.",
  "instance": "/api/v1/me/enrollments",
  "code": "CONSENT_REQUIRED",
  "request_id": "6f1c2b7e-0d1a-4c55-9a0e-2f7f3c1b9d10"
}
```

| Campo | Regla |
| --- | --- |
| `type` | `https://smartmentor/errors/` + `code` en minúsculas con guiones. No resuelve a una página (por ahora es un identificador) |
| `title` | Texto fijo en inglés por código; la app no lo muestra: traduce `code` con su catálogo de textos |
| `status` | El mismo código HTTP de la respuesta |
| `detail` | Explicación en inglés para quien depura. Nunca datos personales, SQL, trazas ni secretos |
| `instance` | Ruta de la petición |
| `code` | Identificador estable de esta tabla (`UPPER_SNAKE_CASE`) |
| `request_id` | El `X-Request-ID` que viaja de la app a la API y a `ai/` (sección 18.2) |

Extensiones permitidas (solo las de la columna «Extensiones»): `errors` (lista `{loc, msg, type}` de validación; nunca el valor recibido), `retryable` (booleano), `job_id`, `cycle` (lista de ids que cierran el ciclo), `missing` (lista de lo que falta), `attempts_used`, `max_attempts`.

**Recursos ajenos.** Pedir un objeto que existe pero no pertenece al usuario responde `404 NOT_FOUND`, igual que si no existiera (sección 18.2, ids secuenciales): nunca `403`.

## Genéricos (API y `ai/`)

| `code` | HTTP | Significado | Emite | Extensiones |
| --- | ---: | --- | --- | --- |
| `VALIDATION_ERROR` | 422 | El cuerpo, la ruta o la consulta no cumplen el esquema | API, ai | `errors` |
| `NOT_FOUND` | 404 | El recurso no existe o no es del usuario | API, ai | — |
| `CONFLICT` | 409 | Conflicto de unicidad o de estado sin código más específico | API | — |
| `BUSINESS_RULE_VIOLATION` | 422 | Regla de negocio sin código más específico (también `CHECK` de la base) | API | — |
| `REFERENCE_NOT_FOUND` | 422 | Una llave foránea apunta a un registro que no existe | API | — |
| `INVALID_STATE_TRANSITION` | 409 | La operación no es válida en el estado actual de la entidad (curso, inscripción, paso, intento, piloto) | API | — |
| `IDEMPOTENCY_KEY_REQUIRED` | 428 | Falta `Idempotency-Key` en una operación que la exige | API | — |
| `IDEMPOTENCY_KEY_REUSED` | 422 | La misma `Idempotency-Key` llegó con otro cuerpo | API, ai | — |
| `PAYLOAD_TOO_LARGE` | 413 | El cuerpo supera el límite de la ruta | API, ai | — |
| `UNSUPPORTED_MEDIA_TYPE` | 415 | Tipo de contenido no admitido | API, ai | — |
| `RATE_LIMITED` | 429 | Demasiadas peticiones (G-02); trae `Retry-After` | API | — |
| `INTERNAL_ERROR` | 500 | Error inesperado; el detalle queda solo en los registros | API, ai | — |
| `SERVICE_UNAVAILABLE` | 503 | Un servicio del que depende no responde | API, ai | — |
| `NOT_READY` | 503 | `GET /ready` falla (base, prompts o precios) | API, ai | `missing` |
| `HTTP_<status>` | var. | Respaldo para errores HTTP sin código propio (por ejemplo `HTTP_405`) | API, ai | — |

## Identidad y autorización

| `code` | HTTP | Significado | Emite | CU / pantalla |
| --- | ---: | --- | --- | --- |
| `UNAUTHORIZED` | 401 | Falta autenticación | API, ai | — |
| `MISSING_TOKEN` | 401 | No llegó `Authorization: Bearer` | API, ai | — |
| `INVALID_TOKEN` | 401 | Token vencido, mal firmado o con emisor o audiencia incorrectos | API, ai | — |
| `IDENTITY_PROVIDER_UNAVAILABLE` | 503 | No se pudo obtener el JWKS de Keycloak | API, ai | — |
| `FORBIDDEN` | 403 | Autenticado, pero sin permiso (sin código más específico) | API, ai | — |
| `INSUFFICIENT_ROLE` | 403 | Ninguno de los roles del usuario (`user_roles`) permite la ruta | API | CU-35 |
| `SECOND_FACTOR_REQUIRED` | 403 | Ruta de `instructor` o `admin` con un token sin segundo factor (DEF-27, G-03) | API | A4 |
| `ACCOUNT_DEACTIVATED` | 403 | El usuario existe pero `active = false` | API | CU-34 |
| `EMAIL_NOT_VERIFIED` | 403 | Primer ingreso con correo sin verificar: no se crea ni se enlaza el usuario (G-01) | API | CU-34 |
| `IDENTITY_ALREADY_LINKED` | 409 | El `sub` del token ya está enlazado a otro usuario | API | CU-34 |
| `IDENTITY_INCOMPLETE` | 422 | `identity_provider` e `identity_subject` deben ir juntos | API | AD1 |
| `EMAIL_ALREADY_REGISTERED` | 409 | Ya existe un usuario con ese correo | API | AD1 |
| `USER_NOT_FOUND` | 404 | El usuario no existe | API | AD1 |
| `ROLE_NOT_FOUND` | 404 | El rol no existe | API | AD1 |
| `ROLE_CODE_ALREADY_EXISTS` | 409 | Ya existe un rol con ese código | API | AD1 |
| `ROLE_ALREADY_ASSIGNED` | 409 | El usuario ya tiene ese rol | API | AD1 |
| `LAST_ADMIN` | 409 | Quitar el rol o desactivar al usuario dejaría la plataforma sin administrador (G-06) | API | CU-14 |
| `CONSENT_REQUIRED` | 403 | Falta la autorización `data_processing` vigente para inscribirse | API | CU-17, A3 |
| `CONSENT_ALREADY_REVOKED` | 409 | La autorización ya estaba revocada | API | E11b |
| `EVALUATOR_NOT_ASSIGNED` | 403 | El instructor no está asignado como evaluador del curso (`course_evaluators`, DEF-24) | API | D5b, D5c |

## Cursos, syllabus y temas

| `code` | HTTP | Significado | Emite | CU / pantalla |
| --- | ---: | --- | --- | --- |
| `COURSE_NOT_FOUND` | 404 | El curso no existe o no es del instructor | API | D1 |
| `OWNER_NOT_FOUND` | 422 | El instructor asignado no existe | API | AD5 |
| `INVALID_COURSE_STATUS` | 422 | Estado de curso fuera de la lista | API | — |
| `SYLLABUS_NO_TEXT` | 422 | El PDF o el texto no tienen caracteres extraíbles (0 caracteres) | API | D1d, CU-24 |
| `SYLLABUS_TOO_LARGE` | 413 | El PDF supera 10 MB | API | D1b |
| `SYLLABUS_UNSUPPORTED_TYPE` | 415 | No es PDF ni texto | API | D1b |
| `EXTRACTION_IN_PROGRESS` | 409 | Ya hay una extracción en curso para el curso | API | D1c, D2c |
| `TOPIC_NOT_FOUND` | 404 | El tema no existe | API | D2b |
| `INVALID_BLOOM_LEVEL` | 422 | Nivel de Bloom fuera de la lista | API | D2b |
| `PREREQUISITE_ALREADY_EXISTS` | 409 | El prerrequisito ya existe | API | D2b |
| `PREREQUISITE_SELF` | 422 | Un tema no puede ser su propio prerrequisito | API, ai | D2b |
| `PREREQUISITE_TOPIC_NOT_FOUND` | 422 | El prerrequisito apunta a un tema que no existe | API | D2b |
| `PREREQUISITE_CYCLE` | 422 | Los prerrequisitos forman un ciclo; `cycle` trae el camino cerrado (`["a","b","a"]`) | API | D2b, D2d |
| `COURSE_REVIEW_INCOMPLETE` | 422 | Publicar con temas sin revisar o sin resultados de aprendizaje; `missing` trae los temas | API | D2 |
| `LEARNING_PATH_NOT_PUBLISHED` | 422 | La ruta no está publicada | API | E1 |
| `PILOT_RUNNING` | 409 | Cambiar umbrales con el piloto en curso sin `confirm_pilot_change=true` | API | D3b |

## Ruta del aprendiz

| `code` | HTTP | Significado | Emite | CU / pantalla |
| --- | ---: | --- | --- | --- |
| `ENROLLMENT_NOT_FOUND` | 404 | La inscripción no existe o no es del aprendiz | API | E11 |
| `ENROLLMENT_ALREADY_EXISTS` | 409 | El aprendiz ya tiene una inscripción activa en la ruta | API | E1 |
| `ENROLLMENT_CLOSED` | 409 | La inscripción está `abandoned`, `withdrawn` o `completed` | API | E11 |
| `PROFILE_INCOMPLETE` | 422 | Falta la descripción obligatoria para iniciar el diagnóstico; `missing` trae los campos | API | E2 |
| `DIAGNOSTIC_ALREADY_EXISTS` | 409 | La inscripción ya tiene diagnóstico | API | E3 |
| `DIAGNOSTIC_BANK_EMPTY` | 409 | El curso no tiene ítems de diagnóstico aprobados | API | E3 |
| `DIAGNOSTIC_ALREADY_SUBMITTED` | 409 | El diagnóstico ya se entregó | API | E3 |
| `DIAGNOSTIC_NOT_READY` | 409 | El resultado todavía se está calculando; trae `job_id` | API | U1a, E4 |
| `OBJECTIVE_NOT_MEASURABLE` | 422 | El objetivo no tiene las tres partes; `missing` trae `bloom_verb`, `content` o `criterion` | API | E4b |
| `STEP_NOT_FOUND` | 404 | El paso no existe o no es de la inscripción | API | E5 |
| `STEP_NOT_AVAILABLE` | 409 | El paso está `blocked`, `skipped`, `on_hold` o `passed` | API | E5, E6 |
| `MAX_ATTEMPTS_EXCEEDED` | 422 | No quedan intentos (incluye los extra); trae `attempts_used` y `max_attempts` | API | E7c, E9c |
| `ATTEMPT_NOT_FOUND` | 404 | El intento no existe o no es del aprendiz | API | E6b |
| `ATTEMPT_IN_PROGRESS` | 409 | Ya hay un intento abierto para el paso o la final; trae su id en `detail` | API | E6b |
| `ATTEMPT_ALREADY_SUBMITTED` | 409 | El intento ya se entregó (una entrega repetida con la misma `Idempotency-Key` devuelve la respuesta original, no este error) | API | U1c |
| `ATTEMPT_NOT_GRADED` | 409 | El resultado todavía se está calificando; trae `job_id` | API | U1c, U1d |
| `FINAL_ASSESSMENT_LOCKED` | 422 | La final exige todos los pasos en `passed` o `skipped` | API | E8 |
| `REVIEW_ALREADY_REQUESTED` | 409 | Ya se pidió la revisión humana de esa respuesta | API | E7 |
| `REVIEW_NOT_ALLOWED` | 422 | Solo se pide revisión de respuestas cortas calificadas por el LLM | API | E7 |
| `SURVEY_ALREADY_SUBMITTED` | 409 | La encuesta final ya se respondió | API | E13a |
| `BADGE_NOT_FOUND` | 404 | No hay badge (o el `public_id` no existe) | API | E10 |

## Instructor, evaluación y piloto

| `code` | HTTP | Significado | Emite | CU / pantalla |
| --- | ---: | --- | --- | --- |
| `ITEM_NOT_FOUND` | 404 | El ítem no existe o no es de un curso del instructor | API | D5 |
| `RESOURCE_NOT_FOUND` | 404 | El recurso (explicación, video) no existe | API | D5, D5d |
| `ANNOTATION_ALREADY_EXISTS` | 409 | El evaluador ya anotó ese ítem | API | D5b |
| `EVALUATOR_SLOTS_FULL` | 409 | El ítem ya tiene sus dos evaluadores | API | D5b |
| `HUMAN_GRADING_ALREADY_EXISTS` | 409 | El evaluador ya calificó esa respuesta | API | D5c |
| `PILOT_NOT_FOUND` | 404 | El piloto no existe | API | AD4 |
| `PILOT_ALREADY_STARTED` | 409 | Sortear o cambiar la configuración después de iniciar | API | AD4 |
| `PILOT_NOT_READY` | 422 | Iniciar sin cumplir `GET /pilots/{id}/readiness`; `missing` trae lo que falta | API | AD4 |
| `PILOT_CONSENT_REQUIRED` | 422 | Asignar al piloto a un aprendiz sin `pilot_research` vigente | API | AD4 |

## Integración con `ai/` (vistos desde la API)

| `code` | HTTP | Significado | Emite | Extensiones |
| --- | ---: | --- | --- | --- |
| `JOB_NOT_FOUND` | 404 | El trabajo no existe o no es del usuario | API, ai | — |
| `AI_TASK_FAILED` | 502 | El trabajo de `ai/` terminó en `failed` | API | `job_id`, `retryable` |
| `AI_BUDGET_EXCEEDED` | 503 | `ai/` rechazó el trabajo por presupuesto (`budget_exceeded`) | API | `job_id` |
| `AI_SERVICE_UNAVAILABLE` | 503 | `ai/` no responde o devolvió 5xx | API | `retryable` |
| `AI_RESULT_INVALID` | 502 | El resultado de `ai/` no cumple su contrato (`prompts/schemas/…`) al ingerirlo | API | `job_id` |

La app muestra en estos casos el mensaje de U1x («tu avance está guardado»).

## Servicio de IA (`ai/`, HTTP)

| `code` | HTTP | Significado |
| --- | ---: | --- |
| `UNKNOWN_JOB_TYPE` | 422 | `job_type` no está en la tabla de `docs/contracts/ai-service-v1.md` |
| `INVALID_JOB_INPUT` | 422 | `input` no cumple el esquema del `job_type`; trae `errors` |
| `IDEMPOTENCY_KEY_REUSED` | 422 | La misma `idempotency_key` llegó con otro `job_type` o `input` |
| `JOB_NOT_RETRYABLE` | 409 | `POST /v1/jobs/{id}/retry` sobre un trabajo que no está `failed` con `retryable=true` |
| `UNKNOWN_TASK` | 404 | `POST /v1/tasks/{name}` con una tarea que no existe |
| `PROMPT_NOT_FOUND` | 404 | `GET /v1/prompts/{id}` de un prompt que no está en el catálogo |
| `BUDGET_EXCEEDED` | 503 | Una tarea síncrona superaría el presupuesto |

## Servicio de IA (`ai/`, `error.code` de un trabajo `failed`)

No son respuestas HTTP: van en `GET /v1/jobs/{id}` → `error.code`, y la API los traduce a `AI_TASK_FAILED` o `AI_BUDGET_EXCEEDED`.

| `error.code` | `retryable` | Significado |
| --- | :---: | --- |
| `INVALID_OUTPUT` | sí | El LLM no devolvió una salida válida tras 2 reintentos (esquema o validaciones de código); queda `status=invalid_output` en `llm_call_logs` |
| `LLM_PROVIDER_ERROR` | sí | Error del proveedor (5xx, red) tras los reintentos |
| `LLM_QUOTA_EXHAUSTED` | sí (cuando se suba el tope) | El proveedor rechazó por cuota o tope de gasto agotado (por ejemplo, el *project spend cap* de Google AI Studio). No se reintenta solo: hay que subir el tope y pedir el reintento |
| `LLM_PROVIDER_TIMEOUT` | sí | El proveedor no respondió a tiempo |
| `LLM_CONTENT_BLOCKED` | no | El proveedor bloqueó la respuesta por sus filtros |
| `BUDGET_EXCEEDED` | no | Se superó `AI_DAILY_BUDGET_USD`, `AI_COURSE_BUDGET_USD` o `AI_ENROLLMENT_BUDGET_USD`; queda una alerta para el admin |
| `PRICE_NOT_CONFIGURED` | no | El modelo configurado no tiene precio en `config/prices.yaml` (L-12) |
| `NO_SOURCE_FRAGMENTS` | no | No hay fragmentos indexados para el tema: no se puede redactar con RAG |
| `SYLLABUS_NO_TOPICS` | no | El LLM no encontró temas en el texto (CU-24) |
| `VIDEO_SEARCH_UNAVAILABLE` | sí | La búsqueda de videos falló y no hay lista del instructor (L-08) |
| `INPUT_REFERENCE_NOT_FOUND` | no | Una referencia del `input` (curso, tema, documento) no existe en la base |
| `INTERNAL_ERROR` | sí | Error inesperado del *worker* |
