# api/

API de negocio de SmartMentor en FastAPI: usuarios, cursos, rutas y evaluaciones. PostgreSQL con pgvector como única base; el esquema lo crea Liquibase (la API nunca crea ni migra tablas).

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

Todas las rutas de `/api/v1` exigen `Authorization: Bearer <access_token>`. El token lo emite Keycloak; la API solo lo valida. Necesitas un **usuario con contraseña** en el realm `smartmentor` (en Keycloak: *Users → Create new user*, correo con *Email verified* activado, y *Credentials → Set password*). En su primer acceso la API lo da de alta como estudiante; para probar como administrador usa `admin.smartmentor@yopmail.com` (defínele la contraseña).

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

## Dominios y recursos

Cada recurso expone las mismas operaciones. **No existe `DELETE`**: el borrado es lógico.

| Operación | Método y ruta | Respuesta |
| --- | --- | --- |
| Crear | `POST /api/v1/<recurso>` | 201 |
| Consultar | `GET /api/v1/<recurso>/{id}` | 200 (también si está inactivo) |
| Listar | `GET /api/v1/<recurso>?limit=20&offset=0&active=true&<filtros>` | 200 `{items, total, limit, offset}` |
| Actualizar | `PATCH /api/v1/<recurso>/{id}` | 200 (solo los campos enviados) |
| Inactivar / activar | `PATCH /api/v1/<recurso>/{id}/deactivate` · `/activate` | 200 |

`limit` va de 1 a 100. Por defecto las listas devuelven solo registros activos; `active=false` lista los inactivos.

| Dominio | Recursos (ruta) | Reglas de negocio |
| --- | --- | --- |
| `identity` | `roles`, `users`, `user-roles` | Email único sin distinguir mayúsculas (409). `identity_provider` e `identity_subject` van juntos. Un usuario puede tener varios roles. |
| `courses` | `courses`, `topics`, `topic-prerequisites` | Los prerrequisitos forman un grafo sin ciclos (422) y deben ser del mismo curso. El `embedding` se acepta pero no se devuelve (`has_embedding`). |
| `learning-paths` | `learning-paths`, `enrollments`, `path-steps` | Umbrales 0-100 (por defecto 70/80/80 y 3 intentos, según el brief). Una inscripción por usuario y ruta (409). Un paso solo admite temas del curso de la ruta. |
| `content` | `resources` | Un recurso es `video` o `text` y necesita `url` o `content`. |
| `assessments` | `diagnostics`, `assessment-attempts`, `badges` | Un diagnóstico por inscripción. El número de intento y `passed` los calcula la API con los umbrales de la ruta; se rechaza pasar de `max_attempts`. El badge exige una evaluación final aprobada. |
| `observability` | `llm-call-logs` | Registro de cada llamada al LLM; solo se corrigen `status` y `error_message`. |
| `student` | `/me/enrollments...` (no tiene tablas propias) | Casos de uso del estudiante sobre lo suyo, con verificación de pertenencia. Ver [endpoints del estudiante](#endpoints-del-estudiante). |

### Errores

Formato RFC 9457 (`application/problem+json`): `type`, `title`, `status`, `detail`, `instance`, `code` y `request_id`.

| Situación | Estado | Ejemplo de `code` |
| --- | --- | --- |
| Cuerpo inválido | 422 | `VALIDATION_ERROR` (lista `errors` sin el valor recibido) |
| No existe | 404 | `NOT_FOUND` |
| Sin token o token inválido | 401 | `MISSING_TOKEN`, `INVALID_TOKEN` |
| Rol insuficiente o cuenta no habilitada | 403 | `INSUFFICIENT_ROLE`, `EMAIL_NOT_VERIFIED`, `ACCOUNT_DEACTIVATED` |
| Duplicado | 409 | `EMAIL_ALREADY_REGISTERED`, `ALREADY_ENROLLED`, `BADGE_ALREADY_ISSUED` |
| Regla de negocio o referencia inexistente | 422 | `PREREQUISITE_CYCLE`, `MAX_ATTEMPTS_EXCEEDED`, `TOPIC_NOT_FOUND` |

### Autenticación y roles

Cada petición a `/api/v1` lleva `Authorization: Bearer <access_token>`. La API valida la firma (RS256, llaves de Keycloak), `iss`, `aud` y `exp`; ve [`keycloak/README.md`](../keycloak/README.md) para el mapper de audiencia.

- `GET /api/v1/me` devuelve el usuario autenticado y sus roles. Lo propio del estudiante cuelga de `/api/v1/me/...` ([endpoints del estudiante](#endpoints-del-estudiante)). Cómo obtener un token: [Obtener un token y probar la API](#obtener-un-token-y-probar-la-api).
- El primer acceso de alguien que no existe en la base lo crea como `student`. Un usuario precreado por un administrador (por ejemplo el Administrador sembrado) se enlaza por su correo, que Keycloak debe tener verificado.
- Se autoriza con `user_roles`, no con los roles del token.

| Recurso | Lectura | Escritura |
| --- | --- | --- |
| `roles` | admin, teacher, student | admin |
| `users` | admin, teacher | admin |
| `user-roles`, `llm-call-logs` | admin | admin |
| `courses`, `topics`, `topic-prerequisites`, `learning-paths`, `resources` | admin, teacher, student | admin, teacher |
| `enrollments`, `path-steps`, `diagnostics`, `assessment-attempts`, `badges` | admin, teacher | admin, teacher |

Sin token: 401. Con token pero sin el rol: 403. `/health`, `/ready` y `/docs` son públicos. El CRUD genérico de inscripciones, pasos, diagnósticos, intentos y badges es del personal; los estudiantes gestionan lo suyo con los [endpoints del estudiante](#endpoints-del-estudiante).

### Endpoints del estudiante

Rutas bajo `/api/v1/me/...` para que cada usuario gestione **solo lo suyo**. Las puede usar cualquier rol autenticado (un docente también puede inscribirse). El usuario sale siempre del token: no se envía en la petición. Si un dato no es del usuario, la API responde **404** como si no existiera, para no revelar que existe.

| Método y ruta | Qué hace |
| --- | --- |
| `GET /me/enrollments` | Mis inscripciones activas (paginado) |
| `POST /me/enrollments` | Me inscribo en una ruta: `{"learning_path_id", "profile_description"?, "personal_objective"?}`. Una sola vez por ruta (409 `ALREADY_ENROLLED`); la ruta debe existir y estar activa |
| `GET /me/enrollments/{id}` | El detalle de mi inscripción |
| `PATCH /me/enrollments/{id}` | Actualizo `profile_description` y `personal_objective`. No se puede cambiar el estado ni otros campos. Una inscripción completada o abandonada se rechaza (422 `ENROLLMENT_CLOSED`) |
| `PATCH /me/enrollments/{id}/abandon` | Dejo la ruta. Una completada no se puede abandonar |
| `GET /me/enrollments/{id}/steps` | Mi ruta personalizada, en orden |
| `GET /me/enrollments/{id}/diagnostic` | Mi prueba diagnóstica |
| `PATCH /me/enrollments/{id}/diagnostic/answers` | Entrego las respuestas del diagnóstico: `{"answers"}`. Solo una vez (409 `ALREADY_SUBMITTED`) |
| `GET /me/enrollments/{id}/attempts` | Mis intentos de evaluación |
| `PATCH /me/enrollments/{id}/attempts/{attempt_id}/submit` | Entrego las respuestas de un intento: `{"answers"}`. Solo una vez |
| `GET /me/enrollments/{id}/badge` | Mi badge, si aprobé la evaluación final |

El estudiante **nunca fija puntajes ni resultados**: al entregar un intento solo se guardan sus respuestas y la fecha; el puntaje y la aprobación los calcula el sistema (o el personal) con el umbral de la ruta. Los diagnósticos, los pasos de la ruta y los intentos los genera el sistema (la capa de IA, pendiente) o el personal.

### Auditoría

Cada cambio queda en la tabla `<tabla>_audit`, con `app_user_id` igual al id del usuario autenticado. Mientras se resuelve o crea al usuario, se registra `identity:<sub>`.

### Fechas

`timestamptz` en la base y zona `America/Bogota`. La API devuelve ISO-8601 con desfase (`2026-10-07T09:30:00-05:00`) y exige fechas con zona horaria en las peticiones.

## Estructura

```text
api/
├── Dockerfile, pyproject.toml, uv.lock
├── app/
│   ├── main.py            # lifespan, middleware, errores, routers
│   ├── core/              # config, database, logging, middleware, errores HTTP, security (validación de tokens)
│   ├── auth/              # get_current_user, require_roles y la matriz de permisos (composición)
│   ├── common/            # base genérica: entidad, modelo, repositorio, servicio, fábrica de routers
│   ├── health/            # /health y /ready
│   └── domains/<dominio>/ # controller, schemas, dependencies, service, entities, repository, models, repository_impl
├── tests/
│   ├── unit/              # reglas de negocio con repositorios en memoria (sin base de datos)
│   └── integration/       # flujos HTTP contra la base smartmentor_test
└── scripts/dev.sh         # herramientas de desarrollo en contenedores
```

## Desarrollo y calidad

No hace falta instalar Python ni `uv`: todo corre en contenedores (la base debe estar arriba: `docker compose up -d postgres`).

```bash
api/scripts/dev.sh prepare-test-db   # crea y migra smartmentor_test (una vez, y tras nuevos changesets)
api/scripts/dev.sh format            # Ruff format
api/scripts/dev.sh lint              # ruff check + ruff format --check
api/scripts/dev.sh typecheck         # mypy en modo estricto
api/scripts/dev.sh test              # pytest (pasa argumentos: test -k attempts -x)
api/scripts/dev.sh all               # lint + typecheck + pytest
api/scripts/dev.sh lock              # regenera uv.lock tras cambiar dependencias
```

- Las pruebas de integración **solo corren sobre una base cuyo nombre termina en `_test`** y la vacían entre pruebas; nunca tocan `smartmentor`.
- Una prueba compara los modelos SQLAlchemy con el esquema que dejó Liquibase y falla si se desalinean.
- Tras agregar un changeset: `prepare-test-db` y luego `test`.

## Cómo agregar un recurso nuevo

1. Changeset de Liquibase con la tabla, su `_audit` y su trigger ([guía](../database/liquibase/README.md)).
2. En el dominio: `entities.py`, `models.py`, `schemas.py`, `repository.py`, `repository_impl.py` (con `constraint_messages`), `service.py`, `dependencies.py` y `controller.py` con `build_crud_router(...)`.
3. Registrar el router en `app/main.py` si es un dominio nuevo.
4. Pruebas unitarias de las reglas y de integración del flujo HTTP.
