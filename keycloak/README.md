# keycloak/

Proveedor de identidad de SmartMentor: **Keycloak 26.8.0** (OpenID Connect) en un contenedor. La aplicación **no guarda contraseñas**: delega el inicio de sesión en Keycloak, y la API valida los tokens que emite ([ADR 0004](../docs/adr/0004-authentication-keycloak-bearer.md)). Cómo se guardan y se trasladan sus datos: [ADR 0005](../docs/adr/0005-keycloak-postgres-realm-versioned.md). Autenticación entre servicios, registro abierto y segundo factor: [ADR 0014](../docs/adr/0014-service-to-service-auth-client-credentials.md).

## Estructura

```text
keycloak/
├── README.md                    # este documento
├── realm/
│   └── smartmentor-realm.json   # el realm: roles, clientes, flujos y mappers; SIN usuarios, secretos ni llaves (en git)
└── scripts/
    ├── export-realm.sh          # exporta el realm de la consola al archivo anterior (pasa por sanitize-realm.py)
    ├── sanitize-realm.py        # quita usuarios, secretos y llaves de un export, pone los marcadores ${VARIABLE} y comprueba (--check)
    ├── apply-secrets.sh         # aplica a un Keycloak ya importado los secretos y el correo de .env (rotación)
    ├── check-realm-import.sh    # importa el realm en un Keycloak desechable y lo verifica (lo usa la CI)
    └── verify-realm.py          # las comprobaciones sobre la API de administración
```

Keycloak **no tiene volumen propio**: guarda todo en la base `keycloak` del PostgreSQL del proyecto (`database/data/`), con su propio rol (`KEYCLOAK_DB_USER`), separada de la base `smartmentor`.

## Arranque

```bash
cp .env.example .env && scripts/gen-secrets.sh     # una vez; completa a mano lo que el script indique
docker compose up -d        # postgres → (liquibase) → keycloak, que importa el realm si no existe
```

| Dato | Valor |
| --- | --- |
| Consola de administración | <http://localhost:8180> (puerto `KEYCLOAK_PORT` de `.env`) |
| Administrador de la consola (realm `master`) | `KEYCLOAK_ADMIN` y `KEYCLOAK_ADMIN_PASSWORD` de `.env` |
| Realm de la aplicación | `smartmentor`, <http://localhost:8180/realms/smartmentor> |
| URL pública | `KC_HOSTNAME` (por defecto `http://localhost:KEYCLOAK_PORT`) con `KC_HOSTNAME_BACKCHANNEL_DYNAMIC=true`: el `iss` de los tokens es la URL pública y la API puede llamar a Keycloak por `keycloak:8080` |
| Modo | `start-dev` (HTTP). Para producción se usa `start` con HTTPS |
| Base de datos | `keycloak` en el PostgreSQL del proyecto (`jdbc:postgresql://postgres:5432/keycloak`) |

El administrador de la consola se crea solo en el primer arranque con base vacía. Si cambias `KEYCLOAK_ADMIN_PASSWORD` en `.env` después, no tiene efecto: cámbiala desde la consola.

## Qué trae el realm `smartmentor`

### Roles

`learner` (Aprendiz), `instructor` (Instructor) y `admin` (Administrador). Reemplazan a `student` y `teacher` ([ADR 0021](../docs/adr/0021-neutral-roles-and-label-glossary.md)). `learner` es parte del rol por defecto: toda persona que se registra lo recibe.

Los roles de Keycloak sirven para decidir el segundo factor. **La API autoriza con `user_roles` de su base de datos** (la base manda, DEF-27) y refleja allí los cambios de rol en Keycloak.

### Registro, correo y contraseñas (G-01, G-02)

| Ajuste | Valor |
| --- | --- |
| Autorregistro | Habilitado. La pantalla pide nombre, apellido y correo (que es el nombre de usuario) |
| Correo verificado | Obligatorio (`verifyEmail`). Con esta opción, Keycloak 26.8 deja la contraseña para después de verificar el correo: el usuario nuevo queda con las acciones `VERIFY_EMAIL` y `UPDATE_PASSWORD`, así que solo dueño del buzón elige la contraseña |
| Fuerza bruta | Activada: bloqueo temporal tras 5 fallos (espera de 1 a 15 minutos) |
| Política de contraseñas | Mínimo 12 caracteres, mayúscula, minúscula y dígito; distinta del usuario y del correo; sin repetir las últimas 3 |
| Recuperar contraseña | Habilitado (necesita el correo configurado) |

### Segundo factor (OTP) por rol

El realm usa el flujo de login `browser-role-otp`: usuario y contraseña, y después **OTP obligatorio para quien tenga el rol `instructor` o `admin`**. Quien tenga ambos roles lo introduce una sola vez. Un aprendiz entra sin OTP. La primera vez que una persona con esos roles inicia sesión, Keycloak le muestra el código QR para configurarlo con su aplicación de autenticación (Google Authenticator, FreeOTP...).

Implementación: dos subflujos condicionales, uno con *Condition - user role* `instructor` y otro con `admin` y NO `instructor` (así no se pide dos veces). El flujo directo (`direct grant`) del cliente `smartmentor-dev-tools` no pide OTP: por eso la API, además, **exige en las rutas de instructor y admin que el token indique un segundo factor** (ADR 0014).

Comprobado con un Keycloak desechable (`check-realm-import.sh --functional`): el aprendiz recibe el código de autorización sin OTP, y el instructor, el administrador y quien tiene ambos son enviados a configurar el OTP.

### Clientes

| Cliente | Tipo | Para qué |
| --- | --- | --- |
| `smartmentor-ui` | Confidencial, *Standard flow*, URI de retorno `http://localhost:8501/oauth2callback`, mapper de audiencia `smartmentor-api` | La interfaz en Streamlit ([ADR 0006](../docs/adr/0006-frontend-streamlit.md)): corre en el servidor y guarda el secreto (`OIDC_UI_CLIENT_SECRET`) |
| `smartmentor-api-service` | Confidencial con cuenta de servicio (*client credentials*), mapper de audiencia `smartmentor-ai` | La API pide con él el token para llamar a `ai/` (secreto `AI_CLIENT_SECRET`) |
| `smartmentor-ai` | *Bearer only* | Solo define la audiencia (`aud`) que `ai/` exige. Sin secreto |
| `smartmentor-api` | *Bearer only* | Solo define la audiencia de la API. Sin secreto: la API valida tokens y no hace introspección |
| `smartmentor-frontend` | Público con PKCE | Solo Postman (`https://oauth.pstmn.io/v1/callback`). Se borró `http://localhost:8081/*` |
| `smartmentor-dev-tools` | Público, solo *Direct access grants*, token de 30 minutos, *Web origin* `http://localhost:8020` | **Solo desarrollo.** Permite que Swagger, `api/scripts/token.sh` y Postman pidan un token con usuario y contraseña. **No debe existir en producción** (ver abajo) |

Si cambias `APP_PORT`, agrega también la URI de retorno y el *Web origin* de `smartmentor-ui` con ese puerto (consola, luego `export-realm.sh`).

## Secretos y correo: variables en el realm

El realm versionado **no contiene ningún secreto**. Donde hace falta uno hay un marcador `${VARIABLE}` que Keycloak sustituye con las variables de entorno de su contenedor **al importar el realm** (comprobado experimentalmente en Keycloak 26.8.0 con un contenedor desechable: sustituye en secretos de cliente y en `smtpServer`, y deja intactos los textos propios como `${role_default-roles}`).

| Marcador | Variable de `.env` | Dónde |
| --- | --- | --- |
| `${OIDC_UI_CLIENT_SECRET}` | `OIDC_UI_CLIENT_SECRET` | secreto del cliente `smartmentor-ui` |
| `${AI_CLIENT_SECRET}` | `AI_CLIENT_SECRET` | secreto del cliente `smartmentor-api-service` |
| `${SMTP_HOST}`, `${SMTP_PORT}`, `${SMTP_STARTTLS}`, `${SMTP_USER}`, `${SMTP_PASSWORD}`, `${SMTP_FROM}`, `${SMTP_FROM_DISPLAY_NAME}` | las `SMTP_*` homónimas | sección de correo del realm |

Dos advertencias importantes:

1. **Si una variable falta, Keycloak guarda el marcador como texto literal** (el secreto del cliente sería la cadena `${...}`, públicamente conocida). Por eso el compose declara los secretos con `${VAR:?...}` y se niega a arrancar sin ellos.
2. **La sustitución solo ocurre al importar**, y la importación se omite si el realm ya existe. Cambiar `.env` después no cambia un Keycloak ya creado: para eso está `apply-secrets.sh` (sección «Rotar»).

### Correo con Google o con Mailpit

Producción y piloto (plan 18.6): servidor `smtp.gmail.com`, puerto `587` con STARTTLS, `SMTP_USER` la cuenta de Google que envía, `SMTP_PASSWORD` una **contraseña de aplicación** (exige la verificación en dos pasos en esa cuenta), `SMTP_FROM` el remitente. Una cuenta personal tiene un tope diario de envíos (unos 500; por verificar).

Desarrollo: el perfil `mail` del compose levanta **Mailpit**, un buzón que recibe los correos sin enviarlos:

```bash
# en .env: SMTP_HOST=mailpit  SMTP_PORT=1025  SMTP_STARTTLS=false  SMTP_USER=dev  SMTP_PASSWORD=dev  SMTP_FROM=dev@example.test
docker compose --profile mail up -d      # los correos se leen en http://localhost:8025 (MAILPIT_UI_PORT)
```

Con el correo de verificación sin SMTP configurado, el registro queda a medias: la persona no puede completar la verificación. Mientras no haya SMTP, el administrador puede marcar *Email verified* a mano en la consola.

## El usuario administrador

El realm **no lleva usuarios**. El primer administrador se crea en la consola de Keycloak (<http://localhost:8180>, realm `smartmentor`, *Users → Create user*):

1. **Username y Email**: el correo del administrador sembrado (`SEED_ADMIN_EMAIL`; el plan mantiene `admin.smartmentor@yopmail.com`, un buzón público: antes del piloto se cambia por uno propio, plan 18.7).
2. **Email verified: activado.** Es obligatorio: la API solo enlaza por correo cuando Keycloak lo marca como verificado; si no, responde 403 (`EMAIL_NOT_VERIFIED`).
3. Pestaña **Credentials**: define una contraseña (de 12 caracteres o más, según la política).
4. Pestaña **Role mapping → Assign role**: `admin`.
5. Al primer inicio de sesión, Keycloak le pide configurar el **OTP** (lo exige el rol `admin`). Sin ese paso no entra.

Cómo se enlaza con la base: en el primer acceso la API busca al usuario por el `sub` del token y, si no existe, por el correo verificado; encuentra la fila sembrada y guarda el `sub` en `users.identity_subject`. Desde entonces el vínculo es el `sub`, no el correo. Nunca se puede dejar la plataforma sin un administrador (G-06).

Cualquier otra persona se registra sola desde la pantalla de login (rol `learner`). Un instructor se registra igual y un administrador le asigna `instructor` desde la plataforma; la API refleja el rol en Keycloak y, desde ese momento, se le exige el OTP.

## Usuarios de desarrollo (instructor y aprendiz)

Liquibase siembra en la base de la aplicación un instructor y un aprendiz de desarrollo (`SEED_INSTRUCTOR_EMAIL` y `SEED_LEARNER_EMAIL`, changelog `v2.0.1`; ver `database/README.md`). Para poder iniciar sesión también deben existir en Keycloak con el mismo correo, verificado:

```bash
keycloak/scripts/seed-dev-users.sh                # instructor y aprendiz
keycloak/scripts/seed-dev-users.sh --with-admin   # además el administrador (SEED_ADMIN_EMAIL)
```

El script es idempotente (no toca los usuarios que ya existen), asigna el rol de realm correspondiente y usa la contraseña `SEED_USERS_PASSWORD` del `.env` (la genera `scripts/gen-secrets.sh`; debe cumplir la política del realm). El instructor y el administrador configuran su OTP en el primer ingreso. **Solo desarrollo:** en producción deja esas variables vacías y no ejecutes el script.

## Rotar secretos

Un secreto que se publicó, se filtró o simplemente cumplió su ciclo se rota así:

```bash
scripts/gen-secrets.sh                 # solo rellena lo vacío; para rotar uno, vacía antes su línea en .env
# o edita .env a mano con el valor nuevo
docker compose up -d keycloak app api  # los contenedores reciben las variables nuevas
keycloak/scripts/apply-secrets.sh      # aplica OIDC_UI_CLIENT_SECRET, AI_CLIENT_SECRET y SMTP_* al realm existente
```

`apply-secrets.sh` usa `kcadm.sh` dentro del contenedor (que ya tiene esas variables) y **no imprime ningún valor**. Usa las credenciales de arranque del administrador; si cambiaste su contraseña en la consola, exporta `KCADM_USER` y `KCADM_PASSWORD` antes. Después hay que reiniciar los servicios que usan el secreto (`app` y `api`) para que lo relean.

Otras rotaciones:

| Qué | Cómo |
| --- | --- |
| Llaves de firma de los tokens | Consola, *Realm settings → Keys → Providers*: crear un `rsa-generated` y un `rsa-enc-generated` nuevos con mayor prioridad y, pasado el tiempo de vida de los tokens, borrar los anteriores. Los tokens firmados con la llave vieja dejan de valer al borrarla |
| Contraseña del administrador de la consola | Consola, realm `master`, *Users → admin → Credentials* (`KEYCLOAK_ADMIN_PASSWORD` solo sirve en el primer arranque) |
| Contraseña del rol `keycloak` de PostgreSQL | `ALTER ROLE` en PostgreSQL y el mismo valor en `KEYCLOAK_DB_PASSWORD`; PostgreSQL ignora los cambios de `.env` si `database/data/postgres` ya existe |
| Todo el realm desde cero | Sección «Compartir un cambio»: `DROP SCHEMA`, y Keycloak lo importa de nuevo con los valores actuales de `.env` (borra usuarios y sesiones) |

## Cómo se comparte y se traslada (varios PC)

No se copian archivos de datos en bruto. Hay dos mecanismos:

| Qué | Cómo viaja | ¿En git? |
| --- | --- | --- |
| **Configuración** (realm, roles, clientes, flujos, mappers), sin usuarios ni secretos | `keycloak/realm/smartmentor-realm.json`. Keycloak lo importa **solo si el realm no existe** | **Sí** |
| **Datos acumulados** (usuarios nuevos, sesiones, cambios hechos después) | Respaldo lógico con `database/scripts/backup.sh` y restauración con `restore.sh` | No |

### PC nuevo

```bash
git clone <repositorio> && cd smartmentor
cp .env.example .env && scripts/gen-secrets.sh   # y completa a mano los usuarios, el correo y los modelos
docker compose up -d --build
```

Sin más pasos (con el volumen `database/data/postgres` vacío; si ya existe, ejecuta antes `database/scripts/bootstrap.sh` para crear los roles de la base): se crean las bases (incluida `keycloak`), Liquibase aplica el esquema y Keycloak importa el realm con sus roles, clientes y flujos. Keycloak genera unas llaves de firma nuevas en cada PC (un token de un PC no lo valida la API de otro) y el usuario administrador se crea en la consola.

### Compartir un cambio de configuración

Un solo responsable exporta (el JSON se corrompe con exportaciones simultáneas). Cuando cambies algo en la consola (un cliente, un mapper, un rol), expórtalo y haz commit del archivo. El script guarda el export crudo en una carpeta temporal fuera del repositorio, lo pasa por `sanitize-realm.py` (que quita usuarios, secretos y llaves y pone los marcadores `${VARIABLE}`) y comprueba el resultado:

```bash
keycloak/scripts/export-realm.sh      # detiene Keycloak un momento y reescribe keycloak/realm/smartmentor-realm.json
keycloak/scripts/check-realm-import.sh --functional   # opcional: lo importa en un Keycloak desechable y lo verifica
git add keycloak/realm && git commit -m "feat(keycloak): ..."
```

Quien reciba el commit y **ya tenga el realm** (importación omitida) debe aplicar el cambio con la restauración de datos o recreando el realm:

```bash
docker compose stop keycloak
docker compose exec -T postgres psql -U "$POSTGRES_USER" -d keycloak -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public AUTHORIZATION $KEYCLOAK_DB_USER;"
docker compose up -d keycloak          # Keycloak recrea sus tablas e importa el realm del archivo
```

(Esto borra los datos locales de Keycloak y los reemplaza por los del archivo; hay que volver a crear el administrador.)

### Llevar los datos acumulados de un PC a otro

```bash
./database/scripts/backup.sh                 # en el PC de origen: genera keycloak_*.dump y smartmentor_*.dump
# copia los .dump al PC destino (database/backups/)
docker compose stop keycloak api
./database/scripts/restore.sh database/backups/keycloak_YYYYMMDD_HHMMSS.dump
./database/scripts/restore.sh database/backups/smartmentor_YYYYMMDD_HHMMSS.dump
docker compose up -d
```

## Verificación automática

`keycloak/scripts/check-realm-import.sh [--functional]` levanta un Keycloak 26.8.0 **desechable** (H2, un puerto libre, valores de prueba, sin tocar el del proyecto), importa el realm y comprueba con la API de administración: autorregistro y correo verificado, fuerza bruta, política de contraseñas, roles, clientes y audiencias, que los secretos y el correo se sustituyeron, las llaves nuevas y el flujo de OTP. Con `--functional` además prueba el login de cuatro usuarios (aprendiz, instructor, administrador y ambos) y la pantalla de registro. La CI lo ejecuta en cada pull request (trabajo `keycloak-realm`) y `sanitize-realm.py --check` falla si el archivo trae un secreto literal.

## Datos sensibles en git

**Desde el 2026-11-07 el archivo versionado no lleva secretos.** El repositorio es público, así que `realm/smartmentor-realm.json` no incluye los usuarios con sus hashes de contraseña, los *client secrets* ni las llaves privadas de firma.

- **El historial de git sigue teniendo los valores antiguos** (estaban en ramas publicadas). Se tratan como comprometidos y se invalidan **rotándolos**; no se reescribe el historial.
- **Rotar en un Keycloak que ya importó el realm viejo** (el que tenía `student` y `teacher`): lo más simple es recrear el realm (`DROP SCHEMA`, sección «Compartir un cambio») para recibir roles, clientes, llaves y secretos nuevos, y volver a crear el administrador.
- Los respaldos `keycloak_*.dump` también contienen hashes y llaves; `database/backups/` está ignorado por git.
- Los secretos de despliegue (cliente de la interfaz, cuenta de servicio, SMTP) van en `.env`, nunca en este archivo; ver el plan de implementación, G-08.

## Configuración que necesita el realm

### Mapper de audiencia (obligatorio)

> **Ya está configurado** en el realm versionado para `smartmentor-ui`, `smartmentor-dev-tools` y `smartmentor-frontend` (audiencia `smartmentor-api`) y para `smartmentor-api-service` (audiencia `smartmentor-ai`). Estos pasos son para crearlo en otro cliente o en un Keycloak nuevo.

Por defecto el access token de Keycloak trae `aud: account`, y la API lo rechaza (401, y en sus logs `InvalidAudienceError`). Cada cliente con el que se inicie sesión necesita agregar `smartmentor-api` a la audiencia:

1. **Clients → el cliente → Client scopes → `<cliente>-dedicated` → Configure a new mapper → Audience**.
2. Name: `audience-smartmentor-api`.
3. **Included Client Audience**: `smartmentor-api`.
4. **Add to access token**: activado. **Add to ID token**: desactivado.
5. Save, y después `keycloak/scripts/export-realm.sh` para que viaje con el repositorio.

Para comprobarlo, decodifica un access token (por ejemplo en <https://jwt.io>) y verifica que `aud` incluya `smartmentor-api` y que `iss` sea `http://localhost:8180/realms/smartmentor`.

### Primer ingreso y usuarios nuevos

Cualquier persona con correo verificado que inicie sesión y no exista en la base se crea automáticamente como **aprendiz** (`learner`; caso de uso CU-34). El autorregistro está habilitado, así que cualquiera puede llegar hasta ahí: por eso el correo verificado es obligatorio.

## Probar la API con un token

Cómo obtener un token y llamar a la API (Swagger, terminal y Postman) está en [`api/README.md`](../api/README.md#obtener-un-token-y-probar-la-api). De Keycloak solo necesitas tener un usuario con contraseña en el realm `smartmentor`: regístrate desde la pantalla de login o crea uno en **Users → Create new user** (correo y *Email verified* activado) → pestaña **Credentials → Set password**.

## Cómo comprobar que todo está bien

Con un access token de tu usuario (obtenido por el frontend o por una herramienta de pruebas OAuth):

```bash
curl -H "Authorization: Bearer $TOKEN" http://localhost:8020/api/v1/me
# → {"id":..., "email":"...", "roles":["learner"], "identity_provider":"keycloak", ...}
```

| Respuesta | Causa probable |
| --- | --- |
| 401 `MISSING_TOKEN` | No se envió la cabecera `Authorization: Bearer ...` |
| 401 `INVALID_TOKEN` | Token vencido, firma de otro realm, `iss` distinto de `OIDC_ISSUER_URL` o falta el mapper de audiencia. El motivo exacto está en `docker logs smartmentor-api` (busca `token rejected`) |
| 403 `EMAIL_NOT_VERIFIED` | El usuario de Keycloak no tiene *Email verified* |
| 403 `IDENTITY_CONFLICT` | Ese correo ya pertenece a otra identidad de Keycloak |
| 403 `INSUFFICIENT_ROLE` | El rol del usuario en `user_roles` no permite la operación |
| 503 `IDENTITY_PROVIDER_UNAVAILABLE` | La API no alcanza Keycloak para descargar las llaves (`OIDC_JWKS_URL`) |

## Integración con el frontend y la API (resumen)

```text
Streamlit ──(1) inicio de sesión OIDC (smartmentor-ui)──► Keycloak
    │                                                        │
    │◄────────────(2) access token (JWT)─────────────────────┘
    │
    └──(3) Authorization: Bearer <token>──► API FastAPI ──(4) valida firma (JWKS), iss, aud, exp
                                               │
                                               └──(5) client credentials (smartmentor-api-service)──► ai/ (aud smartmentor-ai)
```

Con Streamlit se usa `st.login()` con `expose_tokens` para obtener el access token en el servidor. El detalle está en [D-03](../proyecto/decisiones-pendientes.md) y el [ADR 0004](../docs/adr/0004-authentication-keycloak-bearer.md).

## Variables

| Variable | Valor local | Para qué |
| --- | --- | --- |
| `KEYCLOAK_PORT` | `8180` | Puerto de la consola en tu máquina |
| `KC_HOSTNAME` | vacío (`http://localhost:KEYCLOAK_PORT`) | URL pública de Keycloak; en producción, la URL HTTPS |
| `KEYCLOAK_ADMIN`, `KEYCLOAK_ADMIN_PASSWORD` | (definidas en `.env`) | Administrador de la consola |
| `KEYCLOAK_DB_NAME`, `KEYCLOAK_DB_USER`, `KEYCLOAK_DB_PASSWORD` | `keycloak`, (definidas en `.env`) | Base y rol de Keycloak en PostgreSQL |
| `OIDC_UI_CLIENT_SECRET`, `AI_CLIENT_SECRET` | (generadas por `gen-secrets.sh`) | Secretos de `smartmentor-ui` y `smartmentor-api-service` (los sustituye el realm al importar) |
| `SMTP_*` | Gmail o Mailpit | Correo de verificación y recuperación (sustituidas al importar) |
| `OIDC_ISSUER_URL` | `http://localhost:8180/realms/smartmentor` | `iss` esperado por la API: la URL con la que los clientes piden el token |
| `OIDC_AUDIENCE` | `smartmentor-api` | `aud` esperado por la API |
| `OIDC_DOCS_CLIENT_ID` | vacío | Cliente con el que Swagger (`/docs`) pide el token con usuario y contraseña (`smartmentor-dev-tools`). Vacío lo desactiva |
| `OIDC_JWKS_URL` | `http://keycloak:8080/realms/smartmentor/protocol/openid-connect/certs` | Llaves públicas, por la red interna de Docker |

La API no arranca si faltan o están vacías las variables `OIDC_*`.

## Producción (no incluido)

`start-dev` usa HTTP y no es para producción. Habría que: ejecutar `start` con HTTPS y un nombre de host fijo (`KC_HOSTNAME` con la URL HTTPS), un rol de base de datos con mínimos privilegios, regenerar llaves y secretos, cambiar el administrador sembrado por un correo propio, y revisar las URI de retorno de `smartmentor-ui`.

**Elimina el cliente `smartmentor-dev-tools`** antes de producción y deja `OIDC_DOCS_CLIENT_ID` vacío en la API. Entregar el usuario y la contraseña al cliente (flujo *password*) está desaconsejado por OAuth 2.1: sirve para probar, pero en producción las contraseñas solo deben escribirse en la pantalla de Keycloak.
