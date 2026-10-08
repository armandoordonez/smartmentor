# SmartMentor

Plataforma de cursos adaptativos generados con IA: a partir de un syllabus genera un diagnóstico, una ruta de aprendizaje personalizada, recursos y evaluaciones, y otorga un badge al aprobar. Proyecto de grado de la Maestría en Ciencia de Datos; documento vivo que cada cohorte actualiza. El detalle del proyecto está en [`proyecto/brief.md`](proyecto/brief.md).

## Estado

| Componente | Estado |
| --- | --- |
| Base de datos (PostgreSQL 17 + pgvector, Liquibase v1.0.1) | Listo |
| API de negocio (FastAPI): 6 dominios, 14 recursos, CRUD con borrado lógico | Listo |
| Keycloak (sobre el mismo PostgreSQL, realm versionado en git) | Listo |
| Endpoints del estudiante (inscribirse, ver su ruta, entregar respuestas, ver su badge) | Listo |
| Autenticación con Keycloak y bearer tokens, roles de la aplicación | Listo ([ADR 0004](docs/adr/0004-authentication-keycloak-bearer.md)); falta configurar el mapper de audiencia en tu Keycloak |
| Capa de IA (`ai/`), prompts, interfaz (`app/`), endpoints de estudiante | Pendiente |

Seguimiento de tareas con responsables y porcentaje de avance: [`proyecto/checklist.md`](proyecto/checklist.md). Deuda técnica y próximos pasos: [`HANDOFF.md`](HANDOFF.md).

## Requisitos

- Docker y Docker Compose.
- Nada más: Python, `uv`, Liquibase y las herramientas de calidad corren en contenedores.

## Puesta en marcha (menos de 10 minutos)

```bash
cp .env.example .env           # reemplaza POSTGRES_PASSWORD y DATABASE_PASSWORD (iguales) y KEYCLOAK_ADMIN_PASSWORD
docker compose up -d --build   # postgres → liquibase update → api, y keycloak
```

| Servicio | URL | Para qué |
| --- | --- | --- |
| API | <http://localhost:8020/docs> | Documentación interactiva y pruebas manuales |
| Keycloak | <http://localhost:8180> | Consola de identidad ([guía](keycloak/README.md)) |
| PostgreSQL | `localhost:5442` | `psql -h localhost -p 5442 -U smartmentor -d smartmentor` |

Los puertos (5442, 8020, 8180) se cambian en `.env`; se eligieron porque 5432, 8000 y 8080 suelen estar ocupados.

**Antes de usar la API con un frontend**, configura Keycloak (realm, roles, mapper de audiencia, tu usuario administrador con correo verificado): [`keycloak/README.md`](keycloak/README.md). Todas las rutas de `/api/v1` exigen un bearer token. Cómo obtenerlo y probar con Swagger, la terminal o Postman: [`api/README.md`](api/README.md#obtener-un-token-y-probar-la-api).

Comprobar que todo responde:

```bash
curl localhost:8020/health      # {"status":"ok"}
curl localhost:8020/ready       # base de datos y extensión vector disponibles
curl -H "Authorization: Bearer $(api/scripts/token.sh tu@correo.com)" localhost:8020/api/v1/me   # tu usuario y roles
```

## Calidad y pruebas

```bash
api/scripts/dev.sh prepare-test-db   # una vez
api/scripts/dev.sh all               # Ruff + mypy estricto + pytest
```

## Estructura

| Carpeta | Contenido |
| --- | --- |
| [`api/`](api/README.md) | API FastAPI y estándar de microservicios |
| [`database/`](database/README.md) | PostgreSQL, Liquibase, bootstrap, respaldos y modelo de datos |
| [`keycloak/`](keycloak/README.md) | Proveedor de identidad: realm versionado y guía de configuración |
| [`docs/adr/`](docs/adr/README.md) | Decisiones de arquitectura |
| [`proyecto/`](proyecto/README.md) | Brief y decisiones pendientes |
| `app/`, `ai/`, `prompts/`, `data/`, `notebooks/`, `design/`, `tests/` | Por construir en las siguientes fases |

## Trabajar en varios PC y trasladar datos

Lo que viaja con git: el código, los changelogs de Liquibase y el realm de Keycloak (`keycloak/realm/`, con roles, clientes y usuarios de prueba). Un PC nuevo queda funcionando con `cp .env.example .env` y `docker compose up -d --build`.

Lo que **no** viaja con git: `.env` y los datos de PostgreSQL (`database/data/`), que incluyen la base de Keycloak. No se copian los archivos de datos en bruto: se trasladan con respaldos lógicos.

```bash
./database/scripts/backup.sh                               # genera smartmentor_*.dump y keycloak_*.dump
./database/scripts/restore.sh database/backups/<archivo>.dump   # restaura (reemplaza la base de destino)
```

Detalle y precauciones: [`database/README.md`](database/README.md), [`keycloak/README.md`](keycloak/README.md) y el [ADR 0005](docs/adr/0005-keycloak-postgres-realm-versioned.md). El realm versionado contiene secretos de **datos de prueba**; ver la advertencia antes de usar datos reales.
