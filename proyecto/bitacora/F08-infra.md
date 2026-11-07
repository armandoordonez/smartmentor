# Bitácora F08 · Keycloak, infraestructura y CI

Rama: `feature/infra-compose-ci-keycloak` (desde `origin/dev`). Agente: `infra` (Ola 1). Fase 8 del plan.

## Hecho

| Bloque | Contenido |
| --- | --- |
| Realm v3 (`keycloak/realm/smartmentor-realm.json`) | Roles `learner`, `instructor`, `admin` (`learner` por defecto, sin `student` ni `teacher`); autorregistro con `verifyEmail`; fuerza bruta; política de contraseñas; flujo `browser-role-otp` (OTP obligatorio con `instructor` o `admin`, una sola vez si tiene ambos); clientes `smartmentor-ui`, `smartmentor-ai`, `smartmentor-api-service`; se borró `http://localhost:8081/*`; secretos y correo con `${VARIABLE}` |
| Scripts de Keycloak | `sanitize-realm.py` (pone marcadores y `--check`), `export-realm.sh`, `apply-secrets.sh` (rotación con kcadm), `check-realm-import.sh` y `verify-realm.py` (importación en Keycloak desechable) |
| `scripts/` | `gen-secrets.sh` (solo secretos vacíos, idempotente, sin imprimir valores), `test-gen-secrets.sh`, `check-env-coherence.py` |
| Compose y `.env.example` | Perfiles `ai` (`ai` y `ai-worker`) y `mail` (Mailpit); `app` depende de `api` y `keycloak`; Keycloak con `KC_HOSTNAME` y `KC_HOSTNAME_BACKCHANNEL_DYNAMIC`; credenciales con `${VAR:?}`; Liquibase como `OWNER_DATABASE_*`; `EMBEDDING_DIMENSION` 768 (pedido del agente `database`) |
| CI | Trabajos nuevos `ai`, `prompts`, `infra`, `keycloak-realm`, `docs`, `secrets`, `audit`, `images`; `.markdownlint-cli2.jsonc`, `lychee.toml`, `.gitleaks.toml`; `dependabot.yml` y `.pre-commit-config.yaml` con `ai/` |
| Documentación | `keycloak/README.md` reescrito (administrador, OTP, correo, rotación) |

Commits: `fc1b43d` (realm), el del compose y scripts, y los posteriores de la rama.

## Desviaciones frente al plan o al brief

- **`smartmentor-api` pasa a *bearer only*** (sin secreto): el plan pedía «secreto regenerado», pero la API no usa el secreto, así que se elimina en vez de rotarlo.
- **`smartmentor-frontend` se conserva solo para Postman** (PKCE, sin URI de 8081); `smartmentor-dev-tools` se conserva (solo desarrollo).
- **Registro sin campo de contraseña**: con `verifyEmail` Keycloak 26.8.0 no pide la contraseña en el formulario; la persona la define después de verificar el correo (`UPDATE_PASSWORD`). Es más seguro y coherente con G-01, pero cambia la pantalla A3 de Figma (observado, no configurado).
- **Reflejo de roles (G-03 / ADR 0014)**: la API necesitará una credencial de administración de Keycloak. NO la creé: reutilizar `smartmentor-api-service` sería peligroso (su token viaja a `ai/`). Propuesta: un cuarto cliente `smartmentor-api-admin` con `manage-users` y `view-realm` y su propio secreto, a decidir en la Fase 3.
- **`APP_DATA_SOURCE` queda en `sample`** (único valor que acepta hoy `app/`); el Anexo D dice `api`.
- **Usuarios de base**: nombres fijos `smartmentor_owner/api/ai` en `.env.example` (los usa el changeset 045); `POSTGRES_USER` sigue siendo el superusuario del contenedor y se define a mano.
- Las claves de LLM, los modelos y los topes del servicio `ai` son opcionales en el compose (`:-`), porque solo importan para el proveedor elegido; las credenciales de base y los secretos de Keycloak son obligatorios.

## Decisiones

- **Sustitución `${VAR}` en la importación: SÍ funciona** (Keycloak 26.8.0, contenedor desechable). Sustituye secretos de cliente y `smtpServer`; respeta marcadores propios como `${role_default-roles}`. Riesgo comprobado: **una variable ausente queda como texto literal** (secreto `${X}`). Mitigación: el compose declara esas variables con `:?`. Como la importación se omite si el realm existe, se escribió `apply-secrets.sh` para rotar.
- **OTP por rol sin duplicar**: dos subflujos condicionales (rol `instructor`; rol `admin` y NO `instructor`). Alternativa descartada: hacer a `admin` compuesto de `instructor` (ensucia los roles).
- **Flujo propio `browser-role-otp`** en lugar de editar el `browser` de fábrica (los flujos *builtIn* no se modifican bien al importar).
- **Mailpit con `MP_SMTP_AUTH_ACCEPT_ANY`**: el realm siempre autentica; en desarrollo se usan credenciales cualesquiera.
- **Contexto de construcción de `ai` en la raíz** (`dockerfile: ai/Dockerfile`) porque la imagen necesita `prompts/`; `.dockerignore` ya estaba pensado así.
- **Herramientas de CI por imagen de Docker con versión fijada** (markdownlint-cli2 v0.18.1, lychee 0.22.0, gitleaks v8.30.1, Trivy 0.67.2, actionlint 1.7.7): se verificó que existen; evitan acciones de terceros.
- **gitleaks**: archivos actuales + solo los commits nuevos respecto a `dev` (el historial anterior está «dado por rotado»). `.gitleaks.toml` exime `design/**/variables.json` (falso positivo `generic-api-key`).
- **Auditoría de dependencias y Trivy son informativas** (`continue-on-error`).
- **Verificador de enlaces sin red** (`offline = true`) para que no dependa de sitios externos.
- **markdownlint**: se desactivan reglas de estilo (MD004, MD013, MD024, MD025, MD029, MD032, MD033, MD036, MD041, MD060) y se excluye lo histórico; excepciones temporales explícitas (ver abajo).

## Problemas y lecciones

- Python 3.10 del sistema no parsea sintaxis de 3.12 (`class X[T]`): `check-env-coherence.py` salta archivos que no parsea salvo que definan `BaseSettings`; la CI lo corre con Python 3.12.
- `cookielib` de Python descarta las cookies de `localhost`: `verify-realm.py` las maneja a mano.
- El aislamiento del worktree rechaza muchas construcciones de shell (`$PWD`, heredocs, nombres como «gitleaks»); se usaron scripts auxiliares en el scratchpad.
- Con `docker-compose.yml` actual y `container_name` fijos no se pudo levantar el stack completo sin chocar con el del dueño: la validación del compose fue `config` y la del realm un Keycloak desechable.

## Métricas

- Realm: importa sin errores en Keycloak 26.8.0; `check-realm-import.sh --functional`: **31 comprobaciones, 0 fallos**, 48 s. Login: aprendiz sin OTP; instructor, admin y ambos van a `CONFIGURE_TOTP`. El registro crea el usuario con `VERIFY_EMAIL` + `UPDATE_PASSWORD` y rol efectivo `learner`. Llaves RSA generadas al importar; 0 usuarios. Token de `smartmentor-api-service`: `aud` incluye `smartmentor-ai`.
- Rotación: `apply-secrets.sh` restauró los dos secretos y el correo tras alterarlos en el Keycloak desechable.
- `docker compose config`: válido sin perfiles y con `ai` + `mail`; con `.env.example` vacío se niega y lista 13 variables obligatorias faltantes.
- `check-env-coherence.py`: 67 variables documentadas, 62 referencias del compose, 17 variables de `Settings`: coherente (4 futuras: `APP_CONTEXT_PROFILE`, `ORGANIZATION_NAME`, `BADGE_ISSUER_NAME`, `BADGE_ISSUER_URL`). Probado en negativo.
- `gen-secrets.sh`: `test-gen-secrets.sh` correcto (no pisa, longitudes, permisos 600, idempotente, la salida no contiene valores).
- markdownlint: 44 archivos, 0 errores; lychee: 275 enlaces correctos, 0 errores; actionlint: sin hallazgos; ShellCheck (-S warning): sin hallazgos; gitleaks sobre archivos actuales: limpio.
- Auditoría de dependencias (informativa, hoy): `api` — dnspython 2.8.0 (GHSA-45c3-73f7-pv4m, corrige 2.9.0); `app` — pillow 12.3.0 con 6 avisos o más (corrige 13.0.0); `ai` — ninguno.

## Adenda: usuario de métricas (pedido de database, commit 0745800)

- `.env.example`: `METRICS_DATABASE_USER=smartmentor_metrics` (fijo, lo usa el changeset), `METRICS_DATABASE_PASSWORD` vacía y `METRICS_DATABASE_URL` (la lee el notebook; va en la lista de variables futuras de `check-env-coherence.py`).
- Compose: ambas variables pasan a `postgres` con `:-` (NO obligatorias: sin contraseña el bootstrap no crea el rol).
- `gen-secrets.sh` genera `METRICS_DATABASE_PASSWORD` si está vacía (el dueño puede dejarla vacía borrando la línea tras ejecutarlo si no usa métricas, o no ejecutar el paso).

## Adenda: interfaz v3 (pedido de app-core, commit 7468148)

- CI, trabajo `app`: `APP_DATA_SOURCE: fixtures`.
- Compose `app`: `APP_DATA_SOURCE` por defecto `api`, `APP_ENV`, `APP_PUBLIC_URL`, `APP_CONTEXT_PROFILE`, `ORGANIZATION_NAME`, `PILOT_WINDOW_TEXT`, `API_BASE_URL`, `OIDC_SERVER_METADATA_URL`, `OIDC_UI_CLIENT_ID/SECRET` y `APP_COOKIE_SECRET`, con los nombres de `app/src/core/config.py` de esa rama.
- Los secretos de la app van con `:-` (Compose no permite condicionar `:?` a otra variable): la app falla nombrando la variable. `OIDC_UI_CLIENT_SECRET` sigue siendo obligatorio en el servicio `keycloak`.
- Desviación: `API_BASE_URL` por defecto `http://api:8000`, no `:8020` (8020 es el puerto publicado en el anfitrión; dentro de la red la API escucha en 8000). `app/README.md` de esa rama dice 8020 y debe corregirse.
- `APP_CONTEXT_PROFILE` y `ORGANIZATION_NAME` salieron de la lista de variables futuras; `.env.example` deja `ORGANIZATION_NAME` y `APP_CONTEXT_PROFILE` donde estaban.

## Adenda: API v2 (pedido de api-core, commit 9cb4877)

- Servicio `api`: `APP_CONTEXT_PROFILE`, `REQUIRE_SECOND_FACTOR` (false por defecto), `AI_SERVICE_MODE` (fake), `AI_SERVICE_URL`, `AI_SERVICE_CLIENT_ID`, `AI_SERVICE_CLIENT_SECRET`, `AI_SERVICE_TOKEN_URL` (por defecto interna de Keycloak), `AI_SERVICE_TIMEOUT_SECONDS`, `AI_SWEEP_INTERVAL_SECONDS`; se quitó `EMBEDDING_DIMENSION` de ese servicio (sigue en `ai`).
- Decisión: en `.env` se conservan los nombres del Anexo D (`AI_BASE_URL`, `AI_CLIENT_ID`, `AI_CLIENT_SECRET`, que también usa el realm) y el compose los entrega a la API como `AI_SERVICE_*`. `.env.example` agrega `AI_SERVICE_MODE`, `AI_SERVICE_TOKEN_URL`, `AI_SERVICE_TIMEOUT_SECONDS`, `AI_SWEEP_INTERVAL_SECONDS` y `REQUIRE_SECOND_FACTOR`.
- `REQUIRE_SECOND_FACTOR` queda en false: activarlo exige comprobar que el token de Keycloak trae `amr`/`acr` con OTP (no verificado aquí; el flujo `browser-role-otp` no configura ese claim).
- CI, trabajo `api`: usa `ci_user` (superusuario del servicio efímero) para Liquibase y pytest; los roles `smartmentor_*` no existen allí y el changeset de permisos los omite con aviso. Se agregó `SEED_ADMIN_EMAIL` de prueba al paso de Liquibase. `api/scripts/dev.sh` (de `api`) carga `.env` con nombres antiguos (`DATABASE_*` desde `POSTGRES_*`); la CI no lo usa.

## Prueba en seco de la integración

Rama temporal desde `origin/dev` fusionando `database-v2-rebase`, `api-v2-identity-courses`, `app-v3-core` e `infra-compose-ci-keycloak` (eliminada, no publicada): **0 conflictos de fusión**. `docker compose config` válido con y sin perfiles y el compose vacío se niega a arrancar. La coherencia del `.env` detectó 3 ajustes internos de `Settings` sin documentar (`SYLLABUS_MAX_BYTES`, `IDEMPOTENCY_TTL_SECONDS`, `APP_FIXTURES_DIR`); se agregaron a `SETTINGS_INTERNAL` en `check-env-coherence.py`. `ai/Dockerfile` aún no existe: el perfil `ai` no se puede construir.

## Impacto en el brief

- **Seguridad / identidad**: el brief debe decir que el autorregistro exige correo verificado, que hay OTP obligatorio para instructor y administrador y protección de fuerza bruta.
- **Despliegue**: el piloto necesita una cuenta SMTP (contraseña de aplicación de Google) o Mailpit en desarrollo; los secretos viven solo en `.env` y se generan con `scripts/gen-secrets.sh`.
- **Calidad**: la CI incluye pruebas de `ai`, hashes de prompts, Markdown, enlaces, secretos y escaneo de imágenes.

## Cambios pedidos a archivos compartidos y a otros agentes

- **database** (aplicado aquí): `postgres` recibe `OWNER_/API_/AI_DATABASE_*`; `liquibase` usa `OWNER_DATABASE_*` y `SEED_ADMIN_EMAIL`; `EMBEDDING_DIMENSION` 768. Con un volumen existente los roles solo se crean con `database/scripts/bootstrap.sh` o `reset-app-schema.sh` (documentado en `keycloak/README.md` y en `.env.example`).
- **api**: el compose entrega `DATABASE_USER/PASSWORD` desde `API_DATABASE_*`, y `AI_BASE_URL`, `AI_CLIENT_ID`, `AI_CLIENT_SECRET`; falta una URL interna del endpoint de tokens (hoy solo se conoce `OIDC_JWKS_URL`; con `KC_HOSTNAME_BACKCHANNEL_DYNAMIC` sirve `http://keycloak:8080/realms/smartmentor/protocol/openid-connect/token`). Decidir el cliente de administración (arriba). Sus pruebas leen `DATABASE_*` en `.env`: `api/scripts/dev.sh` carga `POSTGRES_*` y habrá que actualizarlo.
- **ai**: debe existir `ai/Dockerfile` (contexto en la raíz, copia `prompts/`, usuario no root, `HEALTHCHECK` en `/health`), comando `uvicorn app.main:app --port 8030` y `python -m app.worker`. El compose le pasa `AI_DATABASE_*`, `DATABASE_HOST/PORT/NAME`, `OIDC_*`, `AI_SERVICE_AUDIENCE`, `AI_LLM_*`, `AI_EMBEDDING_*`, `EMBEDDING_DIMENSION`, claves y topes; si su `Settings` usa otros nombres, `check-env-coherence.py` lo señalará. El worker no tiene `HEALTHCHECK` (se anula el de la imagen).
- **app**: recibe `APP_COOKIE_SECRET`, `OIDC_UI_CLIENT_ID/SECRET` y `OIDC_ISSUER_URL`; debe aceptar `APP_DATA_SOURCE=api` cuando implemente el login y avisar para cambiar el valor del ejemplo.
- **Excepciones temporales de markdownlint** (los dueños deben corregir y quitarlas de `.markdownlint-cli2.jsonc`): `database/README.md` línea 184 (tabla con columnas de más, MD056) y `docs/adr/0001-postgres-pgvector.md` (falta línea en blanco bajo tres encabezados, MD022).
- **Dueño del proyecto**: ejecutar `scripts/gen-secrets.sh` sobre su `.env`, definir a mano `POSTGRES_USER`, `KEYCLOAK_ADMIN`, `KEYCLOAK_DB_USER`, `SMTP_FROM` y los datos de correo; recrear su realm de Keycloak (`DROP SCHEMA`) para recibir el realm v3; crear el administrador con OTP. Actualizar las dependencias señaladas (dnspython, pillow).
