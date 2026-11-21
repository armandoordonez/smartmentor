# Bitácora F07b · `feature/app-v3-learner`

Fase 7, parte 2: páginas del aprendiz (E3 a E14, U1x). Rama creada desde `origin/dev`, con `origin/dev` fusionado (Authlib en `streamlit[auth]`).

## Hecho

- 12 páginas en `app/src/pages/learner/`: `diagnostic` (E3, U1a), `diagnostic_result` (E4, E4b), `path` (E5, E5b), `topic` (E6), `quiz` (E6b, E6c, U1b, U1c), `quiz_result` (E7, E7b, E7c), `final_assessment` (E8, U1d), `final_result` (E9, E9c), `badge` (E10 y verificación pública), `achievements` (E12), `progress` (E11, E11b), `final_survey` (E13a, E13b) y `retention_test` (E14, P2). Metas y racha dentro de E11.
- Clientes: `clients/ops_learner.py` (operaciones nuevas, mezclas para HTTP y fixtures, escenarios), `clients/models_learner.py`; 53 JSON en `tests/fixtures/learner/`.
- `core/`: `learner_state.py`, `learner_flow.py` (inscripción actual, navegación por `next_action`, espera de trabajos con `st.fragment(run_every)`), `question_flow.py` (preguntas de una en una con guardado parcial).
- Componentes nuevos: `path_rows.py`, `stat_tiles.py`. Servicios: `learning.py`, `content.py`.
- 13 escenarios de fixtures (`learner_diagnostic`, `learner_calculating`, `learner_calculating_error`, `learner_objective`, `learner_path`, `learner_fixed_path`, `learner_quiz_failed`, `learner_exhausted`, `learner_final_ready`, `learner_final_failed`, `learner_final_exhausted`, `learner_completed`, `learner_badge`, `learner_offline`), visibles en el selector A1.
- Commits publicados en la rama (último: `cc7d036`).

## Desviaciones frente al plan o al brief

- El contrato `api-v2.md` no tiene: historial de intentos, metas de estudio ni racha. Se proponen `GET /me/enrollments/{id}/steps/{id}/attempts` y `…/final/attempts` (`AttemptSummary`) y `GET`/`PUT /me/study-goals` (`StudyGoals`). Un 404 en las metas oculta la sección.
- `AssessmentItem` gana tres campos opcionales propuestos: `topic_name`, `bloom_level` y `rubric_summary` (E3, E6b, E6c). La rúbrica visible no llega de otra forma.
- La explicación alterna de E7b se lee de `StepContent.explanation` cuando su `resource_id` es `remedial_resource_id`; el contrato no dice cómo se obtiene.
- `FixturesClient` repite como eco el `next_action` de un trabajo terminado y del objetivo guardado (sin esto, las páginas rebotan entre sí con un `next_action` fijo). Sin reglas de negocio.
- «Intentos por tema» (E11) es el promedio de `attempts_used` de los temas con intentos (Figma: 1,5; el fixture da 1,0).
- Los pasos de las pantallas U1x se estiman con el estado del trabajo (la API solo da `progress_label`).

## Decisiones

- Cada página parte de la inscripción actual y solo redirige con `next_action`; E4, E5, E10, E11 y E12 se pueden abrir desde el menú sin guardia.
- Un trabajo fallido muestra «Tu avance está guardado» con Reintentar (vuelve a pedir con una clave de idempotencia nueva) y Volver a mi ruta; nunca descarta lo respondido.
- E4b y E11b van en línea (no hay modal en Streamlit); «Compartir» muestra la dirección pública de verificación.
- Diferencias aceptadas con Figma (declaradas en las pruebas): nombre de curso completo en vez de «Fundamentos de ML», índice de calidad del video, composición del quiz (4 + 1), «de Regresión logística» del prerrequisito, «último puntaje» (se muestra el mejor), botones «Demo» y notas «Prototipo», `placeholder` de los campos (AppTest no los lee), ícono ★ y botón de descarga.

## Problemas y lecciones

- La ejecución anterior se cortó por el límite de uso antes de escribir código.
- `AppTest.run()` repite la página original: tras una navegación hay que usar `at.switch_page(...)`.
- Con un `next_action` fijo en fixtures, `redirect_unless` entraba en un ciclo entre páginas (resuelto con el eco).
- `st.error` y `st.warning` no entran en `page_texts`; se prueban con `at.error` y `at.warning`.
- Los comandos Bash con heredocs o variables calculadas los rechaza el aislamiento: se usaron archivos y rutas literales.

## Métricas

- `pytest` de `app`: 429 pasan (274 de la base, 155 nuevas) en unos 36 s. Ruff y `ruff format`: limpios. `mypy` estricto: 0 errores en 71 archivos.
- Comparación con `estructura-pantallas.json` (`assert_matches_figma`-equivalente): E3, E4, E5, E5b, E6, E6b, E7b, E8, E9, E9c, E10, E11, E13a, E13b, U1a, U1b y U1c con solo las diferencias aceptadas arriba.
- Contenedor desechable en modo fixtures (`uv run streamlit run`): `/_stcore/health` responde `ok` (HTTP 200); contenedor eliminado.

## Impacto en el brief

- Sección de funcionalidades del aprendiz: agregar historial de intentos, metas y racha como rutas propuestas.
- Sección de privacidad: «Salir del piloto» y «Revocar y borrar mis datos» quedan en Mi progreso.

## Cambios pedidos a archivos compartidos

- `docs/contracts/api-v2.md`: agregar las rutas propuestas (historial de intentos, metas) y los campos `topic_name`, `bloom_level`, `rubric_summary` de los ítems.
- `clients/models.py`, `clients/base.py`, `clients/api.py`, `clients/fixtures.py`, `core/session.py`, `tests/ui/test_pages.py`: cambios mínimos (tres campos del ítem; el Protocol y las clases heredan las mezclas; el campo `learner`; la prueba de E1 ya navega al tema).

## Qué falta

- Comparación con Figma de E4b, E7, E7c, E12 y E14 (sin prueba de texto por diferencias de datos).
- Revisión visual en navegador y del CSS de las tarjetas nuevas (`card-objective`, `card-final`, `card-alternate`, `card-next-attempt`, `card-survey`, `card-retention`, `kpi-*`), que reutilizan estilos genéricos.
- Dos dudas de producto: cómo elige el aprendiz el tema de la prueba de retención (se usa el último paso) y de dónde sale la disponibilidad de E14 (hoy, inscripción `completed`).
