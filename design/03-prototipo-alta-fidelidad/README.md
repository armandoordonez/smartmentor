# 3. Prototipo navegable de alta fidelidad

Actividad 3 de la Fase 0, actualizada a la **v3** en la Fase 1 del [plan de implementación](../../PLAN_IMPLEMENTACION_V3.md). Resultado esperado: **enlace clicable para pruebas**.

## Enlaces

- **Figma (diseño):** archivo `atp2fZdSolEoaww3n9jRLg` («SmartMentor · Prototipo Fase 0 v3 (4)», página `0:1`, que en Figma sigue llamándose «SmartMentor v2»). Cada nodo del inventario abre su pantalla.
- **Especificación sin conexión a Figma:** [`v3/`](v3/README.md) trae los textos, el diseño automático, los enlaces entre pantallas y las 24 variables de color, extraídos de la exportación del 2026-10-20. [`v3/pantallas.md`](v3/pantallas.md) es el inventario generado con tamaño, captura, componentes y navegación de cada frame; [`v3/tokens.json`](v3/tokens.json) y [`v3/variables.json`](v3/variables.json) tienen los tokens.
- **Streamlit:** la app de [`app/`](../../app/README.md) es el prototipo de la Fase 0 (v2). Las páginas nuevas de la columna «Página propuesta» se construyen en la Fase 7.

> [`index.html`](index.html) incrusta un archivo de Figma con otra clave (`5oCXyjG1qaqc4XJNnDd8bN`). Antes de la prueba de usabilidad hay que confirmar con el dueño cuál es el enlace maestro; este README usa la clave del plan.

## Cómo leer el inventario

- **Prefijos:** A acceso, E aprendiz, D instructor, AD administrador, U estados de carga, C4 documentación.
- **Variantes por curso:** E2c–g, E2bc–bg, E3c–g, E4c–g, E5c–g y U1ac–ag (35 frames) repiten la plantilla de su pantalla base con el contenido de otro curso. No se listan; están en [`v3/pantallas.md`](v3/pantallas.md).
- **Prioridades:** P0 es necesaria para el hito de punta a punta del brief; P1 es necesaria para el piloto completo; P2 se recorta si el tiempo aprieta (sección 6.2 del plan). «P0 si hay control» depende de que el piloto tenga grupo de ruta fija.
- **Casos de uso:** el detalle está en [`casos-de-uso.md`](../01-flujo-y-casos-de-uso/casos-de-uso.md).
- **Botones «(Demo del prototipo)» y avances de 2 segundos:** no se construyen (sección 2.5 del plan).

Resumen de la lista de abajo: 50 pantallas P0 (incluidas las de «P0 / P1» y «P0 si hay control»), 10 P1 y 4 P2.

## Puntos de inicio del modo presentación

| Flujo | Primera pantalla | Uso en la prueba de usabilidad |
| --- | --- | --- |
| Selector de rol | A1 | Demo general |
| Login aprendiz | A2 | Tareas del aprendiz |
| Registro y consentimiento | A3 | Tarea de consentimiento |
| Login instructor | A4 | Tareas del instructor |
| Catálogo | E1 | Retomar una tarea sin pasar por el login |
| Mis cursos | D1 | Retomar una tarea del instructor |
| Usuarios y roles | AD1 | Tareas del administrador |
| Sesión expirada | A7 | Solo demo |

## Inventario de pantallas

| Código | Nodo de Figma | Pantalla | Rol | Página propuesta en `app/src/pages/` | Caso de uso | Prioridad |
| --- | --- | --- | --- | --- | --- | --- |
| A1 | [`2:169`](https://www.figma.com/design/atp2fZdSolEoaww3n9jRLg/?node-id=2-169) | Selector de rol | Todos | `common/demo_role_selector.py` (solo con `APP_DATA_SOURCE=fixtures`) | CU-01 | P2 |
| A2 | [`2:201`](https://www.figma.com/design/atp2fZdSolEoaww3n9jRLg/?node-id=2-201) | Login aprendiz | Aprendiz | Keycloak (`st.login`) | CU-01 | P0 |
| A3 | [`2:225`](https://www.figma.com/design/atp2fZdSolEoaww3n9jRLg/?node-id=2-225) | Registro aprendiz | Aprendiz | Keycloak; las dos casillas, en `common/consent.py` | CU-17, CU-34 | P0 |
| A3b | [`103:725`](https://www.figma.com/design/atp2fZdSolEoaww3n9jRLg/?node-id=103-725) | Consentimiento informado | Aprendiz | `common/consent.py` | CU-17, CU-34 | P0 |
| A3c | [`121:903`](https://www.figma.com/design/atp2fZdSolEoaww3n9jRLg/?node-id=121-903) | Tus datos y tus derechos | Aprendiz | `common/data_rights.py` | CU-17 | P0 |
| A4 | [`2:251`](https://www.figma.com/design/atp2fZdSolEoaww3n9jRLg/?node-id=2-251) | Login instructor | Instructor | Keycloak | CU-01 | P0 |
| A5 | [`2:275`](https://www.figma.com/design/atp2fZdSolEoaww3n9jRLg/?node-id=2-275) | Recuperar contraseña | Todos | Keycloak | CU-01 | P0 |
| A6 | [`2:290`](https://www.figma.com/design/atp2fZdSolEoaww3n9jRLg/?node-id=2-290) | 403 Sin permiso | Todos | `main.py` + `core/errors.py` | CU-01 | P0 |
| A7 | [`8:2`](https://www.figma.com/design/atp2fZdSolEoaww3n9jRLg/?node-id=8-2) | Sesión expirada | Todos | `main.py` + `core/errors.py` | CU-01 | P0 |
| E1 | [`5:2`](https://www.figma.com/design/atp2fZdSolEoaww3n9jRLg/?node-id=5-2) | Catálogo de rutas | Aprendiz | `learner/catalog.py` | CU-02 | P0 |
| E2 | [`5:37`](https://www.figma.com/design/atp2fZdSolEoaww3n9jRLg/?node-id=5-37) | Perfil | Aprendiz | `learner/onboarding_profile.py` | CU-03 | P0 |
| E2b | [`123:935`](https://www.figma.com/design/atp2fZdSolEoaww3n9jRLg/?node-id=123-935) | Hoja de vida | Aprendiz | `learner/onboarding_resume.py` | CU-18 | P1 |
| E3 | [`5:61`](https://www.figma.com/design/atp2fZdSolEoaww3n9jRLg/?node-id=5-61) | Diagnóstico | Aprendiz | `learner/diagnostic.py` | CU-04 | P0 |
| U1a | [`94:417`](https://www.figma.com/design/atp2fZdSolEoaww3n9jRLg/?node-id=94-417) | Calculando tu nivel | Aprendiz | `render_loading_steps` en `learner/diagnostic.py` | CU-04 | P0 |
| E4 | [`5:97`](https://www.figma.com/design/atp2fZdSolEoaww3n9jRLg/?node-id=5-97) | Resultado y objetivo | Aprendiz | `learner/diagnostic_result.py` | CU-04, CU-05 | P0 |
| E4b | [`94:536`](https://www.figma.com/design/atp2fZdSolEoaww3n9jRLg/?node-id=94-536) | Editar objetivo (modal) | Aprendiz | `objective_editor` en `diagnostic_result.py` | CU-05 | P0 |
| E5 | [`5:148`](https://www.figma.com/design/atp2fZdSolEoaww3n9jRLg/?node-id=5-148) | Vista de ruta | Aprendiz | `learner/path.py` | CU-06 | P0 |
| E5b | [`96:657`](https://www.figma.com/design/atp2fZdSolEoaww3n9jRLg/?node-id=96-657) | Ruta fija (grupo de comparación) | Aprendiz | `learner/path.py` (variante) | CU-06 | P0 si hay control |
| E6 | [`5:209`](https://www.figma.com/design/atp2fZdSolEoaww3n9jRLg/?node-id=5-209) | Tema (video, texto y calificación) | Aprendiz | `learner/topic.py` | CU-06, CU-20 | P0 / P1 |
| E6b | [`81:419`](https://www.figma.com/design/atp2fZdSolEoaww3n9jRLg/?node-id=81-419) | Quiz del tema | Aprendiz | `learner/quiz.py` | CU-06 | P0 |
| E6c | [`94:489`](https://www.figma.com/design/atp2fZdSolEoaww3n9jRLg/?node-id=94-489) | Respuesta corta | Aprendiz | `learner/quiz.py` | CU-06 | P0 |
| U1b | [`94:441`](https://www.figma.com/design/atp2fZdSolEoaww3n9jRLg/?node-id=94-441) | Preparando reintento | Aprendiz | `render_loading_steps` en `quiz.py` | CU-06 | P0 |
| U1c | [`94:465`](https://www.figma.com/design/atp2fZdSolEoaww3n9jRLg/?node-id=94-465) | Calificando | Aprendiz | `render_loading_steps` en `quiz.py` | CU-06 | P0 |
| E7 | [`5:245`](https://www.figma.com/design/atp2fZdSolEoaww3n9jRLg/?node-id=5-245) | Resultado del quiz | Aprendiz | `learner/quiz_result.py` | CU-06, CU-19 | P0 / P1 |
| E7b | [`69:373`](https://www.figma.com/design/atp2fZdSolEoaww3n9jRLg/?node-id=69-373) | Quiz no aprobado | Aprendiz | `learner/quiz_result.py` | CU-06 | P0 |
| E7c | [`94:607`](https://www.figma.com/design/atp2fZdSolEoaww3n9jRLg/?node-id=94-607) | Intentos agotados | Aprendiz | `learner/quiz_result.py` | CU-06 | P0 |
| E8 | [`3:348`](https://www.figma.com/design/atp2fZdSolEoaww3n9jRLg/?node-id=3-348) | Evaluación final | Aprendiz | `learner/final_assessment.py` | CU-07 | P0 |
| U1d | [`124:1271`](https://www.figma.com/design/atp2fZdSolEoaww3n9jRLg/?node-id=124-1271) | Calificando la final | Aprendiz | `render_loading_steps` en `final_assessment.py` | CU-07 | P0 |
| E9 | [`5:280`](https://www.figma.com/design/atp2fZdSolEoaww3n9jRLg/?node-id=5-280) | Repaso dirigido | Aprendiz | `learner/final_result.py` | CU-07 | P0 |
| E9c | [`103:769`](https://www.figma.com/design/atp2fZdSolEoaww3n9jRLg/?node-id=103-769) | Final con intentos agotados | Aprendiz | `learner/final_result.py` | CU-07 | P0 |
| E10 | [`5:311`](https://www.figma.com/design/atp2fZdSolEoaww3n9jRLg/?node-id=5-311) | Badge | Aprendiz | `learner/badge.py` | CU-08 | P0 |
| E11 | [`5:348`](https://www.figma.com/design/atp2fZdSolEoaww3n9jRLg/?node-id=5-348) | Mi progreso | Aprendiz | `learner/progress.py` | CU-08, CU-17, CU-23 | P1 |
| E11b | [`122:962`](https://www.figma.com/design/atp2fZdSolEoaww3n9jRLg/?node-id=122-962) | Gestionar autorizaciones (modal) | Aprendiz | `learner/progress.py` | CU-17 | P1 |
| E12 | [`5:382`](https://www.figma.com/design/atp2fZdSolEoaww3n9jRLg/?node-id=5-382) | Logros | Aprendiz | `learner/achievements.py` | CU-08 | P0 |
| E13a | [`94:674`](https://www.figma.com/design/atp2fZdSolEoaww3n9jRLg/?node-id=94-674) | Encuesta final (Likert) | Aprendiz | `learner/final_survey.py` | CU-21 | P0 |
| E13b | [`94:812`](https://www.figma.com/design/atp2fZdSolEoaww3n9jRLg/?node-id=94-812) | Encuesta final (SUS) | Aprendiz | `learner/final_survey.py` | CU-21 | P0 |
| E14 | [`104:935`](https://www.figma.com/design/atp2fZdSolEoaww3n9jRLg/?node-id=104-935) | Prueba de retención | Aprendiz | `learner/retention_test.py` | CU-22 | P2 |
| E15 | [`123:1031`](https://www.figma.com/design/atp2fZdSolEoaww3n9jRLg/?node-id=123-1031) | Mi perfil | Aprendiz | `learner/my_profile.py` | CU-18 | P1 |
| D1 | [`3:2`](https://www.figma.com/design/atp2fZdSolEoaww3n9jRLg/?node-id=3-2) | Mis cursos | Instructor | `instructor/courses.py` | CU-09 | P0 |
| D1b | [`95:538`](https://www.figma.com/design/atp2fZdSolEoaww3n9jRLg/?node-id=95-538) | Nuevo curso | Instructor | `instructor/new_course.py` | CU-09 | P0 |
| D1c | [`95:592`](https://www.figma.com/design/atp2fZdSolEoaww3n9jRLg/?node-id=95-592) | Extrayendo temas | Instructor | `render_loading_steps` en `new_course.py` | CU-09, CU-24 | P0 |
| D1d | [`95:618`](https://www.figma.com/design/atp2fZdSolEoaww3n9jRLg/?node-id=95-618) | Error al leer el syllabus | Instructor | `instructor/new_course.py` | CU-24 | P0 |
| D2 | [`6:2`](https://www.figma.com/design/atp2fZdSolEoaww3n9jRLg/?node-id=6-2) | Curso y syllabus | Instructor | `instructor/syllabus_review.py` | CU-10 | P0 |
| D2b | [`95:644`](https://www.figma.com/design/atp2fZdSolEoaww3n9jRLg/?node-id=95-644) | Editar tema | Instructor | `instructor/syllabus_review.py` | CU-10 | P0 |
| D2c | [`95:776`](https://www.figma.com/design/atp2fZdSolEoaww3n9jRLg/?node-id=95-776) | Confirmar volver a extraer | Instructor | `instructor/syllabus_review.py` | CU-25 | P1 |
| D2d | [`104:1102`](https://www.figma.com/design/atp2fZdSolEoaww3n9jRLg/?node-id=104-1102) | Grafo de temas | Instructor | `topic_graph` en `syllabus_review.py` | CU-10 | P0 |
| D3 | [`6:107`](https://www.figma.com/design/atp2fZdSolEoaww3n9jRLg/?node-id=6-107) | Ruta y avance | Instructor | `instructor/path_dashboard.py` | CU-12, CU-13 | P0 |
| D3b | [`95:883`](https://www.figma.com/design/atp2fZdSolEoaww3n9jRLg/?node-id=95-883) | Configurar la ruta | Instructor | `instructor/path_dashboard.py` | CU-12 | P0 |
| D4 | [`3:71`](https://www.figma.com/design/atp2fZdSolEoaww3n9jRLg/?node-id=3-71) | Detalle de aprendiz | Instructor | `instructor/learner_detail.py` | CU-13 | P1 |
| D4b | [`103:825`](https://www.figma.com/design/atp2fZdSolEoaww3n9jRLg/?node-id=103-825) | Intentos agotados | Instructor | `instructor/learner_detail.py` | CU-26 | P1 |
| D4c | [`103:940`](https://www.figma.com/design/atp2fZdSolEoaww3n9jRLg/?node-id=103-940) | Habilitar intentos | Instructor | `instructor/learner_detail.py` | CU-26 | P1 |
| D5 | [`8:13`](https://www.figma.com/design/atp2fZdSolEoaww3n9jRLg/?node-id=8-13) | Revisión de contenido | Instructor | `instructor/content_review.py` | CU-11 | P0 |
| D5b | [`96:850`](https://www.figma.com/design/atp2fZdSolEoaww3n9jRLg/?node-id=96-850) | Anotación de preguntas | Instructor o evaluador | `instructor/item_annotation.py` | CU-27 | P0 |
| D5c | [`96:1013`](https://www.figma.com/design/atp2fZdSolEoaww3n9jRLg/?node-id=96-1013) | Calificación humana | Instructor o evaluador | `instructor/short_answer_grading.py` | CU-28 | P0 |
| D5d | [`103:1058`](https://www.figma.com/design/atp2fZdSolEoaww3n9jRLg/?node-id=103-1058) | Editar recurso | Instructor | `instructor/content_review.py` | CU-11 | P0 |
| D5e | [`103:1193`](https://www.figma.com/design/atp2fZdSolEoaww3n9jRLg/?node-id=103-1193) | Video del tema | Instructor | `instructor/topic_videos.py` | CU-29 | P0 |
| D5f | [`124:1066`](https://www.figma.com/design/atp2fZdSolEoaww3n9jRLg/?node-id=124-1066) | Calidad de los videos | Instructor | `instructor/video_quality.py` | CU-30 | P2 |
| AD1 | [`3:174`](https://www.figma.com/design/atp2fZdSolEoaww3n9jRLg/?node-id=3-174) | Usuarios y roles | Administrador | `admin/users.py` | CU-14 | P0 |
| AD2 | [`3:262`](https://www.figma.com/design/atp2fZdSolEoaww3n9jRLg/?node-id=3-262) | Log LLM y costos | Administrador | `admin/llm_logs.py` | CU-15 | P0 |
| AD3 | [`8:133`](https://www.figma.com/design/atp2fZdSolEoaww3n9jRLg/?node-id=8-133) | Métricas globales | Administrador | `admin/metrics.py` | CU-16 | P1 |
| AD4 | [`96:1083`](https://www.figma.com/design/atp2fZdSolEoaww3n9jRLg/?node-id=96-1083) | Piloto | Administrador | `admin/pilot.py` | CU-32 | P0 si hay control |
| AD4b | [`110:885`](https://www.figma.com/design/atp2fZdSolEoaww3n9jRLg/?node-id=110-885) | Piloto · ruta fija (vista previa) | Administrador | `admin/pilot.py` | CU-32 | P0 si hay control |
| AD5 | [`103:1279`](https://www.figma.com/design/atp2fZdSolEoaww3n9jRLg/?node-id=103-1279) | Cursos, rutas e inscripciones | Administrador | `admin/courses_enrollments.py` | CU-31 | P1 |
| C4 | [`104:985`](https://www.figma.com/design/atp2fZdSolEoaww3n9jRLg/?node-id=104-985) | Catálogo de prompts | Administrador | `admin/prompt_catalog.py` | CU-33 | P2 |

Además: la **matriz de permisos** ([`2:3`](https://www.figma.com/design/atp2fZdSolEoaww3n9jRLg/?node-id=2-3)) y la **biblioteca de componentes** ([`24:2`](https://www.figma.com/design/atp2fZdSolEoaww3n9jRLg/?node-id=24-2)) con `Badge` (Verde, Azul, Ámbar, Gris, Violeta), `Botón` (Primario azul, verde y violeta, y Secundario), `Menú superior` (Aprendiz, Instructor, Admin), `Campo` y `Estado de carga` ([`94:407`](https://www.figma.com/design/atp2fZdSolEoaww3n9jRLg/?node-id=94-407)). El menú del aprendiz suma «Mi perfil».

## Lo que cambia frente a la v2

| Área | Cambio |
| --- | --- |
| Acceso | Consentimiento informado (A3b) y derechos (A3c); aviso de la Ley 1581; verificación en dos pasos del instructor |
| Perfil | Hoja de vida estructurada (E2b, E15) y pesos del nivel 80/10/10 |
| Diagnóstico | 15 preguntas, estados de carga (U1a), objetivo editable (E4b) y cortes con «Obligatorio» |
| Ruta | Motivo de cada paso, ruta fija del piloto (E5b), avance no lineal con intentos agotados (E7c) |
| Evaluación | Respuesta corta con rúbrica (E6c, E7), explicación alterna (E7b), final con intentos agotados (E9c), encuesta final y SUS (E13) |
| Instructor | Creación y extracción del curso (D1b–D1d), grafo (D2d), intentos extra (D4b, D4c), anotación ciega, calificación humana, video y calidad (D5b–D5f) |
| Administrador | Piloto (AD4, AD4b), cursos e inscripciones (AD5), catálogo de prompts (C4) |

## Ajustes pendientes antes de la prueba de usabilidad

Contradicciones del plan (sección 2.4) que afectan lo que ve el participante:

- [ ] Unificar los datos de ejemplo de Laura en Regresión logística (E5, D3 y D4 no coinciden) y de Julián Pérez (D3 dice «Abandonada» y D4b «En espera por intentos agotados») (C-14, C-15).
- [ ] Corregir la fecha del piloto en A3b (2 al 15 de noviembre de 2026 es incompatible con el estado del proyecto) (C-03).
- [ ] No mostrar el «calidad 81 de 100» del video antes de que el aprendiz califique (C-08).
- [ ] Revisar las marcas de terceros en los cursos de IA aplicada («Nuevo · Anthropic», «Nuevo · Google», «Claude Ventas») (C-01, DEF-04).
- [ ] Mostrar «Revisión» y no «Embedding» en D2b (C-16).
- [ ] Dibujar los estados que Figma no tiene: error de un trabajo de IA (U1x), catálogo vacío e instructor sin cursos (ver [`flujos.md`](../01-flujo-y-casos-de-uso/flujos.md#casos-de-error-de-las-pantallas-de-carga-u1x)).
- [ ] Dibujar el menú de perfil con cambio de rol (CU-35); Figma solo tiene el selector previo al login (A1).
- [ ] Confirmar `error/acento` (variable `118:923`) y que el archivo en vivo no cambió desde el 2026-10-20 (ver [`v3/README.md`](v3/README.md)).
