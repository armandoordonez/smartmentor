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
| Documentación interactiva (OpenAPI) | <http://localhost:8020/docs> (puerto `API_PORT`); el botón *Authorize* recibe el access token |
| Liveness / readiness | `GET /health`, `GET /ready` |
| API de negocio | `http://localhost:8020/api/v1/...` |
| Logs | JSON en la salida del contenedor: `docker logs -f smartmentor-api` |

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

- `GET /api/v1/me` devuelve el usuario autenticado y sus roles.
- El primer acceso de alguien que no existe en la base lo crea como `student`. Un usuario precreado por un administrador (por ejemplo el Administrador sembrado) se enlaza por su correo, que Keycloak debe tener verificado.
- Se autoriza con `user_roles`, no con los roles del token.

| Recurso | Lectura | Escritura |
| --- | --- | --- |
| `roles` | admin, teacher, student | admin |
| `users` | admin, teacher | admin |
| `user-roles`, `llm-call-logs` | admin | admin |
| `courses`, `topics`, `topic-prerequisites`, `learning-paths`, `resources` | admin, teacher, student | admin, teacher |
| `enrollments`, `path-steps`, `diagnostics`, `assessment-attempts`, `badges` | admin, teacher | admin, teacher |

Sin token: 401. Con token pero sin el rol: 403. `/health`, `/ready` y `/docs` son públicos. Los estudiantes consultan el catálogo; sus flujos propios (inscribirse, responder quizzes) llegarán con endpoints que verifican la pertenencia.

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
