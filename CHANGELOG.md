# CHANGELOG

Cambios por versión y cohorte.

## Sin publicar (cohorte 1)

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

- `proyecto/checklist.md`: lista de verificación del brief con responsables, avance de la fase y comparación de frontends (Streamlit y Next.js); `proyecto/scripts/avance.sh` calcula el avance.

- ADR 0001 a 0003, `proyecto/decisiones-pendientes.md` y estándar de microservicios FastAPI (rev. 2).
