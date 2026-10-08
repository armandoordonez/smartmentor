# Reglas de diseño para la interfaz (Figma → Streamlit)

Reglas para pasar los diseños de Figma al código de `app/` con el MCP de Figma. Completan la arquitectura de [`README.md`](README.md) y el [ADR 0006](../docs/adr/0006-frontend-streamlit.md); si algo choca, mandan esos dos documentos.

## Fuente del diseño

| Dato | Valor |
| --- | --- |
| Archivo | [SmartMentor · Prototipo Fase 0 v2 (Estudiante, Docente, Admin)](https://www.figma.com/design/wIzBv0tOtRaoVmldEXPyff/SmartMentor-%C2%B7-Prototipo-Fase-0-v2--Estudiante--Docente--Admin-?node-id=0-1) |
| `fileKey` | `wIzBv0tOtRaoVmldEXPyff` |
| Página | `0:1` «SmartMentor v2» (es la única) |
| Biblioteca de componentes | frame `24:2` «Componentes · Biblioteca» |
| Matriz de permisos por rol | frame `2:3` |
| Variables de Figma | **No hay**: `get_variable_defs` devuelve vacío. Los colores están puestos a mano en cada capa; los valores de la sección 2 salen de `get_design_context` |
| Límite del MCP | La cuenta conectada está en el plan **Starter**, que limita las llamadas al MCP. El 2026-10-07 se agotó el cupo: de D2–D5, AD1–AD3 y A7 solo se leyó el árbol de capas (`get_metadata`), no su contexto de diseño (ver sección 4) |

Todos los frames de pantalla miden 1280 × 800 (escritorio). No hay versiones para celular.

## Estado

El prototipo está construido: todas las pantallas del diseño, menos las de login (A2 a A5), corren con datos de ejemplo. Para ejecutarlo: `app/scripts/dev.sh run`. Para revisarlo: `app/scripts/dev.sh all` (Ruff, mypy estricto y pytest con `AppTest`).

## 1. Tecnología: no hay React, CSS ni bundler

| Pregunta | Respuesta en este proyecto |
| --- | --- |
| Framework de UI | **Streamlit 1.65** (Python 3.12), multipágina con `st.navigation(position="hidden")` y una barra superior propia |
| Librería de estilos | Ninguna. Todo el aspecto sale de `.streamlit/config.toml` y de los parámetros de cada widget |
| Build y bundler | Ninguno. Dependencias con `uv` (`pyproject.toml` y `uv.lock`); Ruff (línea de 100, comillas dobles), mypy estricto y pytest, igual que la API. Se corren en contenedores con `app/scripts/dev.sh` |
| Gráficas | Las nativas de Streamlit; la paleta está en `chartCategoricalColors` del tema |
| Storybook o catálogo de componentes | No hay. Las páginas se prueban con `streamlit.testing.v1.AppTest` en `tests/ui/` |

**Regla principal:** `get_design_context` devuelve código de referencia en React y Tailwind. **No se copia.** Sirve para leer la estructura, los textos, el espaciado y los colores, y se reescribe con widgets de Streamlit. Nunca se agrega React, Tailwind, componentes personalizados (`streamlit.components.v1`) ni CSS para imitar un detalle de Figma: se simplifica el diseño y se anota la diferencia en la sección 2.

## 2. Tokens de diseño

### Valores del diseño

| Token | Hex | Uso en Figma |
| --- | --- | --- |
| `primary` (azul) | `#0073E5` | Botón principal, antetítulos, borde del tema en curso, rol Estudiante |
| `green` | `#1A8C4D` | Estados aprobado o dominado, rol Docente |
| `violet` | `#734DD9` | Rol Admin |
| `amber` | `#CC730D` | Advertencias y avisos de permisos |
| `red` | `#CC3333` | El «403» de la pantalla A6 |
| `text` | `#1A1A1F` | Texto principal |
| `text-muted` | `#6B7080` | Texto secundario, etiquetas, badge gris |
| `border` | `#E0E3EB` | Bordes de tarjetas, campos y barra superior |
| `background` | `#F5F5F7` | Fondo de la página |
| `surface` | `#FFFFFF` | Tarjetas, campos, barra superior |
| Fondos de badges | `#E8F0FC` azul, `#E0F5E5` verde, `#FFF2DB` ámbar, `#EDEDF2` gris, `#F0E8FC` violeta | Badges, avatar y avisos |

**Tipografía:** Inter. Título de página 28 px Bold; título de tarjeta 18 px Semibold; filas y campos 14 px; cuerpo, menú y botones 13 px; metadatos 12 px; badges 11 px Semibold; antetítulo 10–11 px Semibold azul.

**Radios:** botones y badges en píldora; tarjetas 14 px; filas 12 px; campos 10 px.

### Dónde viven en el código

| Qué | Dónde |
| --- | --- |
| Colores, fuente, tamaños de títulos, radios, paleta de badges y avisos | [`.streamlit/config.toml`](.streamlit/config.toml), sección `[theme]` |
| Fuente Inter | [`src/static/fonts/`](src/static/fonts/), declarada en `[[theme.fontFaces]]` y servida con `server.enableStaticServing` |
| Texto y color de cada estado (badges) | [`src/components/theme.py`](src/components/theme.py) |
| Formato de números y fechas («92 %», «1,5», «1 h 20 min», «5 oct 2026») | [`src/components/formatting.py`](src/components/formatting.py) |

No hay tokens en JSON ni transformación automática: un valor nuevo de Figma se copia a mano a `config.toml` y, si es un estado, a `theme.py`. **Nunca se escribe un hex en una página.**

La paleta de Streamlit (`greenColor`, `greenBackgroundColor`, `greenTextColor` y las demás) está ajustada a los hex de Figma, así que `st.badge(color="green")` y `st.warning(...)` se ven como el Badge y el aviso ámbar del diseño.

### Diferencias aceptadas con Figma

| En Figma | En Streamlit | Motivo |
| --- | --- | --- |
| Fondo gris `#F5F5F7` con tarjetas blancas | Fondo blanco con tarjetas de borde `#E0E3EB`; el gris queda para los campos (`secondaryBackgroundColor`) | `st.container` no tiene color de fondo propio; con fondo gris, las tarjetas también quedarían grises |
| Tres botones primarios (azul, verde, violeta) | Uno solo, `type="primary"`, en azul | `primaryColor` es uno para toda la app; el color del rol queda en el badge |
| Botón secundario gris sin borde | Botón secundario blanco con borde | Estilo fijo de Streamlit |
| Logo: cuadrado azul provisional | Ícono `:material/school:` en azul | No hay logo todavía |
| Avatar con iniciales | `st.popover` con las iniciales: nombre, correo y «Cambiar de rol» | Da la salida que en producción hará el logout |
| Opción elegida con fondo azul claro | `st.radio` | Las opciones en tarjeta exigirían CSS |
| Insignia: círculo azul de 110 px con estrella | Ícono `:material/workspace_premium:` en azul | Sin CSS no hay círculos de color |
| Recuadro negro del video | Recuadro con borde y los datos del video (sin URL en los datos de ejemplo); con URL, `st.video` | El video real viene de la API |
| Espaciados exactos en píxeles | Orden de los elementos, `gap`, `st.space` | Streamlit no expone márgenes |
| KPI con el valor arriba y la etiqueta abajo | `st.metric`: etiqueta arriba, valor abajo | Widget fijo |

## 3. Componentes

### Biblioteca de Figma (`24:2`) → código

| Componente de Figma | Variantes | Equivalente |
| --- | --- | --- |
| `Boton` | `Primario azul`, `Primario verde`, `Primario violeta`, `Secundario` | `st.button(type="primary")` / `st.button()`. Para navegar, `st.switch_page` o `st.page_link` |
| `Badge` | `Verde`, `Azul`, `Ámbar`, `Gris`, `Violeta` | `st.badge(texto, color=...)` con `green`, `blue`, `orange`, `gray`, `violet` |
| `Nav` («Menú superior») | `Rol=Estudiante`, `Docente`, `Admin` | `render_header` en [`components/layout.py`](src/components/layout.py); los enlaces de cada rol están en `LINKS` de [`core/navigation.py`](src/core/navigation.py) |
| `Campo` | — | `st.text_input`, `st.text_area`, `st.selectbox` |

### Componentes de la interfaz (`src/components/`)

| Archivo | Función | Pantallas |
| --- | --- | --- |
| `layout.py` | `render_header`, `render_page_header`, `eyebrow`, `render_notice`, `render_brand`, `render_status_screen` | Todas; A6 y A7 |
| `table.py` | `render_table(headers, widths, rows, key)` con celdas de texto, badge (`(texto, color)`) o `Actions`; devuelve la acción pulsada | D1–D5, AD1, AD2 |
| `course_card.py` | `render_path_card` | E1 |
| `path_timeline.py` | `render_path_timeline`, `step_detail` | E5 |
| `quiz_form.py` | `render_options`, `render_answer_review` | E3, E6, E7, E8 |
| `video_player.py` | `render_video`, `render_explanation` | E6 |
| `levels.py` | `render_levels` | E4, D4 |
| `kpi_cards.py` | `render_kpis`, `render_metric_card` | E11, D3, AD2, AD3 |
| `badge_card.py` | `render_badge_hero`, `render_badge_slot` | E10, E12 |
| `role_card.py` | `render_role_card` | A1 |

Reglas:

- Los componentes reciben **todos** sus datos por parámetro y devuelven lo que eligió el usuario; la página decide qué hacer.
- **Prohibido en `components/`:** leer o escribir `st.session_state`, llamar a `services/` o `clients/`, aplicar reglas de negocio.
- Todo widget que se repite lleva un `key` derivado del id del dato (`f"open-path-{path.id}"`).
- Antes de crear un componente se busca uno que sirva con otros parámetros. Un bloque que aparece en varias pantallas va a `components/`; uno único se queda en la página.
- Texto de usuario o de la IA: `st.markdown` sin `unsafe_allow_html`.

## 4. Pantallas de Figma → páginas

Prefijos de Figma: **A** acceso, **E** estudiante, **D** docente, **AD** admin. La tabla completa con los endpoints está en el [README](README.md#pantallas-roles-y-endpoints).

| Frame | Node | Página |
| --- | --- | --- |
| A1 · Selector de rol | `2:169` | `pages/common/role_selector.py` (solo sin login) |
| A2–A5 · Login, registro, recuperar contraseña | `2:201`, `2:225`, `2:251`, `2:275` | **No se construyen**: son de Keycloak (`st.login`). Su estilo va al tema del realm en `keycloak/` |
| A6 · 403, A7 · Sesión expirada | `2:290`, `8:2` | `main.py` + `core/errors.py` + `render_status_screen` |
| E1 · Catálogo | `5:2` | `pages/student/catalog.py` |
| E2 · Perfil, E3 · Diagnóstico, E4 · Resultado | `5:37`, `5:61`, `5:97` | `pages/student/diagnostic.py` (tres pasos deducidos de los datos) |
| E5 · Vista de ruta | `5:148` | `pages/student/my_path.py` |
| E6 · Tema, E7 · Resultado del quiz | `5:209`, `5:245` | `pages/student/topic.py` |
| E8 · Evaluación final | `3:348` | `pages/student/final_assessment.py` |
| E9 · Repaso dirigido | `5:280` | `pages/student/review.py` |
| E10 · Badge | `5:311` | `pages/student/badge.py` |
| E11 · Mi progreso | `5:348` | `pages/student/progress.py` |
| E12 · Logros | `5:382` | `pages/student/achievements.py` |
| D1 · Mis cursos | `3:2` | `pages/teacher/courses.py` |
| D2 · Curso y syllabus | `6:2` | `pages/teacher/syllabus_review.py` |
| D3 · Ruta y avance | `6:107` | `pages/teacher/dashboard.py` |
| D4 · Detalle de estudiante | `3:71` | `pages/teacher/student_detail.py` |
| D5 · Revisión de recursos y preguntas | `8:13` | `pages/teacher/content_review.py` |
| AD1 · Usuarios y roles | `3:174` | `pages/admin/users.py` |
| AD2 · Log LLM y costos | `3:262` | `pages/admin/llm_logs.py` |
| AD3 · Métricas globales | `8:133` | `pages/admin/metrics.py` |

### Lo que se infirió (sin contexto de diseño por el límite del MCP)

De D2–D5, AD1–AD3 y A7 se tienen los textos y la posición de cada capa, pero no las etiquetas de los botones y badges instanciados. Se completaron así; **cuando haya cupo, se verifican con `get_design_context` y se corrigen**:

| Pantalla | Inferido |
| --- | --- |
| D2 | Botones del encabezado: «Ruta y avance» y «Revisar contenido». Acciones: «Agregar tema» y «Editar temas» (deshabilitados hasta que exista la capa de IA) y «Validar syllabus y publicar». Badges de Bloom en azul y de embedding «Indexado»/«Pendiente» |
| D3 | Botón «Editar umbrales» (abre un diálogo). Badges de inscripción «En curso», «Completada», «Abandonada». Se agregó la columna «Ver detalle» para abrir D4 |
| D4 | Un botón «Descargar intentos» (CSV). Badges de resultado «Aprobado»/«No aprobado» |
| D5 | Las dos pestañas del diseño son el filtro «Todo»/«Pendientes»; el tema se elige con un selector. Acciones: «Aprobar», «Retirar», «Restaurar» |
| AD1 | Botones «Nuevo usuario» (diálogo) y «Exportar CSV». Badges de rol y de estado «Activo»/«Inactivo» |
| AD3 | Badge de cada métrica: «Meta ≥ x» (verde si se cumple, ámbar si no) con las metas del brief; «Reportar» para el costo |
| A7 | Botón «Volver a entrar» y enlace «Cambiar de rol» |

### Diferencias de contenido con Figma

- Los números (inscritos, horas, porcentajes) salen de los datos de ejemplo, no se copian del diseño: el diseño es una foto de una historia y no es consistente entre pantallas (p. ej., E12 muestra un badge que E5 todavía no ha ganado).
- El quiz muestra las preguntas una por una con «Siguiente» y, en la última, «Enviar respuesta».
- «Reintentar con otra explicación» (E7) solo aparece si el tema no se aprobó y quedan intentos.

## 5. Assets

- **El diseño no tiene imágenes ni íconos exportables.** Cuando exista un logo, va en `app/assets/images/` (`logo.svg`, `logo-icon.svg`) y se usa con `st.logo` y `st.set_page_config(page_icon=...)`.
- **Fuente:** Inter variable en `src/static/fonts/InterVariable.woff2` con su licencia (`OFL.txt`). Se aloja con la app; no se carga desde Google Fonts.
- **Contenido de los cursos** (videos, lecturas): no es un asset; viene de la API como URL.
- **CDN:** no hay.
- Las URLs de imágenes que entrega el MCP de Figma duran 7 días: se descargan a `assets/images/` y nunca se enlazan desde el código.

## 6. Íconos

- Material Symbols, incluidos en Streamlit, con la cadena `:material/<nombre>:` en `icon=` o dentro del Markdown. No hay carpeta de íconos ni librería aparte, y no se exportan íconos de Figma.
- Nombres en inglés de [Material Symbols](https://fonts.google.com/icons): `school` (marca), `workspace_premium` (badge), `lock` (logro bloqueado), `chevron_right` (abrir tema), `play_circle` (video), `swap_horiz` (cambiar de rol).
- No se usan emojis como íconos.

## 7. Estilos

- **Sin CSS.** El CSS inyectado depende de clases internas de Streamlit que cambian entre versiones. Si un PR lo justifica, va en un solo archivo cargado desde `components/layout.py`, nunca disperso por las páginas.
- **Texto pequeño y de color:** `:small[...]`, `:blue[...]`, `:gray[...]`, `:orange[...]` de Markdown (p. ej., el antetítulo es `:small[:blue[**PASO 1 DE 3 · PERFIL**]]`).
- **Avisos ámbar** («Tu rol: Docente · ...»): `render_notice`, que usa `st.warning` con la paleta del tema.
- **Responsive:** `layout="wide"`, máximo 3 columnas; `st.columns` se apila en pantallas angostas. No hay versiones aparte para celular.
- **Textos:** en español, tal como aparecen en Figma (con el espacio antes de `%`). Los identificadores, las claves de sesión y los `key` de widgets van en inglés.

## 8. Flujo para implementar o corregir un frame

1. Buscar el `nodeId` en la sección 4 (o con `get_metadata` si es un frame nuevo).
2. `get_design_context` del frame (`skillNames="resource:figma-design-to-code"`), con captura. Leer la estructura, los textos y los estados; descartar el React.
3. Si hay un color o un tamaño nuevo, agregarlo a la sección 2 y a `config.toml` o `components/theme.py`.
4. Reusar los componentes de la sección 3; crear uno nuevo solo si el bloque se repite.
5. Si la pantalla necesita datos nuevos: el modelo en `clients/models.py`, la operación en `clients/base.py`, la respuesta en `clients/sample_data.py` (con las reglas que aplicaría la API) y la vista en `services/`.
6. `app/scripts/dev.sh all`. Agregar la página a `tests/ui/test_pages.py` con el título que debe mostrar.
7. Correr la app (`app/scripts/dev.sh run`) y comparar con la captura de Figma.

### Qué no se hace

- Llamar a la API o leer el token desde una página o un componente.
- Ocultar un botón como medida de seguridad: la API protege (401/403/404). La matriz de permisos de Figma (`2:3`) solo dice qué se muestra.
- Guardar datos personales en `st.cache_data`.
- Poner reglas de negocio (umbrales, intentos, calificación) en `services/` o en las páginas: en el prototipo las simula `clients/sample_data.py`; en producción, la API.
