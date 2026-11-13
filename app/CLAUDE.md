# Reglas de diseño para la interfaz (Figma v3 → Streamlit)

Reglas para pasar los diseños de Figma v3 al código de `app/`. Completan la arquitectura de [`README.md`](README.md) y el [ADR 0006](../docs/adr/0006-frontend-streamlit.md); si algo choca, mandan esos dos documentos. Las decisiones de esta reescritura salen de las secciones 2.6, 5.5 y 5.5.1 del [plan de implementación](../PLAN_IMPLEMENTACION_V3.md) y del vocabulario de roles de su sección 13.

## Fuente del diseño

| Dato | Valor |
| --- | --- |
| Archivo | «SmartMentor · Prototipo Fase 0 v3 (4)» |
| `fileKey` | `atp2fZdSolEoaww3n9jRLg` |
| Página | `0:1` (sigue llamándose «SmartMentor v2» en Figma; es la única) |
| Biblioteca de componentes | frame `24:2` «Componentes · Biblioteca» |
| Matriz de permisos por rol | frame `2:3` |
| Componente nuevo | `94:407` «Estado de carga» |
| Especificación sin conexión a Figma | [`design/03-prototipo-alta-fidelidad/v3/`](../design/03-prototipo-alta-fidelidad/v3/README.md): textos, diseño automático y enlaces de las 96 pantallas ([`pantallas.md`](../design/03-prototipo-alta-fidelidad/v3/pantallas.md), [`estructura-pantallas.json`](../design/03-prototipo-alta-fidelidad/v3/estructura-pantallas.json)), [`tokens.json`](../design/03-prototipo-alta-fidelidad/v3/tokens.json) y [`variables.json`](../design/03-prototipo-alta-fidelidad/v3/variables.json) |
| Inventario y casos de uso | [`design/03-prototipo-alta-fidelidad/README.md`](../design/03-prototipo-alta-fidelidad/README.md) y [`casos-de-uso.md`](../design/01-flujo-y-casos-de-uso/casos-de-uso.md) |
| Variables de Figma | **Existen y están resueltas** (24 nombres, sección 2). 23 se leyeron con `get_variable_defs` en tres frames; `error/acento` (`118:923`) no tiene valor porque ninguna pantalla lo usa |
| Límite del MCP | El plan **Starter** limita las llamadas. **No hace falta volver a Figma** para construir: la especificación versionada trae los textos de todos los frames. Solo se reconecta para confirmar `error/acento` o que el archivo no cambió desde el 2026-10-20 |

Todos los frames de pantalla miden 1280 × 800 (escritorio) o más altos; no hay versiones para celular.

## Estado

Hoy `app/src` es el **prototipo de la Fase 0** (v2): páginas en `pages/student`, `pages/teacher` y `pages/admin`, datos de ejemplo en `clients/sample_data.py`, sin login. La Fase 7 lo **rehace desde Figma v3** conservando el andamiaje técnico (Ruff, mypy estricto, pytest con `AppTest`, `dev.sh`, Dockerfile, fuente Inter). Esta guía describe el destino; lo que aún no existe se marca como «Fase 7».

## 1. Tecnología: no hay React, bundler ni librería de estilos

| Pregunta | Respuesta en este proyecto |
| --- | --- |
| Framework de UI | **Streamlit 1.65** (Python 3.12), multipágina con `st.navigation(position="hidden")` y una barra superior propia. La versión queda fija |
| Librería de estilos | Ninguna. El aspecto sale de `.streamlit/config.toml` y de **un directorio de CSS propio** (sección 7) |
| Build y bundler | Ninguno. Dependencias con `uv` (`pyproject.toml` y `uv.lock`); Ruff (línea de 100, comillas dobles), mypy estricto y pytest, igual que la API. Se corren en contenedores con `app/scripts/dev.sh` |
| Gráficas | Las nativas de Streamlit; la paleta está en `chartCategoricalColors` del tema |
| Grafo de temas | `st.graphviz_chart` (D2d) |
| Storybook o catálogo de componentes | No hay. Las páginas se prueban con `streamlit.testing.v1.AppTest` en `tests/ui/` |

**Regla principal:** `get_design_context` devuelve código de referencia en React y Tailwind. **No se copia.** Sirve para leer la estructura, los textos, el espaciado y los colores, y se reescribe con widgets de Streamlit. Nunca se agrega React, Tailwind ni componentes personalizados (`streamlit.components.v1`). Un detalle de Figma que Streamlit no soporta se simplifica y se anota en «Diferencias aceptadas».

## 2. Tokens de diseño

### Variables de Figma (24)

Fuente: [`v3/variables.json`](../design/03-prototipo-alta-fidelidad/v3/variables.json). Los nombres de Figma quedan en español; el CSS usa su equivalente en inglés (columna «Variable CSS»), y el único lugar con hexadecimales es `tokens.css` (sección 7).

| Variable de Figma | Hex | Variable CSS | Uso |
| --- | --- | --- | --- |
| `texto/principal` | `#15181E` | `--text-primary` | Texto principal |
| `texto/secundario` | `#4A5160` | `--text-secondary` | Texto secundario |
| `texto/terciario` | `#5F6776` | `--text-tertiary` | Etiquetas y metadatos |
| `texto/sobre-acento` | `#FFFFFF` | `--text-on-accent` | Texto sobre botones de color |
| `fondo/pagina` | `#F5F6F8` | `--bg-page` | Fondo de la página |
| `fondo/superficie` | `#FFFFFF` | `--bg-surface` | Tarjetas, campos, barra superior |
| `fondo/sutil` | `#FAFBFC` | `--bg-subtle` | Filas alternas y paneles |
| `fondo/neutro` | `#EEF0F3` | `--bg-neutral` | Badge gris y fondos neutros |
| `borde/default` | `#E3E6EB` | `--border-default` | Bordes de tarjetas y barra |
| `borde/fuerte` | `#C9CDD5` | `--border-strong` | Bordes de campos |
| `aprendiz/acento` | `#1D5FD1` | `--learner-accent` | Botón principal y antetítulos del Aprendiz |
| `aprendiz/suave` | `#E8F0FC` | `--learner-soft` | Fondos y badge azul |
| `aprendiz/texto` | `#174EA6` | `--learner-text` | Texto sobre fondo suave |
| `instructor/acento` | `#11774A` | `--instructor-accent` | Botón principal del Instructor, estados aprobado o dominado |
| `instructor/suave` | `#E5F4EC` | `--instructor-soft` | Fondos y badge verde |
| `instructor/texto` | `#0D6640` | `--instructor-text` | Texto sobre fondo suave |
| `admin/acento` | `#5B3CC4` | `--admin-accent` | Botón principal del Administrador |
| `admin/suave` | `#EEEAFB` | `--admin-soft` | Fondos y badge violeta |
| `admin/texto` | `#4B2FB0` | `--admin-text` | Texto sobre fondo suave |
| `aviso/acento` | `#D98A00` | `--warning-accent` | Advertencias |
| `aviso/suave` | `#FFF4DE` | `--warning-soft` | Fondo del aviso y badge ámbar |
| `aviso/texto` | `#8A5300` | `--warning-text` | Texto del aviso |
| `error/suave` | `#FDECEA` | `--error-soft` | Fondo del error y del 403 |
| `error/texto` | `#9B1C14` | `--error-text` | Texto del error |
| `error/acento` | **sin valor** | `--error-accent` | Nombre inferido por la secuencia (`118:923`); ninguna pantalla lo usa. Mientras no se confirme, `tokens.css` lo define igual que `--error-text` |

Cambios frente a la v2: el azul `#0073E5` pasa a `#1D5FD1`, el verde `#1A8C4D` a `#11774A` y el violeta `#734DD9` a `#5B3CC4`. Dos variables (`texto/sobre-acento` y `fondo/superficie`) valen `#FFFFFF`; se asignaron por orden de creación.

### Otros tokens

Tomados de [`v3/tokens.json`](../design/03-prototipo-alta-fidelidad/v3/tokens.json) (frecuencia de uso en el diseño):

| Token | Valores |
| --- | --- |
| Tipografía | **Inter.** Título de página 28 px Bold (el estilo más usado entre los de 16 px o más); título de tarjeta 18 px Semibold; cuerpo 13 px Regular; etiquetas 12 px Semibold; badges 11 px Semibold |
| Radios | Botones y badges en píldora (99 px, 746 usos); tarjetas 14 px y 16 px; campos 10 px; filas 12 px; chips 6 px |
| Espaciado | Múltiplos de 2: 4, 6, 8, 10, 12, 14 y 16 px (los más usados son 10, 4 y 12 px) |
| Sombras | Ninguna |

### Dónde viven en el código

| Qué | Dónde |
| --- | --- |
| Hexadecimales, radios, espaciados y tipografía como variables CSS | `src/static/styles/tokens.css` (Fase 7). **Es el único archivo con hexadecimales** |
| Valores que Streamlit toma del tema nativo (`primaryColor`, fondos, texto, fuente) | [`.streamlit/config.toml`](.streamlit/config.toml), sección `[theme]`. Una prueba verifica que coinciden con `tokens.css` |
| Fuente Inter | [`src/static/fonts/`](src/static/fonts/), declarada en `[[theme.fontFaces]]` y servida con `server.enableStaticServing` |
| Texto y color de cada estado (badges) | [`src/components/theme.py`](src/components/theme.py) |
| Etiquetas de rol y de contexto | `src/core/labels.py` (Fase 7, sección 8) |
| Formato de números y fechas («92 %», «1,5», «1 h 20 min», «5 oct 2026») | [`src/components/formatting.py`](src/components/formatting.py) |

No hay transformación automática de `variables.json` a CSS: un valor nuevo de Figma se copia a mano a `tokens.css` y, si Streamlit lo usa, a `config.toml`. **Nunca se escribe un hexadecimal en una página ni en un componente.**

### Diferencias aceptadas con Figma

| En Figma | En Streamlit | Motivo |
| --- | --- | --- |
| Fondo gris `#F5F6F8` con tarjetas blancas | CSS de `layout.css` da el fondo y las tarjetas | `st.container` no tiene color propio; se resuelve con `.st-key-<nombre>` |
| Tres botones primarios (azul, verde, violeta) | Un `type="primary"` cuyo color toma `roles.css` (`--accent`). **P1:** depende de selectores que pueden cambiar con la versión de Streamlit | `primaryColor` es uno para toda la app |
| Botón secundario gris sin borde | Botón secundario blanco con borde | Estilo fijo de Streamlit |
| Logo: cuadrado azul provisional | Ícono `:material/school:` | No hay logo todavía |
| Avatar con iniciales | `st.popover` con las iniciales: nombre, correo, **roles del usuario («Cambiar de perfil», CU-35)** y salir | El cierre de sesión real redirige al `end_session_endpoint` de Keycloak |
| Opción elegida con fondo azul claro | `st.radio` o CSS del componente | Las opciones en tarjeta exigen CSS por `key` |
| Insignia: círculo azul con estrella | Ícono `:material/workspace_premium:` | Sin CSS no hay círculos de color |
| Recuadro negro del video | Recuadro con borde y los datos del video; con URL, `st.video` | El video viene de la API |
| Espaciados exactos en píxeles | Orden de los elementos, `gap`, `st.space` | Streamlit no expone márgenes |
| KPI con el valor arriba y la etiqueta abajo | `st.metric`: etiqueta arriba, valor abajo | Widget fijo |
| Botones «(Demo del prototipo)» y avance automático a los 2 segundos | **No se construyen** | Los estados reales salen de la API; en `fixtures` se usan escenarios de datos |
| Tamaños de letra en px (título 28, tarjeta 18, cuerpo 13) | Los tokens en `rem` salen un 12,5 % más pequeños (24,5, 15,75 y 11,4 px), porque la raíz de Streamlit es de 14 px | Decisión del dueño (2026-11-13, V-010): se deja así |

## 3. Componentes

### Biblioteca de Figma (`24:2`) → código

| Componente de Figma | Variantes | Equivalente |
| --- | --- | --- |
| `Botón` | Primario azul, verde y violeta; Secundario | `st.button(type="primary")` / `st.button()`. Para navegar, `st.switch_page` o `st.page_link` |
| `Badge` | Verde, Azul, Ámbar, Gris, Violeta | `st.badge(texto, color=...)` con `green`, `blue`, `orange`, `gray`, `violet` |
| `Menú superior` (`Nav`) | `Rol=Aprendiz`, `Instructor`, `Admin` | `render_header` en [`components/layout.py`](src/components/layout.py); los enlaces de cada rol están en `LINKS` de [`core/navigation.py`](src/core/navigation.py). El menú del Aprendiz suma «Mi perfil» |
| `Campo` | — | `st.text_input`, `st.text_area`, `st.selectbox` |
| `Estado de carga` (`94:407`) | — | `render_loading_steps` (U1a–U1d y D1c) |

### Componentes de la interfaz (`src/components/`)

Existentes (se conservan):

| Archivo | Función | Pantallas |
| --- | --- | --- |
| `layout.py` | `render_header`, `render_page_header`, `eyebrow`, `render_notice`, `render_brand`, `render_status_screen` | Todas; A6 y A7 |
| `table.py` | `render_table(headers, widths, rows, key)` con celdas de texto, badge o `Actions` | D1–D5, AD1, AD2, AD5 |
| `course_card.py` | `render_path_card` | E1 |
| `path_timeline.py` | `render_path_timeline`, `step_detail` (con el motivo de cada paso) | E5, E5b |
| `quiz_form.py` | `render_options`, `render_answer_review` | E3, E6b, E7, E8 |
| `video_player.py` | `render_video`, `render_explanation` | E6 |
| `levels.py` | `render_levels` | E4, D4 |
| `kpi_cards.py` | `render_kpis`, `render_metric_card` | E11, D3, AD2, AD3 |
| `badge_card.py` | `render_badge_hero`, `render_badge_slot` | E10, E12 |
| `role_card.py` | `render_role_card` | A1 (solo `fixtures`) |

Nuevos de la v3 (Fase 7):

| Archivo | Función | Pantallas |
| --- | --- | --- |
| `loading_steps.py` | `render_loading_steps(title, steps, estimate)`: tres pasos con «Listo», «En curso» y «Pendiente»; sondea el trabajo y ofrece reintentar si falla | U1a–U1d, D1c |
| `consent_form.py` | Las dos casillas (datos obligatoria, piloto opcional) y el texto del consentimiento | A3, A3b, E11b |
| `resume_form.py` | Estudios, cargo, años de experiencia, herramientas, idioma y nivel | E2b, E15 |
| `objective_editor.py` | Verbo de Bloom + contenido + criterio; deshabilita «Guardar» si el criterio no es medible; vista previa con el número de temas | E4b |
| `rubric_result.py` | Detalle por criterio de la rúbrica de una respuesta corta | E7 |
| `attempt_history.py` | Historial de intentos y de intentos agotados | E7c, E9c, D4b |
| `topic_graph.py` | Grafo de temas con `st.graphviz_chart` y estado «Sin ciclos · validado» | D2d |
| `video_feedback.py` | «¿Te sirvió?», etiquetas y comentario anónimo | E6 |
| `annotation_form.py` | Rúbrica de 4 criterios y veredicto, anotación ciega | D5b |
| `likert_scale.py` | Escala de 1 a 5 y SUS de 10 ítems | E13a, E13b |

Reglas:

- Los componentes reciben **todos** sus datos por parámetro y devuelven lo que eligió el usuario; la página decide qué hacer.
- **Prohibido en `components/`:** leer o escribir `st.session_state`, llamar a `services/` o `clients/`, aplicar reglas de negocio.
- Todo widget que se repite lleva un `key` derivado del id del dato (`f"open-path-{path.id}"`). Ese `key` también es el selector estable del CSS (`.st-key-<key>`).
- Antes de crear un componente se busca uno que sirva con otros parámetros. Un bloque que aparece en varias pantallas va a `components/`; uno único se queda en la página. Cada componente con estilo propio tiene su archivo en `static/styles/components/`.
- Texto de usuario o de la IA: `st.markdown` sin `unsafe_allow_html`.
- Cada página resuelve el `next_action` que devuelve la API; **nunca deduce estados por su cuenta**.

## 4. Pantallas de Figma → páginas

Prefijos de Figma: **A** acceso, **E** aprendiz, **D** instructor, **AD** administrador, **U** estados de carga, **C4** documentación. Las variantes por curso (E2c–g, E2bc–bg, E3c–g, E4c–g, E5c–g y U1ac–ag, 35 frames) repiten la plantilla de su pantalla base con otro contenido; no tienen página propia. La lista completa con casos de uso y prioridades está en el [inventario](../design/03-prototipo-alta-fidelidad/README.md#inventario-de-pantallas).

Las páginas están en `pages/learner`, `pages/instructor`, `pages/admin` y `pages/common` (Fase 7). Orden de construcción: aprendiz (P0), instructor (P0), administrador (P1) y piloto (P0 si hay grupo de control).

| Frame | Node | Página |
| --- | --- | --- |
| A1 · Selector de rol | `2:169` | `pages/common/demo_role_selector.py` (solo con `APP_DATA_SOURCE=fixtures`) |
| A2, A4, A5 · Login, recuperar contraseña | `2:201`, `2:251`, `2:275` | **No se construyen**: son de Keycloak (`st.login`). Su estilo va al tema del realm (P2) |
| A3 · Registro | `2:225` | Keycloak; las dos casillas, en `pages/common/consent.py` |
| A3b · Consentimiento informado | `103:725` | `pages/common/consent.py` |
| A3c · Tus datos y tus derechos | `121:903` | `pages/common/data_rights.py` |
| A6 · 403, A7 · Sesión expirada | `2:290`, `8:2` | `main.py` + `core/errors.py` + `render_status_screen` |
| E1 · Catálogo | `5:2` | `pages/learner/catalog.py` |
| E2 · Perfil | `5:37` | `pages/learner/onboarding_profile.py` |
| E2b · Hoja de vida | `123:935` | `pages/learner/onboarding_resume.py` |
| E3 · Diagnóstico, U1a · Calculando tu nivel | `5:61`, `94:417` | `pages/learner/diagnostic.py` |
| E4 · Resultado y objetivo, E4b · Editar objetivo | `5:97`, `94:536` | `pages/learner/diagnostic_result.py` |
| E5 · Vista de ruta, E5b · Ruta fija | `5:148`, `96:657` | `pages/learner/path.py` (una página, dos variantes) |
| E6 · Tema | `5:209` | `pages/learner/topic.py` |
| E6b, E6c · Quiz; U1b, U1c · Carga | `81:419`, `94:489`, `94:441`, `94:465` | `pages/learner/quiz.py` |
| E7, E7b, E7c · Resultado del quiz | `5:245`, `69:373`, `94:607` | `pages/learner/quiz_result.py` |
| E8 · Evaluación final, U1d | `3:348`, `124:1271` | `pages/learner/final_assessment.py` |
| E9 · Repaso dirigido, E9c · Final con intentos agotados | `5:280`, `103:769` | `pages/learner/final_result.py` |
| E10 · Badge | `5:311` | `pages/learner/badge.py` |
| E11 · Mi progreso, E11b · Autorizaciones | `5:348`, `122:962` | `pages/learner/progress.py` |
| E12 · Logros | `5:382` | `pages/learner/achievements.py` |
| E13a, E13b · Encuesta final | `94:674`, `94:812` | `pages/learner/final_survey.py` |
| E14 · Prueba de retención (P2) | `104:935` | `pages/learner/retention_test.py` |
| E15 · Mi perfil | `123:1031` | `pages/learner/my_profile.py` |
| D1 · Mis cursos | `3:2` | `pages/instructor/courses.py` |
| D1b · Nuevo curso, D1c · Extrayendo, D1d · Error al leer | `95:538`, `95:592`, `95:618` | `pages/instructor/new_course.py` |
| D2, D2b, D2c, D2d · Syllabus y grafo | `6:2`, `95:644`, `95:776`, `104:1102` | `pages/instructor/syllabus_review.py` |
| D3 · Ruta y avance, D3b · Configurar | `6:107`, `95:883` | `pages/instructor/path_dashboard.py` |
| D4, D4b, D4c · Detalle de aprendiz | `3:71`, `103:825`, `103:940` | `pages/instructor/learner_detail.py` |
| D5, D5d · Revisión de contenido | `8:13`, `103:1058` | `pages/instructor/content_review.py` |
| D5b · Anotación de preguntas | `96:850` | `pages/instructor/item_annotation.py` |
| D5c · Calificación humana | `96:1013` | `pages/instructor/short_answer_grading.py` |
| D5e · Video del tema | `103:1193` | `pages/instructor/topic_videos.py` |
| D5f · Calidad de los videos (P2) | `124:1066` | `pages/instructor/video_quality.py` |
| AD1 · Usuarios y roles | `3:174` | `pages/admin/users.py` |
| AD2 · Log LLM y costos | `3:262` | `pages/admin/llm_logs.py` |
| AD3 · Métricas globales | `8:133` | `pages/admin/metrics.py` |
| AD4, AD4b · Piloto | `96:1083`, `110:885` | `pages/admin/pilot.py` |
| AD5 · Cursos, rutas e inscripciones | `103:1279` | `pages/admin/courses_enrollments.py` |
| C4 · Catálogo de prompts (P2) | `104:985` | `pages/admin/prompt_catalog.py` |

### Diferencias de contenido con Figma

- Los números (inscritos, horas, porcentajes) salen de los datos, no se copian del diseño. En el modo `fixtures` se generan de una sola fuente para que las pantallas sean coherentes (contradicciones C-14 y C-15 del plan).
- El quiz muestra las preguntas una por una; la respuesta corta (E6c) lleva la rúbrica visible y un límite de 500 caracteres.
- «Reintentar con otra explicación» (E7b) solo aparece si el tema no se aprobó y quedan intentos.
- El índice de calidad del video no se muestra al aprendiz antes de que califique (C-08).
- Las pantallas de carga (U1x) y la de extracción (D1c) tienen un estado de error que Figma no dibuja: se resuelve desde `ai_jobs.status` (ver [`flujos.md`](../design/01-flujo-y-casos-de-uso/flujos.md#casos-de-error-de-las-pantallas-de-carga-u1x)).

## 5. Assets

- **El diseño no tiene imágenes ni íconos exportables.** Cuando exista un logo, va en `app/assets/images/` (`logo.svg`, `logo-icon.svg`) y se usa con `st.logo` y `st.set_page_config(page_icon=...)`.
- **Fuente:** Inter variable en `src/static/fonts/InterVariable.woff2` con su licencia (`OFL.txt`). Se aloja con la app; no se carga desde Google Fonts.
- **Contenido de los cursos** (videos, lecturas): no es un asset; viene de la API como URL.
- **CDN:** no hay.
- Las URLs de imágenes que entrega el MCP de Figma duran 7 días: se descargan a `assets/images/` y nunca se enlazan desde el código. Las 97 capturas PNG del prototipo no se versionan (DEF-17).

## 6. Íconos

- Material Symbols, incluidos en Streamlit, con la cadena `:material/<nombre>:` en `icon=` o dentro del Markdown. No hay carpeta de íconos ni librería aparte, y no se exportan íconos de Figma.
- Nombres en inglés de [Material Symbols](https://fonts.google.com/icons): `school` (marca), `workspace_premium` (badge), `lock` (logro bloqueado), `chevron_right` (abrir tema), `play_circle` (video), `swap_horiz` (cambiar de perfil).
- No se usan emojis como íconos.

## 7. Estilos: un directorio para todo el CSS

Esto **reemplaza** la regla anterior («Sin CSS») y **amplía** la de este documento: ahora todo el CSS vive en `app/src/static/styles/`, con un cargador único. Se registra en el ADR 0017.

```text
app/src/static/styles/
├── README.md        # cómo se cambia un color, orden de carga y reglas
├── tokens.css       # ÚNICO lugar con hexadecimales: las 24 variables de Figma, radios, espaciados y tipografía, como variables CSS
├── base.css         # tipografía, enlaces, foco visible
├── layout.css       # barra superior, tarjetas, rejilla
├── roles.css        # acento por rol: --accent, --accent-soft, --accent-text
└── components/      # un archivo por componente (badge.css, loading_steps.css, rubric_result.css…)
```

| Regla | Detalle |
| --- | --- |
| Cargador único | `app/src/core/styles.py` lee los archivos en orden fijo (tokens, base, layout, roles, componentes) y los inyecta una vez por página desde `render_header`. Se guarda en caché salvo con `APP_ENV=local`, donde se relee para ver los cambios al guardar |
| Colores solo como variables | Fuera de `tokens.css` no puede haber hexadecimales ni `rgb()`; se usa `var(--learner-accent)` y similares. Una prueba lo verifica |
| Selectores estables | Solo clases propias y `.st-key-<nombre>` (el contenedor de Streamlit que lleva `key`). No se usan clases internas de Streamlit, que cambian entre versiones. La versión de Streamlit queda fija |
| Tema nativo | Los valores que Streamlit toma de `.streamlit/config.toml` (`primaryColor`, fondos, texto, fuente) siguen allí; una prueba verifica que coinciden con `tokens.css` |
| Contraste | La misma prueba calcula el contraste de los pares de `tokens.css`: 4,5:1 para texto y 3:1 para bordes de campos |
| Texto del usuario | El CSS es propio; el texto del usuario o de la IA nunca se inyecta con `unsafe_allow_html` |
| Perfiles de contexto (P2) | `APP_CONTEXT_PROFILE` puede cargar un `themes/<perfil>.css` que solo redefine variables |
| Botón principal por rol | `roles.css` define `--accent` según el rol activo, para que el botón primario sea azul, verde o violeta como en Figma. **P1**, porque depende de selectores de Streamlit que pueden cambiar |

Otras reglas de presentación:

- **Texto pequeño y de color:** `:small[...]`, `:blue[...]`, `:gray[...]`, `:orange[...]` de Markdown cuando basta con eso (p. ej., el antetítulo `:small[:blue[**PASO 1 DE 4 · PERFIL**]]`).
- **Avisos ámbar** («Tu rol: Instructor · ...»): `render_notice`, que usa `st.warning` con la paleta del tema.
- **Responsive:** `layout="wide"`, máximo 3 columnas; `st.columns` se apila en pantallas angostas. No hay versiones aparte para celular.
- **Accesibilidad:** el estado siempre lleva texto además del color (los badges ya traen texto); foco visible en `base.css`.
- **Textos:** en español, tal como aparecen en Figma (con el espacio antes de `%`). Los identificadores, las claves de sesión y los `key` de widgets van en inglés.

## 8. Roles y etiquetas

Los códigos de rol son **`learner`**, **`instructor`** y **`admin`** (sección 13 del plan). Las carpetas de páginas, las enumeraciones y las claves de sesión usan esos códigos; nunca `student` ni `teacher`.

| Código | Etiqueta (perfil `generic`) | En el menú |
| --- | --- | --- |
| `learner` | Aprendiz | Aprendiz |
| `instructor` | Instructor | Instructor |
| `admin` | Administrador | Admin |

- Las etiquetas visibles salen de `src/core/labels.py` (un diccionario por perfil de contexto: `generic`, `academic`, `corporate`), no de cadenas escritas en las páginas. Solo `generic` es P0. Detalle en el [glosario](../design/01-flujo-y-casos-de-uso/glosario.md).
- El «rol activo» es solo de presentación: la API autoriza por la unión de los roles del usuario. `GET /me` devuelve `roles`, `role_labels` y `default_role`; el menú del avatar permite cambiar de perfil (CU-35).
- Un experto externo que anota o califica es un `instructor` asignado en `course_evaluators`; no existe un rol `evaluator`.

## 9. Datos y clientes

| Pieza | Plan (Fase 7) |
| --- | --- |
| `core/auth.py` | `st.login("keycloak")` con `smartmentor-ui`; revisión de `exp` antes de cada llamada; cierre de sesión con redirección al `end_session_endpoint` |
| `clients/api.py` | `httpx` con el token en cada llamada, errores RFC 9457 como `ApiError`, `Idempotency-Key` en las entregas y sondeo de trabajos con espera progresiva |
| `clients/fixtures.py` | Responde con JSON fijos de `app/tests/fixtures/`, generados por el arnés de `ai/` y validados contra los esquemas de la API. **Sin reglas de negocio.** Se activa con `APP_DATA_SOURCE=fixtures` |
| `clients/models.py` | Modelos generados desde el OpenAPI de la API (`app/scripts/dev.sh gen-models`) |
| Pruebas | `AppTest` por página con `fixtures`; prueba del cliente con respuestas simuladas (`respx`) |

El prototipo de la Fase 0 usa `clients/sample_data.py` y `APP_DATA_SOURCE=sample`; se sustituye por lo anterior.

## 10. Flujo para implementar o corregir un frame

1. Buscar el `nodeId` en la sección 4 y sus textos en `v3/pantallas.md` y `v3/estructura-pantallas.json`. Solo si el frame es nuevo o dudoso se usa `get_metadata`.
2. Si hay conexión y cupo, `get_design_context` del frame (`skillNames="resource:figma-design-to-code"`), con captura. Leer la estructura, los textos y los estados; descartar el React.
3. Si hay un color o un tamaño nuevo, agregarlo a `tokens.css` (y a `config.toml` si Streamlit lo usa) y a la sección 2.
4. Reusar los componentes de la sección 3; crear uno nuevo solo si el bloque se repite, con su CSS en `static/styles/components/`.
5. Si la pantalla necesita datos nuevos: el modelo en `clients/models.py`, la operación en `clients/base.py`, la respuesta en `app/tests/fixtures/` y la vista en `services/`.
6. `app/scripts/dev.sh all`. Agregar la página a `tests/ui/test_pages.py` con el título que debe mostrar.
7. Correr la app (`app/scripts/dev.sh run`) y comparar con la captura de Figma.

### Qué no se hace

- Llamar a la API o leer el token desde una página o un componente.
- Ocultar un botón como medida de seguridad: la API protege (401/403/404). La matriz de permisos de Figma (`2:3`) solo dice qué se muestra.
- Guardar datos personales en `st.cache_data`.
- Poner reglas de negocio (umbrales, intentos, calificación, estados) en `services/` o en las páginas: las aplica la API.
- Escribir un hexadecimal o `rgb()` fuera de `tokens.css`, o apuntar a clases internas de Streamlit en el CSS.
- Construir los botones «(Demo del prototipo)» ni los avances automáticos de Figma.
