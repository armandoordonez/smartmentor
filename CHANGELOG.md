# CHANGELOG

Cambios por versión y cohorte.

## v1.0-cohorte1 (2026-11-17)

Cierre de la cohorte 1. Las notas del GitHub Release, con las métricas, están en [`docs/cohorte_1/release.md`](docs/cohorte_1/release.md).

### Cierre de la cohorte 1 (2026-11-14 a 2026-11-17, PR 40 a 94)

- **Experimentos de evaluación (R-005):** E2, E3, E5, E6 y E7 con jueces-agente a ciegas, más E8 (latencia y costo) con el log real. Resultados en [`docs/cohorte_1/evaluation/results/`](docs/cohorte_1/evaluation/results/resumen-r005-2026-11-16.md). Herramientas `eval.syllabus_experiment` y `eval.video_experiment`, y cuentas `experimento_` para los recorridos.
- **Calidad del banco de preguntas (B-062):** formato y mezcla de opciones en código, `topic_quiz` v2 y v3, `diagnostic_generation` v2 y `final_assessment` v2 (medidas con E3b y E3c).
- **Apuntes y lecturas como fuentes del RAG (R-004 y R-010):** carga desde D1b y D2, retiro del RAG al quitarlos y top-k configurable (`AI_RAG_TOP_K`).
- **Videos (B-064 y E6):** «Buscar videos de nuevo» en D5e, diagnóstico de por qué un tema tiene pocos videos y `search_position` de YouTube en cada candidato.
- **Instructor:** «Rutas y avance» abre la ruta activa (B-058), archivar cursos con extracción fallida (B-066), `GET /courses/{id}` con el syllabus vigente (B-065), espera de 80 s configurable para cargar archivos (B-055) y minutos estimados del tema en D2b (T-057).
- **Aprendiz:** la renovación del token conserva el formulario y repite el clic (B-040), U1b desde el clic al reintentar el quiz (B-060), textos de E7c, E9c, E13 y E11 (B-059 y B-061) y `GET /me/study-goals` sin 404.
- **Rendimiento:** los listados de inscripciones leen en lote y no por fila (B-056 y B-063).
- **Visual:** diferencias con Figma corregidas en el aprendiz y el staff (V-088 a V-101).
- **Métricas:** cuaderno de la cohorte 1 sobre la base real (R-006) y el rol de métricas lee `interaction_events` y `assessment_items`.
- **Base compartida en Neon** para todo el equipo, con el esquema hasta el changeset `v2.0.1-010`.
- **Brief de la cohorte 1** ([`proyecto/cohorte_1/brief.md`](proyecto/cohorte_1/brief.md)): lo planteado frente a lo logrado (T-051).
- **Pasan a la siguiente fase:** el piloto con usuarios reales y lo que depende de él (E4, E9, E10, T-031, T-040, T-042, T-043, T-050, F-007) y la explicación alterna de E7b (B-049).

### Plan v3 (2026-11-07 a 2026-11-14)

Lo que sigue reemplaza la base v1 que se describe más abajo. El detalle por tarea, con fecha y hora, está en [`docs/cohorte_1/trazabilidad/`](docs/cohorte_1/trazabilidad/TRAZABILIDAD.md#cómo-se-lleva-este-registro).

- **Base de datos v2.0.0:** 39 tablas, roles `learner`, `instructor` y `admin`, y usuarios de mínimo privilegio por servicio ([ADR 0019](docs/adr/0019-least-privilege-db-users.md)).
- **API v2:** aprendiz, instructor, administrador, piloto, métricas y log del LLM ([contrato](docs/contracts/api-v2.md)). Cambios aditivos para las pantallas del instructor y del administrador (PR 3 y PR 6).
- **Servicio `ai/`:** trabajos asíncronos ([ADR 0010](docs/adr/0010-async-jobs-postgres-pull-ingestion.md)), syllabus, diagnóstico, objetivo, ruta, RAG, videos, bancos de preguntas y calificación con el LLM como juez. Probado con Gemini real el 2026-11-12. El timeout del LLM sube a 240 s (B-013).
- **Interfaz v3:** las 96 pantallas de Figma v3 rehechas en Streamlit ([ADR 0017](docs/adr/0017-frontend-rebuilt-from-figma-v3.md)). El instructor y el administrador ya leen la API real. La sesión dura 3 h y el token se renueva solo.
- **Keycloak v3:** realm sin secretos, OTP para el instructor y el administrador, y prueba de importación en la CI.
- **CI** con GitHub Actions para los tres servicios, Liquibase, el realm, los prompts, la documentación, gitleaks y Trivy.
- **Correcciones:**
  - el bloqueo entre la API y `ai/` (B-001);
  - AD1, AD4 y AD5 con la API real (B-003 a B-008);
  - el nivel del diagnóstico en D4 (B-010);
  - el reintento de la evaluación final, que ahora genera preguntas nuevas (B-011);
  - el flujo del aprendiz con la API real: catálogo, perfil, quiz y ruta (PR 5, B-015 a B-029);
  - Streamlit 1.67 y `pillow` 13.0.0, que cierran las 42 vulnerabilidades del `audit` de `app` (B-009).
- **Herramientas:** `scripts/simulate-learners.py` (aprendices simulados, solo para desarrollo) y la carpeta de seguimiento.

**Base v1 (2026-10, antes del plan v3).** Lo que sigue describe la primera versión.

### Base de datos

- Contenedor `smartmentor-postgres` (PostgreSQL 17 + pgvector 0.8.7) con volumen en `database/data/postgres`, reinicio automático y zona horaria `America/Bogota`.
- Liquibase 5.0.4 en contenedor. Versión de esquema `v1.0.0`: 14 tablas de negocio con su tabla `_audit` y trigger, secuencias propias, `active` y `created_at`, índices HNSW provisionales (D-01) y roles iniciales (`admin`, `teacher`, `student`). Todos los changesets tienen rollback.
- `users` sin contraseña; enlace opcional con un proveedor de identidad (`identity_provider`, `identity_subject`) para Keycloak (D-03).
- Scripts `backup.sh` (copias con fecha) y `bootstrap.sh` (crea la base si falta).

### API

- Microservicio FastAPI con 6 dominios y 14 recursos (CRUD con activar e inactivar, sin `DELETE`), reglas de negocio del brief, errores RFC 9457, logs JSON, `/health` y `/ready`. Dockerfile multi-etapa y servicio `api` en el compose.
- Pruebas unitarias y de integración contra `smartmentor_test`, Ruff y mypy estricto. Herramientas en contenedores con `api/scripts/dev.sh`.

### Identidad

- Esquema `v1.0.1`: usuario `Administrador` (`admin.smartmentor@yopmail.com`) con rol `admin`.
- Keycloak 26.8.0 en el compose. Sus datos están en una base `keycloak` del PostgreSQL del proyecto, con su propio rol; el realm `smartmentor` está versionado en `keycloak/realm/` y se importa solo en un PC nuevo ([ADR 0005](docs/adr/0005-keycloak-postgres-realm-versioned.md)). `backup.sh` respalda ambas bases y `restore.sh` las restaura.
- Autenticación de la API con bearer tokens de Keycloak ([ADR 0004](docs/adr/0004-authentication-keycloak-bearer.md)): validación RS256 por JWKS, enlace por `sub` o correo verificado, alta automática de estudiantes, autorización por `user_roles` y endpoint `/me`. Se elimina la cabecera temporal `X-User-Id`: la auditoría usa el id del usuario autenticado.
- Cierra D-03. Incluye una prueba de punta a punta con tokens reales.
- Generación de tokens para desarrollo ([guía](api/README.md#obtener-un-token-y-probar-la-api)): Swagger UI con login de usuario y contraseña (o token pegado), `api/scripts/token.sh` y una colección de Postman que pide el token antes de cada petición. Usan el cliente `smartmentor-dev-tools`, solo para desarrollo.

### Estudiante

- Endpoints `/api/v1/me/enrollments...` para que el estudiante gestione lo suyo: inscribirse, ver y actualizar su inscripción, abandonarla, ver su ruta, entregar el diagnóstico y los intentos, y ver su badge. Verifican la pertenencia y el estudiante nunca fija puntajes. Dominio nuevo `student`; 148 pruebas en total.

### Interfaz

- Decisión: interfaz en **Streamlit** ([ADR 0006](docs/adr/0006-frontend-streamlit.md)). Arquitectura en `app/README.md`: capas, autenticación con Keycloak (cliente confidencial `smartmentor-ui`), caché solo para datos públicos, datos de ejemplo para la Fase 0 y análisis de la guía de referencia. Sin código todavía.
- Prototipo de la Fase 0 en Streamlit, a partir del [diseño de Figma](https://www.figma.com/design/wIzBv0tOtRaoVmldEXPyff/SmartMentor-%C2%B7-Prototipo-Fase-0-v2--Estudiante--Docente--Admin-?node-id=0-1): 23 pantallas del estudiante, el docente y el admin (sin las de login), con datos de ejemplo que simulan la API y sus reglas (`APP_DATA_SOURCE=sample`). Se entra eligiendo un rol. Tema con los tokens del diseño en `.streamlit/config.toml`, sin CSS; reglas de Figma a Streamlit en `app/CLAUDE.md`. Dockerfile, herramientas en contenedores (`app/scripts/dev.sh`), Ruff, mypy estricto y 36 pruebas (unitarias y de páginas con `AppTest`). Servicio `app` en el compose (`http://localhost:8501`, `APP_PORT` en `.env`).

### Documentación

- Lista de verificación del brief con responsables y avance (`checklist.md`, con su script `avance.sh`). Se retiró al cierre de la cohorte 1: los responsables están en el [brief de la cohorte](proyecto/cohorte_1/brief.md#12-gestión-del-proyecto) y el avance en la [trazabilidad](docs/cohorte_1/trazabilidad/TRAZABILIDAD.md).

- ADR 0001 a 0003, `docs/cohorte_1/decisiones.md` y estándar de microservicios FastAPI (rev. 2).
