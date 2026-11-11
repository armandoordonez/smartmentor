# SmartMentor

Plataforma de cursos adaptativos generados con IA: a partir de un syllabus genera un diagnóstico, una ruta de aprendizaje personalizada, recursos y evaluaciones, y otorga un badge al aprobar. Proyecto de grado de la Maestría en Ciencia de Datos; documento vivo que cada cohorte actualiza. El detalle del proyecto está en [`proyecto/brief.md`](proyecto/brief.md).

## Estado

Última revisión: 2026-11-10. El detalle por fase está en el [tablero del plan](PLAN_IMPLEMENTACION_V3.md#21-tablero-de-avance-del-plan).

| Componente | Estado |
| --- | --- |
| Base de datos (PostgreSQL 17 + pgvector, Liquibase `v2.0.x`: 39 tablas, usuarios de desarrollo y auditoría) | Listo |
| API de negocio (FastAPI): identidad, cursos, rutas, diagnóstico, intentos, badge, encuesta, contenido, evaluación humana, piloto y observabilidad | Listo |
| Servicio de IA (`ai/`: API + worker, proveedor `fake` o `gemini`, presupuesto, registro de llamadas, RAG, banco de ítems, videos) | Listo; probado con Gemini real solo en la estructuración del syllabus |
| Keycloak (realm v3 versionado, roles `learner`/`instructor`/`admin`, OTP para instructor y administrador, correo con Mailpit) | Listo |
| Interfaz Streamlit (`app/`): 13 páginas del aprendiz, 13 del instructor y 6 del administrador | Construida; falta revisión visual en navegador |
| Prompts y esquemas (`prompts/`), herramientas de evaluación (`notebooks/`, `data/eval`) | Listo |
| Integración de punta a punta con el LLM real (Fase 6) | En curso: detenida por el tope de gasto de Google AI Studio |
| Anotación de expertos, usabilidad y piloto (Fase 9b), revisión final (10) y cierre (11) | Pendiente |

Seguimiento: [`PLAN_IMPLEMENTACION_V3.md`](PLAN_IMPLEMENTACION_V3.md) (fuente vigente). [`proyecto/checklist.md`](proyecto/checklist.md) y [`HANDOFF.md`](HANDOFF.md) son anteriores a la versión 3 y se actualizan en la Fase 10.

## Requisitos

- Docker y Docker Compose v2.
- Nada más: Python, `uv`, Liquibase y las herramientas de calidad corren en contenedores.
- Para el servicio de IA con un modelo real: una clave de Gemini (`GEMINI_API_KEY`) y gasto habilitado en Google AI Studio. Sin ella, `AI_LLM_PROVIDER=fake` funciona sin red.

## Puesta en marcha (menos de 10 minutos)

```bash
cp .env.example .env            # luego completa los valores: cada variable está comentada
scripts/gen-secrets.sh          # genera contraseñas locales para lo que esté vacío
docker compose --profile mail --profile ai up -d --build   # postgres → liquibase → api, keycloak, app, ai, ai-worker, mailpit
keycloak/scripts/seed-dev-users.sh   # crea en Keycloak al instructor y al aprendiz de desarrollo (--with-admin añade al administrador)
```

Todos los secretos, usuarios, claves y modelos viven solo en `.env` (ignorado por git). `.env.example` queda sin credenciales.

| Servicio | URL | Para qué |
| --- | --- | --- |
| Interfaz | <http://localhost:8501> | Aplicación Streamlit; inicia sesión con Keycloak ([guía](app/README.md)) |
| API | <http://localhost:8020/docs> | Documentación interactiva y pruebas manuales |
| Servicio de IA | `localhost:8030` | Solo lo usa la API; no es público |
| Keycloak | <http://localhost:8180> | Consola de identidad ([guía](keycloak/README.md)) |
| Mailpit | <http://localhost:8025> | Bandeja de los correos de desarrollo |
| PostgreSQL | `localhost:5442` | `psql -h localhost -p 5442 -U <POSTGRES_USER> -d smartmentor` |

Los puertos se cambian en `.env` (`POSTGRES_PORT`, `API_PORT`, `KEYCLOAK_PORT`, `APP_PORT`, `AI_PORT`, `MAILPIT_UI_PORT`). Los contenedores tienen nombre fijo: solo se levanta un stack por máquina.

Comprobar que todo responde:

```bash
curl localhost:8020/health      # {"status":"ok"}
curl localhost:8020/ready       # base de datos y extensión vector disponibles
```

Todas las rutas de `/api/v1` exigen un bearer token de Keycloak: [`api/README.md`](api/README.md#obtener-un-token-y-probar-la-api).

## Calidad y pruebas

```bash
api/scripts/dev.sh prepare-test-db   # una vez
api/scripts/dev.sh all               # Ruff + mypy estricto + pytest (API)
app/scripts/dev.sh all               # lo mismo para la interfaz
ai/scripts/dev.sh all                # lo mismo para el servicio de IA
```

La integración continua (GitHub Actions) repite estas validaciones y además revisa Liquibase, prompts, el realm de Keycloak, el compose, la documentación y los secretos (gitleaks).

## Estructura

| Carpeta | Contenido |
| --- | --- |
| [`api/`](api/README.md) | API FastAPI y estándar de microservicios |
| [`database/`](database/README.md) | PostgreSQL, Liquibase, bootstrap, respaldos y modelo de datos |
| [`keycloak/`](keycloak/README.md) | Proveedor de identidad: realm versionado y guía de configuración |
| [`docs/adr/`](docs/adr/README.md) | Decisiones de arquitectura |
| [`proyecto/`](proyecto/README.md) | Brief y decisiones pendientes |
| [`app/`](app/README.md) | Interfaz en Streamlit (versión 3 del diseño) |
| [`ai/`](ai/README.md) | Servicio de IA: API, worker, tarifas y arnés de evaluación |
| [`prompts/`](prompts/README.md) | Prompts versionados y esquemas |
| [`data/`](data/README.md), [`notebooks/`](notebooks/README.md) | Datos de evaluación y métricas del piloto |
| [`scripts/`](scripts) | Generación de secretos y verificación de coherencia del `.env` |
| `PLAN_IMPLEMENTACION_V3.md` | Plan y tablero de avance |

## Trabajar en varios PC y trasladar datos

Lo que viaja con git: el código, los changelogs de Liquibase y el realm de Keycloak (`keycloak/realm/`, con roles y clientes; los usuarios y secretos se crean con los scripts). Un PC nuevo queda funcionando con los pasos de «Puesta en marcha».

Lo que **no** viaja con git: `.env` y los datos de PostgreSQL (`database/data/`), que incluyen la base de Keycloak. No se copian los archivos de datos en bruto: se trasladan con respaldos lógicos.

```bash
./database/scripts/backup.sh                               # genera smartmentor_*.dump y keycloak_*.dump
./database/scripts/restore.sh database/backups/<archivo>.dump   # restaura (reemplaza la base de destino)
```

Detalle y precauciones: [`database/README.md`](database/README.md), [`keycloak/README.md`](keycloak/README.md) y el [ADR 0005](docs/adr/0005-keycloak-postgres-realm-versioned.md).
