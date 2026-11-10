# api/

API de negocio de SmartMentor en FastAPI: identidad, cursos y la integración con el servicio de IA (las rutas, evaluaciones, contenido y piloto llegan en las partes siguientes de la Fase 3). PostgreSQL con pgvector como única base; el esquema lo crea Liquibase (la API nunca crea ni migra tablas).

- Estándar que sigue: [`microservice-development-standard.md`](microservice-development-standard.md) (rev. 2).
- Decisiones: [ADR 0001 (PostgreSQL + pgvector)](../docs/adr/0001-postgres-pgvector.md), [ADR 0002 (Liquibase)](../docs/adr/0002-liquibase-schema-versioning.md), [ADR 0003 (organización por dominio)](../docs/adr/0003-api-domain-first-layout.md).
- Modelo de datos: [`database/README.md`](../database/README.md).

> **Requiere un bearer token de Keycloak** en todas las rutas de `/api/v1` ([ADR 0004](../docs/adr/0004-authentication-keycloak-bearer.md)). La autorización usa los roles de la tabla `user_roles`. Configuración de Keycloak y solución de errores 401/403: [`keycloak/README.md`](../keycloak/README.md).

## Ejecución

```bash
cp .env.example .env          # una vez; completa POSTGRES_PASSWORD y DATABASE_PASSWORD (iguales)
docker compose up -d --build  # postgres → liquibase update → api (y keycloak)
```

| Qué | Dónde |
| --- | --- |
| Documentación interactiva (Swagger UI) | <http://localhost:8020/docs> (puerto `API_PORT`); el botón *Authorize* hace el login por ti ([cómo](#obtener-un-token-y-probar-la-api)) |
| Esquema OpenAPI (para importar en Postman) | <http://localhost:8020/openapi.json> |
| Liveness / readiness | `GET /health`, `GET /ready` |
| API de negocio | `http://localhost:8020/api/v1/...` |
| Logs | JSON en la salida del contenedor: `docker logs -f smartmentor-api` |

## Obtener un token y probar la API

Todas las rutas de `/api/v1` exigen `Authorization: Bearer <access_token>`. El token lo emite Keycloak; la API solo lo valida. Necesitas un **usuario con contraseña** en el realm `smartmentor` (en Keycloak: *Users → Create new user*, correo con *Email verified* activado, y *Credentials → Set password*). En su primer `GET /me` la API lo da de alta como aprendiz (`learner`); para probar como administrador, define `SEED_ADMIN_EMAIL` antes de crear la base y crea ese usuario en Keycloak con el mismo correo verificado.

| Forma | Pide el token | Útil para |
| --- | --- | --- |
| [Swagger UI](#1-swagger-ui-login-desde-la-página) | Swagger, al escribir usuario y contraseña | Probar rápido desde el navegador |
| [Terminal](#2-terminal-apiscriptstokensh) | `api/scripts/token.sh` en cada llamada | `curl`, scripts y pruebas automáticas |
| [Postman, token automático](#3-postman-token-automático-antes-de-cada-petición) | Un script, antes de cada petición | Probar la API sin iniciar sesión cada vez |
| [Postman, login con navegador](#4-postman-con-login-en-el-navegador) | Postman, con la pantalla de Keycloak | Probar el flujo que usará el frontend |
| [Pegar un token](#5-pegar-un-token-ya-emitido) | Ya lo tienes | Cualquier cliente |

Las formas 1 a 3 usan el cliente de Keycloak **`smartmentor-dev-tools`**, que entrega el token a cambio del usuario y la contraseña, sin navegador. Es **solo para desarrollo** (ver [Seguridad](#seguridad-de-estas-herramientas)). El token dura 30 minutos con ese cliente y 5 con `smartmentor-frontend`.

### 1. Swagger UI: login desde la página

1. Abre <http://localhost:8020/docs> y pulsa **Authorize**.
2. En **Login (usuario y contraseña)** escribe el correo y la contraseña del usuario de Keycloak. `client_id` aparece ya completo (`smartmentor-dev-tools`) y los scopes `openid profile email` ya vienen marcados. Deja `client_secret` vacío.
3. Pulsa **Authorize** y luego **Close**. Swagger pide el token a Keycloak y lo envía en cada petición que pruebes con *Try it out*. La autorización se conserva al recargar la página.
4. Empieza por `GET /api/v1/me`: debe devolver tu usuario y tus roles.

Al vencer el token (30 minutos) las llamadas responden 401: pulsa **Authorize** y vuelve a iniciar sesión.

En el mismo cuadro, **Token (pegar)** permite pegar un token que ya tengas (forma 5).

### 2. Terminal: `api/scripts/token.sh`

Imprime solo el token, así que se usa dentro de cada llamada, y cada llamada lleva un token recién pedido:

```bash
export TOKEN_PASSWORD='la-contraseña'     # evita escribirla en la línea de comandos (queda en el historial)

curl -H "Authorization: Bearer $(api/scripts/token.sh usuario@correo.com)" \
     http://localhost:8020/api/v1/me

curl -X POST http://localhost:8020/api/v1/courses \
     -H "Authorization: Bearer $(api/scripts/token.sh admin.smartmentor@yopmail.com)" \
     -H "Content-Type: application/json" \
     -d '{"owner_user_id": 1, "name": "Ciencia de datos"}'
```

Si no defines `TOKEN_PASSWORD` ni pasas la contraseña como segundo argumento, el script la pide sin mostrarla. Para ver qué trae un token (`iss`, `aud`, `exp`...): `api/scripts/token.sh --claims usuario@correo.com`.

Sin el script, es una sola llamada a Keycloak:

```bash
curl -s -d "grant_type=password" -d "client_id=smartmentor-dev-tools" \
     -d "username=usuario@correo.com" -d "password=la-contraseña" -d "scope=openid profile email" \
     http://localhost:8180/realms/smartmentor/protocol/openid-connect/token
# → {"access_token":"eyJ...","expires_in":1800,...}
```

### 3. Postman: token automático antes de cada petición

Importa los dos archivos de [`api/postman/`](postman/):

1. **Import** → `SmartMentor.postman_collection.json` y `SmartMentor-local.postman_environment.json`.
2. Elige el entorno **SmartMentor local** (arriba a la derecha) y completa `username` y `password` en *Environments*.
3. Ejecuta cualquier petición de la colección, por ejemplo **Sesión → Quién soy (/me)**.

La colección tiene un script de pre-request que pide el token a Keycloak, lo guarda en `access_token` y lo envía como Bearer; lo reutiliza hasta que está por vencer. Para que pida **uno nuevo en cada petición**, pon `always_new_token` en `true` en el entorno. Las carpetas *Sin autenticación* (`/health`, `/ready`) no envían token. Para tus propias peticiones, basta con crearlas dentro de la colección: heredan el script y la autorización.

### 4. Postman con login en el navegador

Para probar el flujo que usará el frontend (código de autorización con PKCE, cliente `smartmentor-frontend`). Pestaña **Authorization** → **OAuth 2.0**:

| Campo | Valor |
| --- | --- |
| Grant Type | Authorization Code (With PKCE) |
| Callback URL | `https://oauth.pstmn.io/v1/callback` (marca *Authorize using browser*) |
| Auth URL | `http://localhost:8180/realms/smartmentor/protocol/openid-connect/auth` |
| Access Token URL | `http://localhost:8180/realms/smartmentor/protocol/openid-connect/token` |
| Client ID | `smartmentor-frontend` |
| Client Secret | (vacío: cliente público) |
| Code Challenge Method | SHA-256 |
| Scope | `openid profile email` |

**Get New Access Token** abre el navegador con el login de Keycloak; después **Use Token**. Este token dura 5 minutos.

### 5. Pegar un token ya emitido

En Swagger: **Authorize → Token (pegar)** y pega el access token **sin** la palabra `Bearer`. En Postman: *Authorization → Bearer Token*. En `curl`: `-H "Authorization: Bearer <token>"`.

### Si algo falla

| Síntoma | Causa probable |
| --- | --- |
| `invalid_grant` / `Invalid user credentials` | Usuario o contraseña incorrectos, o el usuario no tiene contraseña definida |
| `invalid_scope` | Se envió el scope vacío: en Swagger deja marcados `openid profile email` |
| Swagger: error de red o *CORS* al autorizar | El cliente `smartmentor-dev-tools` no permite el origen de la página (*Web origins* debe incluir `http://localhost:8020`) |
| 401 `INVALID_TOKEN` | Token vencido, `iss` distinto de `OIDC_ISSUER_URL` o falta la audiencia `smartmentor-api`. El motivo exacto está en `docker logs smartmentor-api` (busca `token rejected`) |
| 403 `EMAIL_NOT_VERIFIED` | El usuario no tiene *Email verified* en Keycloak |
| 403 `INSUFFICIENT_ROLE` | El rol del usuario (tabla `user_roles`) no permite esa operación; ver la matriz de roles más abajo |

### Seguridad de estas herramientas

- El flujo con usuario y contraseña entregados al cliente (*password grant*) está desaconsejado por OAuth 2.1; se usa aquí solo para desarrollo y pruebas.
- **En producción:** elimina el cliente `smartmentor-dev-tools` de Keycloak y deja `OIDC_DOCS_CLIENT_ID` vacío. Entonces `/docs` solo ofrece *Token (pegar)* y los usuarios inician sesión en la pantalla de Keycloak, a través del frontend.
- No guardes contraseñas reales en el entorno de Postman ni lo compartas: contiene `username` y `password`.

## Dominios y rutas

La Fase 3 entrega `identity`, `courses` y `ai_gateway` (F03a), `learning_paths`, `assessments` y `learner` (F03b) y `content`, `evaluation`, `pilot` y `observability` (F03c). El contrato completo está en [`docs/contracts/api-v2.md`](../docs/contracts/api-v2.md) y el OpenAPI generado en [`docs/contracts/openapi-api.json`](../docs/contracts/openapi-api.json) (una prueba falla si el código cambia sin actualizarlo: `api/scripts/dev.sh openapi`). Los ids de las rutas son enteros; los trabajos usan el `job_id` UUID de `ai/`.

| Dominio | Rutas (prefijo `/api/v1`) | Reglas de negocio |
| --- | --- | --- |
| `identity` | `GET /me`; `GET`, `PUT /me/profile`; `GET`, `POST /me/consents`; `PATCH /me/consents/{type}/revoke`; `POST /me/data-subject-requests`; CRUD de `roles`, `users` y `user-roles`; `GET`, `PUT /users/{id}/roles` | El primer `GET /me` crea el usuario y el rol `learner` (CU-34). Correo único sin distinguir mayúsculas. El administrador reemplaza los roles de un usuario (varios por usuario) y **nunca puede dejar la plataforma sin administrador** (`409 LAST_ADMIN`). Cada cambio queda en la auditoría. |
| `courses` | `POST`, `GET /courses`; `GET`, `PATCH /courses/{id}`; `PATCH /courses/{id}/owner`; `POST /courses/{id}/syllabus`; `POST /courses/{id}/extractions`; `GET /courses/{id}/topics`, `/topic-graph`, `/extraction-metrics`; `POST /courses/{id}/topics`; `PUT /topics/{id}`; `PATCH /topics/{id}/deactivate`; `POST /courses/{id}/publish` | El instructor solo ve sus cursos; el administrador, todos. El syllabus (PDF de hasta 10 MB o texto) se extrae con `pypdf`; sin texto, `422 SYLLABUS_NO_TEXT`. Los prerrequisitos forman un DAG: un ciclo responde `422 PREREQUISITE_CYCLE` con el camino en `cycle`. Publicar exige revisión completa. |
| `ai_gateway` | `GET /jobs/{job_id}` | Estado de un trabajo de `ai/`; si terminó, la API lo ingiere en la misma petición. |
| `learning_paths` | `GET /learning-paths`; `PATCH /learning-paths/{id}/settings`; `GET /learning-paths/{id}/dashboard`, `/learners/{enrollment_id}`; `POST /path-steps/{id}/attempt-grants`; `POST /enrollments/{id}/final-attempt-grants`; `GET /alerts`; `PATCH /alerts/{id}/read`; AD5: `GET`, `POST /enrollments`, `PATCH /enrollments/{id}/withdraw`, `/move` | Máquinas de estados de la inscripción, el paso (con `on_hold`) y el intento en `states.py` (funciones puras). `path.sequence` síncrono crea los pasos. Intentos extra fuera del conteo de la regla. Ajustes con el piloto en curso: `409 PILOT_RUNNING` sin confirmación. Mover o retirar saca del análisis. |
| `assessments` | `GET /badges/{public_id}/assertion.json`, `/image.png` (públicas) | Diagnóstico desde el banco aprobado y `diagnostic.finalize`; intentos con ítems no vistos (`202` e `items.generate_quiz_bank` si se agota el banco); opción múltiple por regla y respuesta corta por criterios (`grading.short_answer`, 2 de 3); final con todos los pasos `passed` o `skipped`; badge Open Badges «hosted» con el receptor con hash y sal. Recalcula niveles y pasos pendientes al cambiar el perfil (`ProfileChangeListener`). |
| `learner` | `POST`, `GET /me/enrollments`; `GET /me/enrollments/{id}` y sus rutas de diagnóstico, objetivo, ruta, contenido del paso, intentos, final, repaso, badge y encuesta; `GET`, `PUT /me/attempts/{id}`…; `POST /me/attempt-answers/{id}/review-request`; `GET /me/badges`; `POST /me/events`; `GET`, `PUT /me/study-goals`; historial de intentos | Toda respuesta de inscripción trae `next_action`. Consentimiento de datos obligatorio (`403 CONSENT_REQUIRED`). Encuesta final con `sus_score`. |

### Estados del curso

`draft` → `extracting` → `in_review` → `generating_content` → `published`; `extracting` → `extraction_failed` (se vuelve a subir un syllabus). La re-extracción (`POST /extractions`) reemplaza los temas **cuando el trabajo termina bien**: si falla, la revisión actual se conserva.

### Integración con `ai/` (trabajos asíncronos)

- La API habla con `ai/` solo a través del puerto `AiServicePort` (`app/domains/ai_gateway/repository.py`). Adaptadores: `HttpAiService` (`httpx`, token de servicio por *client credentials*) y `FakeAiService` (pruebas y desarrollo sin `ai/`). Se elige con `AI_SERVICE_MODE=fake|http` (por defecto `fake`).
- Una operación asíncrona responde `202` con `{job_id, status, poll_url}` y la cabecera `Location`. La app consulta `GET /jobs/{id}` cada 2 s.
- **Ingesta idempotente por consulta (modelo pull):** cada tipo de trabajo tiene un *ingestor* (`SyllabusIngestor`, `PublicationIngestor`) que valida el resultado contra su contrato (`app/domains/ai_gateway/contracts.py`, espejo de `prompts/schemas`) y lo escribe en una transacción. La fila del curso se bloquea y solo se ingiere si el curso sigue esperando ese trabajo (el más reciente): dos consultas simultáneas, o una consulta y el barrido, no duplican nada.
- **Barrido:** una tarea del `lifespan` ingiere cada 60 s (`AI_SWEEP_INTERVAL_SECONDS`, 0 la desactiva) los trabajos terminados que nadie consultó.
- Errores: `failed` produce `502 AI_TASK_FAILED` (con `retryable` y `job_id`); presupuesto, `503 AI_BUDGET_EXCEEDED`; `ai/` caído, `503 AI_SERVICE_UNAVAILABLE`; un resultado que rompe el contrato, `502 AI_RESULT_INVALID`.
- La API solo **lee** `ai_jobs` (para guardar `syllabus_extractions.ai_job_id`); nunca la escribe.

### Convenciones HTTP

| Tema | Regla |
| --- | --- |
| Errores | RFC 9457 (`application/problem+json`) con `type`, `title`, `status`, `detail`, `instance`, `code` y `request_id`. Los `code` salen de [`docs/contracts/error-codes.md`](../docs/contracts/error-codes.md); una prueba falla si el código usa uno que no está allí. |
| Objetos ajenos | `404` del recurso, nunca `403` (matriz de pruebas de propiedad en `tests/integration/ownership/`). |
| `X-Request-ID` | Se acepta (solo `[A-Za-z0-9._-]`, hasta 128), se genera si falta, se devuelve, va en los logs y en cada error, y se reenvía a `ai/`. |
| `Idempotency-Key` | UUID obligatorio en `syllabus`, `extractions`, `publish`, `…/diagnostic/submit`, `…/attempts`, `…/final-attempts` y `/me/attempts/{id}/submit` (y en las del contenido). Misma clave y mismo cuerpo, misma respuesta durante 24 h; otro cuerpo, `422 IDEMPOTENCY_KEY_REUSED`; sin clave, `428`. La tienda es en memoria (un proceso); ver la bitácora. |
| Fechas | `timestamptz` en la base; la API devuelve ISO 8601 en UTC con sufijo `Z`. La app muestra en `America/Bogota`. |
| Paginación | `?limit=20&offset=0` (máximo 100); respuesta `{items, total, limit, offset}`. |

### Autenticación y roles

Cada petición a `/api/v1` lleva `Authorization: Bearer <access_token>`. La API valida la firma (RS256, llaves de Keycloak), `iss`, `aud` y `exp`; ve [`keycloak/README.md`](../keycloak/README.md) para el mapper de audiencia.

- Se autoriza por la **unión** de los roles de `user_roles` (no los del token). El «rol activo» de la app es solo de presentación (CU-35): `GET /me` devuelve `roles`, `role_labels`, `role_short_labels` y `default_role` (el de mayor privilegio).
- Con `REQUIRE_SECOND_FACTOR=true` (Fase 8), las rutas solo de instructor o admin exigen que el token indique segundo factor (`amr`/`acr`): `403 SECOND_FACTOR_REQUIRED`.
- Un correo sin verificar nunca crea ni enlaza usuarios (`403 EMAIL_NOT_VERIFIED`): con el registro abierto sería una forma de quedarse con el perfil del administrador.
- Etiquetas de los roles: glosario en `app/domains/identity/labels.py`, perfil con `APP_CONTEXT_PROFILE` (`generic` por defecto).

| Ruta | Quién |
| --- | --- |
| `/me`, `/me/profile`, `/me/consents`, `/me/data-subject-requests` | Cualquier usuario autenticado, solo lo propio |
| `GET /roles` | Cualquier rol |
| `POST`, `PATCH /roles`; `users`, `user-roles`, `users/{id}/roles`; `PATCH /courses/{id}/owner` | `admin` |
| `courses`, `topics`, `syllabus`, `publish` | `instructor` (los suyos) y `admin` (todos) |
| `GET /jobs/{id}` | Dueño del trabajo y `admin` |

`/health`, `/ready` y `/docs` son públicos.

### Auditoría

Cada cambio queda en la tabla `<tabla>_audit`, con `app_user_id` igual al id del usuario autenticado. Mientras se resuelve o crea al usuario se registra `identity:<sub>`; el barrido registra `system:ai-sweeper`. El usuario de base `smartmentor_api` no puede leer ni escribir las tablas `_audit` (solo el trigger).

## Estructura

```text
api/
├── Dockerfile, pyproject.toml, uv.lock
├── app/
│   ├── main.py            # lifespan (puerto de IA y barrido), middleware, errores, routers
│   ├── core/              # config, database, logging, middleware, errores HTTP, security, idempotency, openapi
│   ├── auth/              # get_current_user, require_roles y las políticas por rol (composición)
│   ├── common/            # base genérica: entidad, modelo, repositorio, servicio, fábrica de routers CRUD
│   ├── health/            # /health y /ready
│   └── domains/<dominio>/ # controller, schemas, dependencies, service, entities, repository, models, repository_impl
│       ├── identity/      # usuarios, roles, perfil, consentimientos, solicitudes de derechos
│       ├── courses/       # cursos, syllabus, temas, prerrequisitos, publicación, ingestores
│       ├── ai_gateway/    # puerto AiServicePort, FakeAiService, HttpAiService, trabajos, barrido
│       ├── learning_paths/# rutas, inscripciones, pasos, estados, intentos extra, alertas, tablero
│       ├── assessments/   # banco, diagnóstico, intentos, calificación, final, badge, ingestores
│       └── learner/       # rutas /me del aprendiz, encuesta, eventos, metas
├── tests/
│   ├── unit/              # reglas con repositorios en memoria y FakeAiService; contrato contra prompts/schemas
│   └── integration/       # flujos HTTP contra smartmentor_test; matriz de propiedad; alineación modelos-esquema
├── postman/               # colección generada desde el OpenAPI (dev.sh postman)
└── scripts/               # dev.sh, token.sh, export_openapi.py, export_postman.py
```

## Desarrollo y calidad

No hace falta instalar Python ni `uv`: todo corre en contenedores (la base debe estar arriba: `docker compose up -d postgres`).

```bash
api/scripts/dev.sh prepare-test-db   # crea y migra smartmentor_test (una vez, y tras nuevos changesets)
api/scripts/dev.sh format            # Ruff format
api/scripts/dev.sh lint              # ruff check + ruff format --check
api/scripts/dev.sh typecheck         # mypy en modo estricto
api/scripts/dev.sh test              # pytest (pasa argumentos: test -k courses -x)
api/scripts/dev.sh openapi           # regenera docs/contracts/openapi-api.json
api/scripts/dev.sh postman           # regenera la colección de Postman desde ese OpenAPI
api/scripts/dev.sh all               # lint + typecheck + pytest
api/scripts/dev.sh lock              # regenera uv.lock tras cambiar dependencias
```

- Las pruebas de integración **solo corren sobre una base cuyo nombre termina en `_test`** y la vacían entre pruebas; nunca tocan `smartmentor`.
- Una prueba compara los modelos SQLAlchemy con el esquema que dejó Liquibase y falla si se desalinean.
- Pruebas de contrato: las salidas de `FakeAiService` se validan contra `prompts/schemas/*.json` y contra los modelos de ingesta; el OpenAPI publicado, el catálogo de códigos de error y la protección de cada ruta tienen su guardia en `tests/unit/test_contracts_guards.py`.
- Tras agregar un changeset: `prepare-test-db` y luego `test`.

## Cómo agregar un recurso o un tipo de trabajo

1. Changeset de Liquibase con la tabla, su `_audit` y su trigger ([guía](../database/liquibase/README.md)).
2. En el dominio: `entities.py`, `models.py`, `schemas.py`, `repository.py`, `repository_impl.py` (con `constraint_messages`), `service.py`, `dependencies.py` y `controller.py`.
3. Registrar el router en `app/main.py` si es un dominio nuevo.
4. Para un trabajo de `ai/`: modelo del resultado en `ai_gateway/contracts.py`, un ingestor idempotente y su registro en `ai_gateway/dependencies.py`.
5. Pruebas unitarias de las reglas, de integración del flujo HTTP y de propiedad (objeto ajeno responde 404); `dev.sh openapi` y `dev.sh postman`.
