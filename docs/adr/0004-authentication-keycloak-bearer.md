# ADR 0004: Autenticación con Keycloak y bearer tokens

* **Estado:** Aceptado
* **Fecha:** 2026-10-07
* **Autor:** eduar.troyano
* **Fuente:** [`proyecto/brief.md`](../../proyecto/brief.md), módulo 1 "Gestión de usuarios" (registro, login, roles admin, docente y estudiante)
* **Relacionados:** [D-03](../../proyecto/decisiones-pendientes.md), [estándar de microservicios, sección 35](../../api/microservice-development-standard.md), [`keycloak/README.md`](../../keycloak/README.md)

## 1. Contexto

La primera entrega de la API no tenía autenticación. El brief pide registro, inicio de sesión y roles. El proyecto ya cuenta con Keycloak desplegado, con un realm `smartmentor`, los roles `admin`, `teacher` y `student`, y dos clientes (`smartmentor-frontend` y `smartmentor-api`).

La interfaz (Streamlit o Next.js) aún no está decidida, así que la API debe poder protegerse sin depender de ella.

## 2. Decisión

1. **La aplicación no guarda contraseñas.** El inicio de sesión lo hace Keycloak (OpenID Connect). La tabla `users` no tiene `password_hash`.
2. **La API es un servidor de recursos.** Recibe `Authorization: Bearer <access_token>` y valida el JWT:
   - firma con las llaves públicas del realm (JWKS) y **solo RS256** (se rechazan `none` y HS256);
   - emisor (`iss`), audiencia (`aud`) y expiración (`exp`), con 10 segundos de tolerancia de reloj;
   - presencia de `exp`, `iss`, `sub` y `aud`.
3. **La autorización usa los roles de la base de datos** (`user_roles`), **no los del token**. Así un administrador de la aplicación crea docentes y administradores desde la propia API, sin necesitar la API de administración de Keycloak, y un rol manipulado o desactualizado en el token no concede permisos.
4. **Enlace entre Keycloak y la aplicación** (en cada petición, `AuthenticationService`):
   1. Si hay un usuario con `identity_provider = keycloak` e `identity_subject = sub`, es ese.
   2. Si no, y el token trae un `email` **verificado**, se busca el usuario por correo (sin distinguir mayúsculas). Si existe y no está enlazado a otra identidad, se enlaza guardando el `sub`. Así se enlaza el administrador sembrado y los docentes que un administrador creó antes.
   3. Si tampoco existe, **se crea automáticamente con el rol `student`**.
   - Un correo sin verificar o ausente se rechaza con 403 (`EMAIL_NOT_VERIFIED`): sin esa regla, quien registre en Keycloak el correo de otra persona podría quedarse con su cuenta.
   - Un correo que ya pertenece a otra identidad se rechaza con 403 (`IDENTITY_CONFLICT`), y una cuenta inactiva con 403 (`ACCOUNT_DEACTIVATED`).
   - Desde el primer enlace, el vínculo es el `sub` y no el correo.
5. **Matriz de roles** (lectura / escritura), definida en `app/auth/policies.py`:

   | Recurso | Lectura | Escritura |
   | --- | --- | --- |
   | `roles` | admin, teacher, student | admin |
   | `users` | admin, teacher | admin |
   | `user-roles`, `llm-call-logs` | admin | admin |
   | `courses`, `topics`, `topic-prerequisites`, `learning-paths`, `resources` | admin, teacher, student | admin, teacher |
   | `enrollments`, `path-steps`, `diagnostics`, `assessment-attempts`, `badges` | admin, teacher | admin, teacher |
   | `/me` | cualquier usuario autenticado | — |

   Los estudiantes consultan el catálogo y su propio perfil. Lo que un estudiante hace sobre sus datos (inscribirse, responder un quiz) pasará por endpoints propios con verificación de pertenencia en la fase de la interfaz; por eso el CRUD genérico no se abre a su rol.
6. **Auditoría:** `app_user_id` es el id del usuario autenticado. Se elimina la cabecera temporal `X-User-Id`. Mientras se resuelve o se crea un usuario, la auditoría registra `identity:<sub>`.
7. **Configuración obligatoria:** `OIDC_ISSUER_URL`, `OIDC_JWKS_URL` y `OIDC_AUDIENCE`. La API no arranca si faltan o están vacías. `OIDC_ISSUER_URL` es el emisor tal como lo ve el cliente (`http://localhost:8180/realms/smartmentor`); `OIDC_JWKS_URL` puede ser una URL interna de la red de Docker (`http://keycloak:8080/...`).
8. **Rutas públicas:** `/health`, `/ready` y la documentación OpenAPI (`/docs`, `/openapi.json`).
9. **Cómo se obtiene un token en desarrollo.** OpenAPI declara dos esquemas equivalentes y Swagger UI los ofrece en *Authorize*:
   - *Token (pegar)*: un access token ya emitido.
   - *Login (usuario y contraseña)*: Swagger lo pide a Keycloak con el cliente `smartmentor-dev-tools` (`OIDC_DOCS_CLIENT_ID`). Se definen los scopes `openid profile email` y se preseleccionan, porque Keycloak rechaza un `scope` vacío (`invalid_scope`).

   `smartmentor-dev-tools` es un cliente público con *Direct access grants* (flujo *password*), `Web origin` `http://localhost:8020` y token de 30 minutos. También lo usan `api/scripts/token.sh` y la colección de Postman de `api/postman/`, que piden un token antes de cada llamada. **Es solo para desarrollo:** el flujo *password* está desaconsejado por OAuth 2.1. En producción se elimina el cliente y `OIDC_DOCS_CLIENT_ID` queda vacío, de modo que `/docs` ofrece solo *Token (pegar)*. El frontend usa `smartmentor-frontend` con el código de autorización y PKCE.

## 3. Requisito en Keycloak: audiencia del token

Por defecto, el access token de Keycloak trae `aud: account`. Para que la API lo acepte, cada cliente que inicia sesión (por ejemplo `smartmentor-frontend`) necesita un *mapper* de audiencia hacia `smartmentor-api`. Los pasos están en [`keycloak/README.md`](../../keycloak/README.md). Sin él, la API responde 401 y registra `InvalidAudienceError` en sus logs.

## 4. Alternativas descartadas

- **Roles del token como fuente de autorización:** exigiría que el admin gestione roles en Keycloak y depende de que el token esté al día.
- **Validar el token llamando a Keycloak en cada petición (introspección):** añade una dependencia de red por petición. La validación local con JWKS es suficiente y no necesita el `client secret`.
- **Rechazar usuarios desconocidos:** descartado por el producto: los estudiantes se crean solos en su primer acceso.
- **Pedir siempre el token con el navegador (código + PKCE) también en Swagger y Postman:** es el flujo correcto, pero obliga a iniciar sesión cada vez; se mantiene para el frontend y como opción en Postman, y se agrega el cliente de desarrollo para el resto.

## 5. Consecuencias

- **Positivas:** la API no maneja credenciales; el cambio de proveedor de identidad solo toca la configuración; los permisos se administran dentro de la aplicación y quedan auditados.
- **Negativas y pendientes:**
  - El registro abierto en Keycloak permite que cualquiera con correo verificado se vuelva estudiante. Si el piloto debe ser cerrado, hay que restringir el registro en Keycloak o cambiar la regla 4.3 a "rechazar".
  - Los endpoints propios de estudiante con verificación de pertenencia quedan para la fase de la interfaz.
  - No hay limitación de peticiones ni revocación inmediata de tokens (un token válido sirve hasta que expira, por eso conviene mantener corta su vida en Keycloak).
  - La descarga de llaves la hace `PyJWKClient` (síncrono) en un hilo aparte con caché; si Keycloak rota llaves, se renuevan al ver un `kid` desconocido.

## 6. Referencias

- [RFC 9068: JWT Profile for OAuth 2.0 Access Tokens](https://www.rfc-editor.org/rfc/rfc9068)
- [OpenID Connect Core 1.0](https://openid.net/specs/openid-connect-core-1_0.html)
- [PyJWT](https://pyjwt.readthedocs.io/)
