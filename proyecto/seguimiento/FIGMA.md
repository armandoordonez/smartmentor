# Figma: huecos y contradicciones

El [archivo de Figma v3](https://www.figma.com/design/atp2fZdSolEoaww3n9jRLg/SmartMentor-%C2%B7-Prototipo-Fase-0-v3-4) es el **prototipo para ver cómo luce** cada pantalla. Las reglas y los datos salen de la API y de los casos de uso ([`design/01-flujo-y-casos-de-uso/`](../../design/01-flujo-y-casos-de-uso/)). Cuando Figma no dibuja algo que el código necesita, o se contradice, se anota aquí y **se avisa al dueño antes de inventar el diseño**.

## Estado del archivo en vivo (revisado el 2026-11-12 13:55)

- Una página, «SmartMentor v2», con 96 pantallas, la matriz de permisos y la biblioteca de componentes.
- Los nombres de todas las pantallas coinciden con la copia del repo en [`design/03-prototipo-alta-fidelidad/v3/estructura-pantallas.json`](../../design/03-prototipo-alta-fidelidad/v3/estructura-pantallas.json). No apareció ninguna pantalla nueva ni faltó ninguna. Solo se compararon los nombres, no el contenido de cada una (eso deja abierta en parte la P-14 del plan).
- Todas las pantallas que le tocan a la app tienen página en `app/src/pages/` ([`navigation.py`](../../app/src/core/navigation.py)). A2, A4 y A5 son de Keycloak y no se construyen.

## Huecos (Figma no lo dibuja)

| ID | Registrado | Qué falta | Dónde se necesita | Mientras tanto | Estado |
| --- | --- | --- | --- | --- | --- |
| F-001 | 2026-11-12 13:55 | Estado de **error de un trabajo de IA** en las pantallas de carga (U1a–U1d, D1c) | Diagnóstico, quiz, final y extracción del syllabus | El código lo resuelve con `ai_jobs.status` ([`flujos.md`](../../design/01-flujo-y-casos-de-uso/flujos.md#casos-de-error-de-las-pantallas-de-carga-u1x)) | ✔ Aprobado por el dueño (2026-11-13 10:46): error con «Reintentar» y «Volver», avance guardado |
| F-002 | 2026-11-12 13:55 | **Catálogo vacío** (E1 sin rutas) | CU-02 | Por definir | ☐ |
| F-003 | 2026-11-12 13:55 | **Instructor sin cursos** (D1 vacío) | Primer ingreso del instructor | Por definir | ☐ |
| F-004 | 2026-11-12 13:55 | **Menú de perfil con cambio de rol** (CU-35). Figma solo tiene el selector previo al login (A1) | Usuarios con varios roles | Por definir | ☐ |
| F-012 | 2026-11-12 14:18 | **D5f pide datos que el sistema no recoge.** Figma muestra una calificación promedio («4,5»), el efecto en el quiz («+11 pts»), los reportes y un índice con 6 pesos (calificación 30 %, quiz 30 %, vista completa 15 %, reportes 10 %, fuente 10 %, subtítulos 5 %). El aprendiz (E6) solo elige una etiqueta (`useful`, `audio_issue`, `outdated`, `too_long`), si vio el video completo y un comentario. La API calcula un índice bayesiano con la proporción de «útil». Tampoco calcula el estado (recomendado, en observación, en revisión) ni agrupa los comentarios con IA | Calidad de los videos (T-014) | Decisión del dueño (2026-11-12 14:22): **la pantalla se ajusta a lo que mide la API**. Índice, «% útil», vista completa y etiquetas; «Efecto en el quiz» en «—»; la API calcula el estado con los umbrales 75 y 60 de Figma | ✔ Decidido (código ⬆ subido, sin PR) |
| F-013 | 2026-11-12 14:33 | **No hay estado «sin piloto»** en AD4: Figma siempre muestra un piloto ya creado. Con la API real puede no existir ninguno (se crea con `POST /pilots`) | Piloto (T-015d) | La página muestra un aviso y no ofrece crear uno. Falta decidir si se agrega un formulario de creación (ruta y fechas) | ☐ Decide el dueño |
| F-014 | 2026-11-12 14:3x (aprox.) | **AD4 dice «ítems equivalentes entre el diagnóstico y la evaluación final»**, pero el modelo de datos agrupa como equivalentes las versiones paralelas de la final y de la prueba de retención (`assessment_items.equivalence_group`, `docs/evaluation/metrics.md`). El diagnóstico no tiene grupo | Piloto (T-015d) | Decisión del dueño (2026-11-12 14:38): se cuenta lo que define `metrics.md` (temas con un grupo de dos o más versiones) y se cambia el texto de la pantalla | ✔ Decidido (código ⬆ subido, sin PR) |
| F-005 | 2026-11-12 13:55 | **Login del administrador**: no tiene pantalla propia | Acceso admin | Se usa la de A4 (Keycloak) | ✖ Resuelto por Keycloak |

## Contradicciones conocidas (de [`design/03…/README.md`](../../design/03-prototipo-alta-fidelidad/README.md#ajustes-pendientes-antes-de-la-prueba-de-usabilidad))

| ID | Registrado | Contradicción | Estado |
| --- | --- | --- | --- |
| F-006 | 2026-11-12 13:55 | Los datos de Laura (Regresión logística) no coinciden entre E5, D3 y D4. Julián Pérez aparece como «Abandonada» en D3 y «En espera por intentos agotados» en D4b (C-14, C-15) | ☐ |
| F-007 | 2026-11-12 13:55 | A3b muestra la fecha del piloto como del 2 al 15 de noviembre de 2026, que ya no es posible (C-03, P-09) | ☐ Decide el dueño |
| F-008 | 2026-11-12 13:55 | La calidad del video («81 de 100») se muestra antes de que el aprendiz califique (C-08) | ☐ |
| F-009 | 2026-11-12 13:55 | Marcas de terceros en los cursos de IA aplicada («Nuevo · Anthropic», «Nuevo · Google», «Claude Ventas») (C-01, DEF-04) | ☐ Decide el dueño |
| F-010 | 2026-11-12 13:55 | D2b dice «Embedding» donde debe decir «Revisión» (C-16) | ☐ |
| F-011 | 2026-11-12 13:55 | Falta confirmar el valor de la variable `error/acento` (`118:923`) (P-13) | ☐ |

### F-015 · 2026-11-12 · A7 «Tu sesión expiró»

Figma dice «Por seguridad cerramos tu sesión tras 30 minutos sin actividad». El dueño decidió que la sesión dure 3 h, así que el texto pasa a «3 horas». **Decidido** (el dueño).

## Revisión visual (T-034)

Comparación en el navegador (1280 × 800, app con datos de ejemplo en el puerto 8502) contra la captura de cada frame de Figma. Primera pasada del 2026-11-13 10:52: E1, D1 y AD1, después de corregir B-014. Las diferencias que ya acepta [`app/CLAUDE.md`](../../app/CLAUDE.md#diferencias-aceptadas-con-figma) (logo, avatar con menú, botón secundario con borde, espaciados exactos) no se repiten aquí.

| ID | Pantallas | En Figma | En la app | Propuesta | Estado |
| --- | --- | --- | --- | --- | --- |
| V-001 | Todas | Barra superior blanca, de lado a lado, pegada arriba | Tarjeta blanca con margen y esquinas redondeadas | Ajustar `layout.css` (`.st-key-app-header`) | ◐ Corregido, sin commit: fondo con `box-shadow` + `clip-path` y línea con `border-image-outset` (sin scroll horizontal ni selectores de Streamlit) |
| V-002 | D1, AD1 y otras con acciones | Botones de la página a la derecha del título | Debajo del título, a la izquierda | Que `render_page_header` acepte acciones y las ponga en una columna a la derecha | ◐ Corregido, sin commit: `render_page_header_with_actions` en D1, AD1, D2, D3 y D4 |
| V-003 | D1, AD1 (tablas) | La primera columna en texto normal | En negrita | Quitar `**…**` en `courses.py` y `users.py`, y revisar las demás tablas | ◐ Corregido en D1, AD1, D2, D3, D5, AD2 y AD5, sin commit |
| V-004 | Tablas | Tarjeta blanca | Fondo gris claro (`--bg-subtle`) | Usar `--bg-surface` en el contenedor de `render_table` | ◐ Corregido, sin commit (`layout.css`) |
| V-005 | E1 | Título de la tarjeta de 18 px semibold | Más pequeño | Ajustar `course_card.css` | ◐ Corregido, sin commit: semibold. El tamaño queda en 15,75 px (V-010, aceptado) |
| V-006 | D1 | Insignia «En revisión» azul | Ámbar (`staff_theme.py`: `in_review` → `orange`) | Cambiar a `blue`, salvo que el ámbar haya sido una decisión | ◐ Corregido, sin commit: azul (decisión del dueño) |
| V-007 | D1 | Subtítulo con el nombre del instructor («Prof. Elena Ramírez») | No aparece | Mostrar `me.full_name` como subtítulo | ◐ Corregido, sin commit: `me.full_name` como subtítulo (Figma antepone «Prof.») |
| V-008 | AD1 | Rol como insignia de color (verde, azul o violeta) | Texto plano; un usuario con varios roles los lista | Una insignia por rol | ◐ Corregido, sin commit: celda `Badges` en `render_table` |
| V-009 | AD1 | Correo en texto normal | Enlace azul (Markdown lo convierte solo) | Mostrarlo como código o escapar la `@` | ◐ Corregido, sin commit: celda `PlainText` con `st.text` |

| V-010 | Todas | Tamaños en px (título de página 28, de tarjeta 18, cuerpo 13) | `tokens.css` los define en `rem` (1,75, 1,125, 0,8125), y la raíz de Streamlit es de 14 px, no de 16: salen 24,5, 15,75 y 11,4 px | Pasar los tokens de tamaño a `px`, o recalcularlos con base 14. Cambia el tamaño de toda la interfaz, así que hay que revisar con capturas | ✔ Aceptada por el dueño (2026-11-13 11:19): los tamaños quedan como están |

| V-011 | E6 | Dos columnas: video, valoración y explicación a la izquierda, y la tarjeta del quiz a la derecha | Una sola columna; el quiz queda al final | Dos columnas en `topic.py` | ☐ **Después del PR 5**, que reescribe `topic.py` |
| V-012 | E6 | Video de unos 230 px de alto | `st.video` a todo el ancho, muy alto | Se resuelve con V-011 | ☐ Después del PR 5 |
| V-013 | E6 | La explicación va en una tarjeta | Título y texto sueltos | Tarjeta en `render_explanation` | ☐ Después del PR 5 |
| V-014 | E6 | Valoración con 5 estrellas | Solo etiquetas («Claro y útil»…) | La API guarda una etiqueta, no estrellas (como F-012) | ✔ Aceptada (modelo de datos) |
| V-015 | D3 | «Configurar ruta» a la derecha del título; nombres sin negrita; «Omitido» violeta y «Abandonada» ámbar; valores fuera de la meta en rojo; «Temas críticos» en un aviso ámbar | Botón debajo, negrita, grises y aviso como texto | `render_page_header_with_actions`, `MASTERY_BADGE` y `ADMIN_ENROLLMENT_BADGE`, `:red[…]` en los temas que la API marca como críticos, `st.warning` | ◐ Corregido, sin commit |
| V-016 | D3 | Celdas de la matriz como bloques de color de todo el ancho | Insignias pequeñas | Streamlit no colorea celdas sin CSS por celda | ✔ Aceptada |
| V-017 | AD2 | Tarea sin negrita; el enlace al catálogo azul y subrayado | Negrita; botón de texto negro | Se quitó la negrita. El enlace queda como botón (`type="tertiary"`) | ◐ Negrita corregida, sin commit; enlace ☐ |
| V-018 | AD3 | P1 azul, P2 ámbar y P3 verde; estado a la derecha; «No cumple» rojo; insignia ámbar de datos de ejemplo con «Configurar piloto» a su derecha; tarjeta blanca de borde fino | Todo gris, estado junto a la prioridad, «No cumple» ámbar, nota como texto y tarjeta con borde grueso | `PRIORITY_COLOR`, `horizontal_alignment="distribute"`, `not_met` en rojo, `st.badge` y fila propia, clave `card-metric-` | ◐ Corregido, sin commit |
| V-019 | AD3 | 4 columnas de tarjetas | 3 columnas | Regla de `app/CLAUDE.md`: máximo 3 columnas | ✔ Aceptada |
| V-020 | D2, D2d | Bloom como insignia (Comprender gris, Aplicar azul, Analizar ámbar); «Corregido» ámbar y «Agregado por ti» violeta, también en el grafo; acciones a la derecha; resumen de revisión en una tarjeta con insignia verde | Bloom en texto; «Corregido» azul y «Agregado» verde; acciones debajo; resumen suelto | `BLOOM_COLOR` (Recordar y Comprender gris, Aplicar azul, Analizar, Evaluar y Crear ámbar: Figma solo pinta tres niveles), `TOPIC_REVIEW_BADGE` y colores de `topic_graph.py`, tarjeta `card-review-summary` | ◐ Corregido, sin commit |
| V-021 | D4 | Acciones a la derecha y «Reiniciar intentos» como principal; perfil y nivel en dos tarjetas lado a lado; nivel con barra y porcentaje | Acciones debajo; una tarjeta bajo la otra; nivel con insignia | `render_page_header_with_actions`, dos columnas `card-learner-*` y `render_level_bars` (E4 sigue con insignias) | ◐ Corregido, sin commit |
| V-022 | D5 | «Recursos (3)» y «Preguntas (12)» como contadores bajo el título; sin negrita; «Anotar preguntas con la rúbrica» como principal | Subtítulos sueltos y negrita | `st.badge` en una fila; botón `primary` | ◐ Corregido, sin commit |
| V-023 | AD5 | «Inscribir aprendiz» como principal; grupo del piloto y consentimiento como insignias (Personalizada azul, Ruta fija violeta, Aceptado verde, Pendiente ámbar); «Sin asignar» en gris; nota final en aviso ámbar | «Crear curso» principal, texto plano, negrita | `PILOT_ARM_BADGE`, `CONSENT_BADGE`, `:gray[…]`, `render_notice` | ◐ Corregido, sin commit |
| V-024 | AD4 | Cuatro tarjetas en dos filas; grupos del sorteo en cajas azul y violeta; la insignia junto al título; nota de la d de Cohen en aviso ámbar | Todo en una columna, sin tarjetas | Columnas con `card-pilot-*`, `pilot-arm-*` en `layout.css`, `render_notice` | ◐ Corregido, sin commit |
| V-025 | D2, D5, AD4, AD5 | Acciones que la app no tiene o elementos de más: D2 abre el tema al hacer clic en la fila; AD5 ofrece «Editar · Desactivar» por curso; AD4 no muestra el campo de la semilla; el botón principal de AD4 y D5 es azul o violeta | Selector «Tema a editar»; «Cambiar instructor»; campo de semilla visible; botón del color del rol | Streamlit no hace clic en filas; la API no tiene desactivar curso desde AD5; la semilla se necesita para sortear; el color del botón sigue al rol (`app/CLAUDE.md`) | ✔ Aceptada |

Pendiente: E2 a E15 (después del PR 5), D5b a D5f, A3, A6, A7 y U1x. Revisadas: E1, E6, D1, D2, D3, D4, D5, AD1, AD2, AD3, AD4 y AD5.
