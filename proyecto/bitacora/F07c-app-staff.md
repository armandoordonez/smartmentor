# Bitácora F07c · `feature/app-v3-staff`

Fase 7, parte 3: páginas del instructor y del administrador. Rama creada desde `origin/dev` (con
`origin/dev` fusionado de nuevo tras el corte por límite de uso).

## Hecho

- Cliente: `clients/models_staff.py` (modelos), `clients/ops_staff_contract.py` (Protocol
  `StaffOps`), `clients/ops_staff.py` (`StaffApiOps` HTTP y `StaffFixturesOps` de fixtures) y 48 JSON
  en `app/tests/fixtures/staff/`. Registro con una línea en `base.py` (el Protocol hereda `StaffOps`),
  `api.py` (hereda `StaffApiOps` y suma `_multipart` para el PDF) y `fixtures.py` (hereda
  `StaffFixturesOps`).
- Núcleo nuevo (archivos propios): `core/staff_state.py` (curso, ruta, inscripción y tema elegidos;
  claves de idempotencia), `core/staff_errors.py` (mensajes de los códigos del instructor y el admin),
  `components/staff_theme.py` (textos y colores de estado), `services/staff_*.py`.
- Instructor: D1 `courses`, D1b/D1c/D1d `new_course`, D2/D2b/D2c/D2d `syllabus_review`, D3/D3b
  `path_dashboard`, D4/D4b/D4c `learner_detail`, D5/D5d `content_review`, D5b `item_annotation`,
  D5c `short_answer_grading`, D5e `topic_videos`, D5f `video_quality`.
- Administrador: AD1 `users`, AD2 `llm_logs`, AD3 `metrics`, AD4/AD4b `pilot`, AD5
  `courses_enrollments`, C4 `prompt_catalog` (catálogo copiado de `prompts/catalog.yaml` en
  `services/staff_prompts.py`).
- Commits en la rama: `5a613da` (cliente), `13f4dd1` (D1 a D2d), `64aa9a2` (D3 a D5f), `5675502`
  (AD1 a AD3) y `e35d0f7` (AD4, AD4b, AD5, C4).
- Pruebas: `tests/unit/test_staff_client.py`, `tests/ui/test_staff_{courses,syllabus,dashboard,content}.py`,
  ayudas en `tests/staff_support.py`.

## Desviaciones frente al plan o al brief

- Las ventanas de Figma (D2b, D2c, D3b, D4c, D5d) se dibujan como paneles bajo el contenido, no como
  `st.dialog`: son más simples de probar con `AppTest` y no cambian el flujo.
- D5 muestra «Recursos (n)» y «Banco de preguntas del tema» una bajo otra (como Figma) y no con
  pestañas.
- La acción de cada fila («Editar · Regenerar») son botones separados, no un solo texto.
- Los KPI usan `st.metric` (etiqueta arriba, valor abajo); `AppTest` no los lee, se prueban aparte.
- D5f «Guardar decisión»: el contrato no trae una ruta para la decisión; «Reemplazar por el video de
  respaldo» y «Retirar» envían `PATCH /video-candidates/{id}` con `status=rejected` (la API promueve el
  respaldo); «Mantener y volver a medir» no llama a la API.
- D2: el contrato no define el cálculo de «N de M temas revisados»; se muestra
  `unchanged + corrected + added` de los temas activos.
- Alertas del instructor (`GET /alerts`, `PATCH /alerts/{id}/read`): no tienen pantalla propia en
  Figma ni en la lista de este agente; quedan sin construir (el tablero lo trae `unread_alerts`).

## Decisiones

- Modelos propuestos (el contrato no los fija, sección 8): `Course`, `Dashboard`, `LearnerDetail`,
  `Resource`, `VideoQuality`, `AnnotationQueue`, `GradingQueue`, `LlmCallLog`, `MetricsEvaluation`,
  `Pilot`, `FixedPathPreview`, `AdminEnrollment`. Ver `models_staff.py`.
- Escenarios de fixtures para pruebas: `StaffFixturesOps.staff_scenario` (`default`, `empty`,
  `forbidden`, `error`, `loading`, `failed`, `no_text`, `cycle`, `pilot_running`, `last_admin`...).
  `<doc>__<escenario>.json` reemplaza a `<doc>.json`. No se agregaron al selector A1.
- Estado de carga D1c: fragmento con `run_every="2s"`; mientras el trabajo no termina vuelve a
  ejecutar la página. Un trabajo fallido ofrece reintentar (`POST /courses/{id}/extractions`).
- La detección de ciclos del grafo (D2d) es solo de presentación; la API valida al guardar y publicar.
- El piloto no se lista en el contrato: la página usa el id 1 (`DEFAULT_PILOT_ID`).
- Los tests de `test_pages.py` y `test_api_mode.py` que suponían «Próximamente» para el instructor se
  actualizaron: ahora su inicio es «Mis cursos».

## Problemas y lecciones

- Los comandos Bash con heredocs largos los rechaza el aislamiento del worktree: se usó `Write` y
  scripts pequeños.
- `st.fragment(run_every)` se ejecuta una vez al cargar: con `AppTest` el trabajo de los fixtures
  termina de inmediato; la prueba de progreso usa el escenario `loading`.
- Un control con `default=None` y un fixture sin estado provoca bucles de ejecución: se recuerda lo ya
  enviado en `st.session_state`.
- En `missing_in_order` un texto de un solo carácter («6») coincide con cualquier cadena y desordena
  el resto: `assert_matches_figma` de `staff_support` acepta `ignore`.

## Métricas

- `ruff check` y `ruff format --check`: limpios. `mypy` estricto: sin errores (a `src/`).
- `pytest` de `app`: 399 pasan en unos 37 s (274 de la base + las de `dev` + 125 de esta parte:
  fixtures contra los modelos, cliente HTTP con `respx`, una prueba `AppTest` por página y escenario).
- Comparación con `estructura-pantallas.json` (`assert_matches_figma`): D1, D2, D3, D4, D4b, D5, D5e,
  AD1, AD2 y AD3, con las diferencias aceptadas declaradas en cada prueba (botones separados, KPI de
  `st.metric`, `▶`, nombres de tema abreviados, el nombre del usuario que va en la barra superior).
- Tamaño: unas 2.700 líneas de páginas, 2.000 de cliente/servicios/núcleo y 1.050 de pruebas; 49
  JSON de fixtures.
- Contenedor desechable (imagen uv, repositorio montado, `APP_DATA_SOURCE=fixtures`): la app arranca y
  `/_stcore/health` responde 200 `ok`; el contenedor se eliminó.

## Qué falta

- Revisión visual en un navegador (no hay capturas ni Figma) y del color del botón por rol.
- Alertas del instructor (`GET /alerts`, `PATCH /alerts/{id}/read`) sin pantalla.
- Filtros del log del LLM (`task`, `model`, `prompt_id`) y edición/desactivación de cursos en AD5:
  el contrato lista rutas (`PATCH /courses/{id}`) pero no el archivado; solo se asigna instructor.
- Importar CSV de usuarios (botón deshabilitado: sin ruta en el contrato).
- Los escenarios de `staff/` no están en el selector A1; se eligen en las pruebas.
- Verificar con la API real (Fase 6) las formas propuestas de `Course`, `Dashboard`, etc.

## Impacto en el brief

- Sección de pantallas del instructor: D5f no tiene ruta de decisión en el contrato.

## Cambios pedidos a archivos compartidos

- `app/README.md` y `app/CLAUDE.md` (agente `app-core`): marcar como hechas las páginas D1 a D5f,
  AD1 a AD5 y C4 en la tabla «Pantallas, roles y endpoints», y listar `ops_staff*.py`,
  `models_staff.py`, `core/staff_*.py`, `services/staff_*.py` y `components/staff_theme.py`.
- `core/navigation.py`: sin cambios (las páginas se registran por existencia del archivo).
