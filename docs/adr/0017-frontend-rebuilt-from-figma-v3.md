# ADR 0017: Interfaz rehecha desde Figma v3 (complementa el ADR 0006)

* **Estado:** Aceptado (decisión del dueño del 2026-11-07, incluido el directorio de estilos)
* **Fecha:** 2026-11-07
* **Autor:** eduar.troyano
* **Fuente:** [plan de implementación v3](../../PLAN_IMPLEMENTACION_V3.md), secciones 0 (punto 3 de la recomendación), 1.3, 2.2, 2.6, 5.5 y 5.5.1
* **Relacionados:** [ADR 0006](0006-frontend-streamlit.md) (complementa), [ADR 0014](0014-service-to-service-auth-client-credentials.md), [ADR 0021](0021-neutral-roles-and-label-glossary.md), [`app/README.md`](../../app/README.md), [`app/CLAUDE.md`](../../app/CLAUDE.md), [especificación de Figma v3](../../design/03-prototipo-alta-fidelidad/v3/README.md)

---

## 1. Contexto

El ADR 0006 eligió Streamlit y una arquitectura por capas. El prototipo de la Fase 0 (`app/src`, 20 páginas) se construyó sobre la v2 de Figma, sin login ni API, con un cliente de ejemplo que repite reglas de negocio (umbrales, intentos), en contra del propio ADR 0006.

El prototipo v3 (fileKey `atp2fZdSolEoaww3n9jRLg`, 97 frames) agrega estados de carga y error de la IA, consentimiento y derechos, hoja de vida, intentos extra, anotación ciega, calificación humana, curaduría de videos, piloto, encuesta SUS y una paleta nueva. Son unas 60 pantallas únicas frente a 20 páginas.

El dueño pidió además **un solo lugar para todos los estilos**, para ajustar colores sin buscarlos por las páginas. `app/CLAUDE.md` decía «sin CSS; si un pull request lo justifica, va en un solo archivo».

## 2. Decisión

1. **Se rehace `app/src` desde Figma v3**, conservando solo el andamiaje técnico: Dockerfile, `pyproject.toml`, `uv.lock`, `scripts/dev.sh` y la fuente Inter. El tema se reescribe con las 24 variables de v3. Páginas, servicios, cliente de ejemplo y pruebas de interfaz se reemplazan.
2. **Se mantiene todo lo decidido en el ADR 0006:** Streamlit; la API como única fuente de reglas y datos; capas `pages`, `components`, `core`, `services` y `clients`.
3. **Autenticación real:** `core/auth.py` con `st.login("keycloak")` y el cliente `smartmentor-ui`; revisión de `exp` antes de cada llamada; cierre de sesión con redirección al `end_session_endpoint`.
4. **Cliente:** `clients/api.py` (`httpx`, RFC 9457 → `ApiError`, `Idempotency-Key` en las entregas, sondeo de trabajos con espera progresiva) y `clients/fixtures.py` con JSON fijos generados por el arnés de `ai/` y validados contra los esquemas de la API, **sin reglas de negocio**. Los modelos se generan desde el OpenAPI.
5. **Estados:** cada página resuelve el `next_action` que devuelve la API; nunca deduce estados por su cuenta. Los botones «(Demo del prototipo)» de Figma no se construyen.
6. **Directorio de estilos `app/src/static/styles/`** (5.5.1): `tokens.css` es el **único** archivo con hexadecimales (las 24 variables de Figma, radios, espaciados y tipografía); `base.css`, `layout.css`, `roles.css` (acento por rol) y `components/` (un archivo por componente), con su `README.md`.
   - Cargador único `app/src/core/styles.py`, en orden fijo, una vez por página desde `render_header`; en caché salvo con `APP_ENV=local`.
   - Fuera de `tokens.css` no hay hexadecimales ni `rgb()`; solo variables CSS.
   - Selectores estables: clases propias y `.st-key-<nombre>`, nunca clases internas de Streamlit. La versión de Streamlit queda fija.
   - Una prueba verifica que `.streamlit/config.toml` coincide con `tokens.css` y calcula el contraste (4,5:1 para texto y 3:1 para bordes de campos).
   - El texto del usuario o de la IA **nunca** se inyecta con `unsafe_allow_html`.
   - P2: `APP_CONTEXT_PROFILE` puede cargar `themes/<perfil>.css`, que solo redefine variables.
7. **Páginas por rol** (`pages/learner`, `pages/instructor`, `pages/admin`) con etiquetas del glosario ([ADR 0021](0021-neutral-roles-and-label-glossary.md)). Orden: aprendiz (P0), instructor (P0), admin (P1), piloto.
8. **`app/CLAUDE.md` se reescribe** con la fuente v3, los tokens nuevos, los componentes y la regla de estilos de este ADR.

## 3. Alternativas descartadas

- **Evolucionar las páginas del prototipo v2:** el cliente de ejemplo y los servicios repiten reglas de negocio y las pantallas no coinciden con v3; adaptarlas cuesta más que rehacerlas.
- **Mantener «sin CSS» o un solo archivo:** no permite dar a cada rol su color de botón ni ajustar la paleta en un solo lugar.
- **Migrar a Next.js:** ya descartado en el ADR 0006; el cambio de diseño no altera ese análisis.

## 4. Consecuencias

- **Positivas:** la interfaz refleja el diseño aprobado; los colores se cambian en un archivo; los datos de prueba salen de una sola fuente (corrige C-14 y C-15); la interfaz puede avanzar con `fixtures` mientras la API y `ai/` se construyen.
- **Negativas y pendientes:**
  - Es la fase más larga del plan (10 a 12 jornadas); se recorta lo P2 si el tiempo aprieta.
  - Los selectores `.st-key-*` pueden cambiar entre versiones de Streamlit: el color de botón por rol es P1.
  - `aviso/acento` no alcanza el contraste para texto y solo puede ser decorativo; los bordes de campos deben medirse (plan 18.2).
  - Las variables `error/acento` (inferida) y posibles cambios del Figma en vivo quedan por confirmar (P-13, P-14).
