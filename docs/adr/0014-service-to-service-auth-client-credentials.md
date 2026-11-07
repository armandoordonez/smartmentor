# ADR 0014: Autenticación entre servicios con *client credentials* y endurecimiento de Keycloak

* **Estado:** Propuesto. Lo cierran la Fase 8 (realm y clientes) y la Fase 3 (reflejo de roles y segundo factor en la API). Las reglas de registro y roles ya las decidió el dueño (DEF-13 y DEF-27, 2026-11-07); falta aprobar el diseño de *client credentials*
* **Fecha:** 2026-11-07
* **Autor:** eduar.troyano
* **Fuente:** [plan de implementación v3](../../PLAN_IMPLEMENTACION_V3.md), secciones 5.4.12, 5.6 (Keycloak), 18.1 (G-01 a G-07), 18.6, 18.7, DEF-13, DEF-27, DEF-28 y DEF-29
* **Relacionados:** [ADR 0004](0004-authentication-keycloak-bearer.md) (complementa), [ADR 0005](0005-keycloak-postgres-realm-versioned.md), [ADR 0008](0008-ai-service-architecture.md), [ADR 0021](0021-neutral-roles-and-label-glossary.md), [`keycloak/README.md`](../../keycloak/README.md)

---

## 1. Contexto

El ADR 0004 resolvió la autenticación de personas: la API valida el bearer token de Keycloak por JWKS y autoriza con los roles de `user_roles`. La arquitectura v3 agrega dos necesidades:

1. **Un servicio llama a otro.** La API invoca a `ai/` ([ADR 0008](0008-ai-service-architecture.md)); `ai/` no debe aceptar llamadas anónimas, aunque esté en la red interna.
2. **El registro se abre.** DEF-13 decidió el autorregistro en Keycloak con el rol `learner` por defecto, varios roles por usuario y menú de perfil. Con el registro abierto aparecen riesgos verificados en el realm (plan 18.1):
   - `verifyEmail: false`: quien se registre con el correo del administrador antes que él podría quedarse con su perfil, porque el enlace se hace por correo (G-01);
   - `bruteForceProtected: false` y política de contraseñas sin endurecer (G-02);
   - los roles viven en dos lugares, la base y el realm; el OTP para instructor y admin se decide en Keycloak, que no se entera si el administrador cambia un rol en la base (G-03).

## 2. Decisión

### 2.1 Entre servicios

1. **La API pide un token con *client credentials*** al cliente confidencial `smartmentor-api-service` (cuenta de servicio con audiencia `smartmentor-ai`).
2. **`ai/` lo valida con la misma lógica de JWKS del ADR 0004** (RS256, `iss`, `aud = smartmentor-ai`, `exp`). Sin token, 401. El cliente `smartmentor-ai` solo define la audiencia.
3. **Variables en `.env`** (vacías en el ejemplo): en la API `AI_BASE_URL`, `AI_CLIENT_ID` y `AI_CLIENT_SECRET`; en `ai/` `AI_SERVICE_AUDIENCE`. El secreto nunca se versiona (ADR 0005, sección 3).
4. **`ai/` no llama a la API** (ingesta por consulta, ADR 0010), así que no necesita credenciales propias.

### 2.2 Registro, primer ingreso y roles (DEF-13, DEF-27)

5. **Autorregistro habilitado en Keycloak solo con `verifyEmail: true`** (G-01). El correo se envía por el SMTP de Google con contraseña de aplicación (DEF-29); en desarrollo, Mailpit. Las variables `SMTP_*` van en `.env`.
6. **Protección de fuerza bruta activada**, política de contraseñas endurecida y límite de peticiones en la API; CAPTCHA si hace falta (G-02).
7. **Primer ingreso (G-04, CU-34):** la API crea la fila de `users` y el rol `learner` en la primera llamada autenticada, enlazando por `sub` y por correo **verificado**, de forma idempotente y segura ante dos llamadas simultáneas. Se mantienen los rechazos del ADR 0004 (`EMAIL_NOT_VERIFIED`, `IDENTITY_CONFLICT`, `ACCOUNT_DEACTIVATED`).
8. **La base manda en los roles (DEF-27):** la autorización sigue leyendo `user_roles`. Cuando el administrador asigna o quita un rol, la API lo **refleja en Keycloak** con su API de administración, para que la política de OTP se aplique.
9. **Segundo factor:** OTP obligatorio en Keycloak para quien tenga `instructor` o `admin` (A4) y, además, **las rutas de instructor y admin exigen que el token indique un segundo factor**. Así, un rol recién asignado que aún no se refleja no abre esas rutas sin OTP.
10. **Varios roles por usuario (G-05, G-06):** el «rol activo» del menú de perfil es solo de presentación; la API autoriza por la unión de roles. El administrador nunca puede dejar la plataforma sin administrador.
11. **Administrador sembrado (DEF-28):** se mantiene el correo actual con `emailVerified` y OTP; el realm no lleva usuarios. Antes del piloto se cambia por un correo propio (riesgo de buzón público, plan 18.7).

### 2.3 Clientes del realm

12. `smartmentor-ui` (confidencial, `http://localhost:8501/oauth2callback`, mapper de audiencia `smartmentor-api`), `smartmentor-ai` y `smartmentor-api-service`. Se borra la URI `http://localhost:8081/*`. `KC_HOSTNAME=http://localhost:8180` y `KC_HOSTNAME_BACKCHANNEL_DYNAMIC=true`.

## 3. Alternativas descartadas

- **Red interna sin autenticación entre servicios:** cualquier contenedor de la red podría encolar trabajos con costo de LLM.
- **Clave compartida estática (cabecera con un secreto fijo):** sin vencimiento ni rotación; Keycloak ya ofrece tokens con vida corta.
- **Introspección del token en cada llamada:** dependencia de red extra; la validación local con JWKS basta (ADR 0004).
- **Roles del token como fuente de verdad:** descartado en el ADR 0004 y confirmado en DEF-27.
- **Registro cerrado (solo alta por el administrador):** contradice DEF-13 y la pantalla A3 de Figma v3.

## 4. Consecuencias

- **Positivas:** `ai/` solo atiende a la API; el registro abierto no permite suplantar al administrador; el OTP se exige aunque los roles cambien en la base.
- **Negativas y pendientes:**
  - La API necesita una credencial de administración de Keycloak con permisos mínimos para reflejar roles (se define en la Fase 8).
  - La API debe pedir y renovar el token de servicio antes de su vencimiento.
  - Abrir el registro depende de crear la contraseña de aplicación de Google (P-19); el tope diario de envíos de una cuenta personal alcanza para el piloto, no para un registro masivo.
  - Verificar en la Fase 8 que Keycloak 26.8 acepte variables en la sección de correo del realm importado.
