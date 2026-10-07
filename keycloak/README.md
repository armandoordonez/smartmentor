# keycloak/

Proveedor de identidad de SmartMentor: **Keycloak 26.8.0** (OpenID Connect) en un contenedor. La aplicación **no guarda contraseñas**: delega el inicio de sesión en Keycloak, y la API valida los tokens que emite ([ADR 0004](../docs/adr/0004-authentication-keycloak-bearer.md)). Cómo se guardan y se trasladan sus datos: [ADR 0005](../docs/adr/0005-keycloak-postgres-realm-versioned.md).

## Estructura

```text
keycloak/
├── README.md              # este documento
├── realm/
│   └── smartmentor-realm.json   # el realm completo: roles, clientes, mappers y usuarios de prueba (en git)
└── scripts/
    └── export-realm.sh    # exporta el realm de la consola al archivo anterior
```

Keycloak **no tiene volumen propio**: guarda todo en la base `keycloak` del PostgreSQL del proyecto (`database/data/`), con su propio rol (`KEYCLOAK_DB_USER`), separada de la base `smartmentor`.

## Arranque

```bash
docker compose up -d        # postgres → (liquibase) → keycloak, que importa el realm si no existe
```

| Dato | Valor |
| --- | --- |
| Consola de administración | <http://localhost:8180> (puerto `KEYCLOAK_PORT` de `.env`) |
| Administrador de la consola (realm `master`) | `KEYCLOAK_ADMIN` y `KEYCLOAK_ADMIN_PASSWORD` de `.env` |
| Realm de la aplicación | `smartmentor`, <http://localhost:8180/realms/smartmentor> |
| Modo | `start-dev` (HTTP). Para producción se usa `start` con HTTPS |
| Base de datos | `keycloak` en el PostgreSQL del proyecto (`jdbc:postgresql://postgres:5432/keycloak`) |

El administrador de la consola se crea solo en el primer arranque con base vacía. Si cambias `KEYCLOAK_ADMIN_PASSWORD` en `.env` después, no tiene efecto: cámbiala desde la consola.

## Cómo se comparte y se traslada (varios PC)

No se copian archivos de datos en bruto. Hay dos mecanismos:

| Qué | Cómo viaja | ¿En git? |
| --- | --- | --- |
| **Configuración y usuarios de prueba** (realm, roles, clientes, mappers) | `keycloak/realm/smartmentor-realm.json`. Keycloak lo importa **solo si el realm no existe** | **Sí** |
| **Datos acumulados** (usuarios nuevos, sesiones, cambios hechos después) | Respaldo lógico con `database/scripts/backup.sh` y restauración con `restore.sh` | No |

### PC nuevo

```bash
git clone <repositorio> && cd smartmentor
cp .env.example .env       # reemplaza los change_me por contraseñas propias
docker compose up -d --build
```

Sin más pasos: se crean las bases (incluida `keycloak`), Liquibase aplica el esquema y Keycloak importa el realm con sus roles, clientes y usuarios. El PC nuevo comparte las mismas llaves de firma, así que un token emitido en un PC lo valida la API de otro.

### Compartir un cambio de configuración

Cuando cambies algo en la consola (un cliente, un mapper, un rol, un usuario de prueba), expórtalo y haz commit del archivo:

```bash
keycloak/scripts/export-realm.sh      # detiene Keycloak un momento y reescribe keycloak/realm/smartmentor-realm.json
git add keycloak/realm && git commit -m "feat(keycloak): ..."
```

Quien reciba el commit y **ya tenga el realm** (importación omitida) debe aplicar el cambio con la restauración de datos o recreando el realm:

```bash
docker compose stop keycloak
docker compose exec -T postgres psql -U smartmentor -d keycloak -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public AUTHORIZATION keycloak;"
docker compose up -d keycloak          # Keycloak recrea sus tablas e importa el realm del archivo
```

(Esto borra los datos locales de Keycloak y los reemplaza por los del archivo.)

### Llevar los datos acumulados de un PC a otro

```bash
./database/scripts/backup.sh                 # en el PC de origen: genera keycloak_*.dump y smartmentor_*.dump
# copia los .dump al PC destino (database/backups/)
docker compose stop keycloak api
./database/scripts/restore.sh database/backups/keycloak_YYYYMMDD_HHMMSS.dump
./database/scripts/restore.sh database/backups/smartmentor_YYYYMMDD_HHMMSS.dump
docker compose up -d
```

## Datos sensibles en git

El archivo `realm/smartmentor-realm.json` incluye, **por decisión del proyecto** (son datos de prueba): los *client secrets*, las **llaves privadas** con que Keycloak firma los tokens y los hashes de contraseñas de los usuarios. Quien tenga el archivo puede firmar tokens válidos para la API.

- Mientras el repositorio sea privado y los datos de prueba, es aceptable.
- **Antes de usar datos reales o hacer público el repositorio:** regenera las llaves y los secretos en la consola, deja de versionar los usuarios y el archivo (`.gitignore`), y elimina el archivo del historial de git. Está anotado en `HANDOFF.md`.
- Los respaldos `keycloak_*.dump` también contienen hashes y llaves; `database/backups/` está ignorado por git.

## Configuración que necesita el realm

Cosas que la API espera. Lo que falte se corrige desde la consola y se exporta con `export-realm.sh`.

### 1. Realm y roles

- Realm: `smartmentor`.
- Roles del realm: `admin`, `teacher` y `student` (los mismos códigos de `roles.code`).

Los roles de Keycloak son informativos para otros sistemas: **la API autoriza con `user_roles` de su base de datos**, así un administrador crea docentes y administradores desde la propia API sin tocar Keycloak.

### 2. Clientes

| Cliente | Tipo | Para qué |
| --- | --- | --- |
| `smartmentor-frontend` | Público, *Standard flow* con PKCE | La interfaz (Streamlit o Next.js) inicia sesión de los usuarios |
| `smartmentor-api` | Define la audiencia (`aud`) de los tokens | La API comprueba que el token sea para ella. **No necesita `client secret`**: solo valida tokens y no hace introspección |

**URIs del frontend** (*Valid redirect URIs* y *Web origins*): deben ser URLs completas, con `//`. Ejemplos válidos:

| Frontend | Redirect URI | Web origin |
| --- | --- | --- |
| Streamlit | `http://localhost:8501/*` | `http://localhost:8501` |
| Next.js | `http://localhost:3000/*` | `http://localhost:3000` |
| Otro puerto (p. ej. 8081) | `http://localhost:8081/*` | `http://localhost:8081` |

### 3. Mapper de audiencia (obligatorio)

Por defecto el access token de Keycloak trae `aud: account`, y la API lo rechaza (401, y en sus logs `InvalidAudienceError`). Cada cliente con el que se inicie sesión necesita agregar `smartmentor-api` a la audiencia:

1. **Clients → `smartmentor-frontend` → Client scopes → `smartmentor-frontend-dedicated` → Configure a new mapper → Audience**.
2. Name: `audience-smartmentor-api`.
3. **Included Client Audience**: `smartmentor-api`.
4. **Add to access token**: activado. **Add to ID token**: desactivado.
5. Save, y después `keycloak/scripts/export-realm.sh` para que viaje con el repositorio.

Para comprobarlo, decodifica un access token (por ejemplo en <https://jwt.io>) y verifica que `aud` incluya `smartmentor-api` y que `iss` sea `http://localhost:8180/realms/smartmentor`.

### 4. El usuario administrador

La base de datos ya tiene el usuario de aplicación (lo creó el changeset `v1.0.1-001-seed-admin-user`):

| Campo | Valor |
| --- | --- |
| Nombre | Administrador |
| Correo | `admin.smartmentor@yopmail.com` |
| Rol en la aplicación | `admin` (en `user_roles`) |

En **Users** → ese usuario de Keycloak:

1. **Email**: exactamente `admin.smartmentor@yopmail.com`.
2. **Email verified: activado.** Es obligatorio: la API solo enlaza por correo cuando Keycloak lo marca como verificado. Si no, responde 403 (`EMAIL_NOT_VERIFIED`).
3. **Credentials: define una contraseña** (sin *Temporary* si no quieres que la cambie al entrar). Sin credenciales no se puede iniciar sesión.

Cómo se enlaza: en el primer acceso, la API busca al usuario por el `sub` del token; como no existe, lo busca por el correo verificado, encuentra al Administrador y guarda el `sub` en `users.identity_subject` (con `identity_provider = keycloak`). Desde entonces el vínculo es el `sub`, no el correo. El rol `admin` ya lo tiene en `user_roles`, así que no se le agrega `student`.

### 5. Usuarios nuevos

Cualquier persona con correo verificado que inicie sesión y no exista en la base se crea automáticamente como **estudiante**. Los docentes y administradores los crea un administrador desde la API (`POST /api/v1/users` y `POST /api/v1/user-roles`), con el mismo correo con el que se registrarán en Keycloak: al verificarlo, la API los enlaza y conservan su rol.

El registro abierto en Keycloak implica que cualquiera con correo verificado se vuelve estudiante. Si el piloto debe ser cerrado, desactiva el autorregistro del realm (*Realm settings → Login → User registration*).

## Cómo comprobar que todo está bien

Con un access token de tu usuario (obtenido por el frontend o por una herramienta de pruebas OAuth):

```bash
curl -H "Authorization: Bearer $TOKEN" http://localhost:8020/api/v1/me
# → {"id":..., "email":"admin.smartmentor@yopmail.com", "roles":["admin"], "identity_provider":"keycloak", ...}
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
Streamlit / Next.js ──(1) inicio de sesión OIDC──► Keycloak
        │                                              │
        │◄────────(2) access token (JWT)───────────────┘
        │
        └──(3) Authorization: Bearer <token>──► API FastAPI
                                                  │
                                 (4) valida firma (JWKS), iss, aud, exp
```

Con Streamlit se usa `st.login()` con `expose_tokens` para obtener el access token en el servidor; con Next.js, Auth.js. Ambas opciones funcionan con la misma validación en la API. El detalle está en [D-03](../proyecto/decisiones-pendientes.md) y el [ADR 0004](../docs/adr/0004-authentication-keycloak-bearer.md).

## Variables

| Variable | Valor local | Para qué |
| --- | --- | --- |
| `KEYCLOAK_PORT` | `8180` | Puerto de la consola en tu máquina |
| `KEYCLOAK_ADMIN`, `KEYCLOAK_ADMIN_PASSWORD` | `admin`, (definida en `.env`) | Administrador de la consola |
| `KEYCLOAK_DB_NAME`, `KEYCLOAK_DB_USER`, `KEYCLOAK_DB_PASSWORD` | `keycloak`, `keycloak`, (definida en `.env`) | Base y rol de Keycloak en PostgreSQL |
| `OIDC_ISSUER_URL` | `http://localhost:8180/realms/smartmentor` | `iss` esperado por la API: la URL con la que los clientes piden el token |
| `OIDC_AUDIENCE` | `smartmentor-api` | `aud` esperado por la API |
| `OIDC_JWKS_URL` | `http://keycloak:8080/realms/smartmentor/protocol/openid-connect/certs` | Llaves públicas, por la red interna de Docker |

La API no arranca si faltan o están vacías las variables `OIDC_*`.

## Producción (no incluido)

`start-dev` usa HTTP y no es para producción. Habría que: ejecutar `start` con HTTPS y un nombre de host fijo (`KC_HOSTNAME`), un rol de base de datos con mínimos privilegios, regenerar llaves y secretos, y dejar de versionar el realm con usuarios.
