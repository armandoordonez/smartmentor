# ADR 0006: Interfaz de usuario con Streamlit

* **Estado:** Aceptado
* **Fecha:** 2026-10-07
* **Autor:** eduar.troyano
* **Fuente:** [`proyecto/brief.md`](../../proyecto/brief.md), secciones "Arquitectura técnica y stack sugerido" («Streamlit para la interfaz (se construye en días)») y "Fase 0: prototipado"
* **Relacionados:** [ADR 0004](0004-authentication-keycloak-bearer.md), [`app/README.md`](../../app/README.md), [`proyecto/checklist.md`](../../proyecto/checklist.md#comparación)

## 1. Contexto

El brief propone Streamlit (recomendado para el MVP) o Next.js («válido si el equipo domina React, pero consume tiempo que conviene dedicar a la evaluación»). Las restricciones del proyecto:

- 8 semanas, con el flujo completo funcionando en la semana 4;
- se aprueba por la calidad de la evaluación, no por la cantidad de funcionalidades;
- la capa de IA, que es el aporte académico, aún no empieza;
- la Fase 0 pide un prototipo navegable (Figma o Streamlit con datos de ejemplo);
- piloto de 15 a 30 estudiantes;
- continuidad entre cohortes de una maestría en ciencia de datos.

La API, la autenticación con Keycloak y los endpoints del estudiante ya existen y no dependen del frontend.

## 2. Decisión

**La interfaz se construye con Streamlit** en `app/`, con la arquitectura descrita en [`app/README.md`](../../app/README.md):

1. **La API es la única fuente de reglas y datos.** La interfaz no se conecta a la base ni repite reglas de negocio; llama a la API con el token del usuario.
2. **Capas:** `pages/` y `components/` (presentación), `core/` (sesión, autenticación, navegación por rol, errores), `services/` (casos de uso de la interfaz) y `clients/` (acceso a la API). Se basa en la guía de referencia [`app/streamlit_frontend_architecture_guide.md`](../../app/streamlit_frontend_architecture_guide.md), con los ajustes analizados en el README.
3. **Autenticación:** `st.login()` con OpenID Connect contra Keycloak, con un cliente **confidencial** propio (`smartmentor-ui`), porque Streamlit corre en el servidor. El access token se queda en el servidor y se envía a la API. Los roles salen de `GET /api/v1/me`.
4. **Caché:** solo para el catálogo público. Los datos personales viven en la sesión de cada usuario, porque la caché de Streamlit es compartida entre usuarios.
5. **Datos de ejemplo:** el cliente de la API tiene una implementación con datos de ejemplo (`APP_DATA_SOURCE=sample`) para el prototipo de la Fase 0, la prueba de usabilidad y las pruebas automáticas.
6. **Prueba técnica previa (1 día):** antes de construir pantallas se verifica el login con Keycloak (`expose_tokens`, vencimiento del token, cierre de sesión y URLs de Keycloak entre la red de Docker y el navegador).

## 3. Alternativa descartada: Next.js

Ventajas reales: control total del diseño, integración de autenticación más madura, mejor rendimiento con mucho tráfico y camino natural a producción. Se descarta porque cuesta semanas que el brief prefiere dedicar a la IA y la evaluación, exige un perfil de frontend que la siguiente cohorte puede no tener y sus ventajas no pesan en un piloto de 15 a 30 estudiantes. Como la API y el login no dependen del frontend, migrar después no obliga a cambiar el backend.

## 4. Consecuencias

- **Positivas:** pantallas en días; un solo lenguaje en todo el proyecto; el prototipo de la Fase 0 se convierte en el MVP; cualquier integrante puede mantenerlo.
- **Negativas y riesgos:**
  - Control limitado del diseño y de la interactividad compleja.
  - La sesión de Streamlit (cookie de 30 días) no sigue el vencimiento del token: la interfaz debe detectarlo y pedir volver a entrar.
  - `st.logout()` no cierra la sesión de Keycloak: hay que redirigir al `end_session_endpoint`.
  - Keycloak debe publicar la misma URL al navegador y a los contenedores (`KC_HOSTNAME` y `KC_HOSTNAME_BACKCHANNEL_DYNAMIC`), o el `iss` no coincidiría con el que valida la API.
  - Si el producto crece después del piloto, probablemente habrá que reescribir la interfaz.
