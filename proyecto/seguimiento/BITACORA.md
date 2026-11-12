# Bitácora

Registro cronológico de todo lo que se hace. **Solo se agregan entradas al final**; si algo estaba mal, se agrega una entrada nueva que lo corrige. Hora de Bogotá (-05).

Tipos: `INICIO`, `CAMBIO`, `COMMIT`, `PRUEBA`, `BUG`, `CORRECCIÓN`, `FIGMA`, `SUBIDA`, `DECISIÓN`, `NOTA`.

## Plantilla

```markdown
### AAAA-MM-DD HH:MM · TIPO · ID

Qué se hizo o qué se encontró, en una o dos líneas.
- Rama: `<rama>` · Commit: `<hash>` (si aplica)
- Archivos: `<ruta>`, `<ruta>`
- Resultado / evidencia: <comando y resultado, enlace>
```

## Entradas

### 2026-11-12 13:30 · NOTA · —

Descarga del repositorio en este equipo (`/home/vboxuser1/Documents/Pro/Smart`), rama `dev` en `d8de841` (fusión del PR 3).

### 2026-11-12 13:40 · BUG · B-001

El arreglo del PR 4 (`448e154`, bloqueo API ↔ `ai/`) no está en `dev`: se fusionó en `fix/conteos-y-tablero` cuando esa rama ya había entrado a `dev`.
- Evidencia: `git merge-base --is-ancestor origin/fix/bloqueo-trabajos-ia origin/dev` responde que no.

### 2026-11-12 13:50 · BUG · B-002

`proyecto/checklist.md`, `HANDOFF.md`, `app/README.md` y `CHANGELOG.md` describen un estado anterior al real.

### 2026-11-12 13:55 · FIGMA · F-001 a F-011

Revisión del archivo de Figma en vivo frente a `design/03-prototipo-alta-fidelidad/v3/estructura-pantallas.json`: las 96 pantallas coinciden por nombre. Se registran los 4 estados que Figma no dibuja y las 6 contradicciones ya conocidas.

### 2026-11-12 13:57 · INICIO · T-001

Rama `feature/seguimiento-trazabilidad` desde `dev` (`d8de841`) para crear `proyecto/seguimiento/`.

### 2026-11-12 14:05 · CAMBIO · T-001

Se crean `README.md`, `HOJA_DE_RUTA.md`, `BITACORA.md`, `BUGS.md`, `FIGMA.md`, `SUBIDAS.md` y `MEJORAS.md` en `proyecto/seguimiento/`. Falta el commit y la subida (los aprueba el dueño).
- Rama: `feature/seguimiento-trazabilidad` · Sin commit todavía
- Pruebas: no aplican (solo documentación)

### 2026-11-12 14:00 · COMMIT · T-001

Commit de la carpeta de seguimiento.
- Rama: `feature/seguimiento-trazabilidad` · Commit: `ee2ee75`

### 2026-11-12 14:01 · CORRECCIÓN · —

La entrada «2026-11-12 14:05 · CAMBIO · T-001» tiene una hora estimada a mano que quedó adelantada. Los archivos se crearon entre las 13:57 y las 14:00 (la hora del commit `ee2ee75`). Desde ahora, toda hora sale de `TZ=America/Bogota date` o de la hora del commit.

### 2026-11-12 14:01 · INICIO · T-002 · B-001

Rama `fix/bloqueo-trabajos-ia-a-dev` desde `origin/dev` (`d8de841`).

### 2026-11-12 14:01 · CORRECCIÓN · B-001

`git cherry-pick -x 448e154` → `0699da7`, sin conflictos. Conserva como autora a Alexander Amador y el mensaje original, con la referencia «cherry picked from».
- Rama: `fix/bloqueo-trabajos-ia-a-dev` · Commit: `0699da7`
- Archivos: `api/app/domains/content/{ingestion,repository_impl}.py`, `api/app/domains/courses/repository_impl.py`, `api/app/domains/learning_paths/repository_impl.py` y 3 archivos de pruebas de integración
- Evidencia: el `patch-id --stable` coincide con el del original (`21f67f3`), y ninguno de los 7 archivos cambió en `dev` desde la base del PR 4

### 2026-11-12 14:01 · PRUEBA · B-001

Sin correr: `api/scripts/dev.sh all` necesita Docker y PostgreSQL, y el dueño todavía no autoriza ejecutar el proyecto. Según su descripción, el PR 4 pasó sus pruebas en su rama original.

### 2026-11-12 14:0x (aprox.) · NOTA · —

Indicación del dueño: los cambios se van haciendo sin commits hasta que él lo pida. Tampoco se levanta el servidor ni se ejecuta el proyecto.

### 2026-11-12 14:0x (aprox.) · INICIO · T-012

D4 (detalle del aprendiz) esperaba la forma de los fixtures y no la respuesta real de `GET /learning-paths/{id}/learners/{enrollment_id}`: faltaban la ruta, el nombre de los temas en niveles e intentos y los pasos agotados.

### 2026-11-12 14:11 · CAMBIO · T-012

Se sigue el patrón del PR 3: cambio aditivo en la API y un adaptador en la app.
- API: `LearnerDetailResponse.learning_path` (`DashboardPath`: id, nombre, grupo y estado). No se quita ni se renombra ningún campo.
- Contrato: `docs/contracts/openapi-api.json` actualizado con el mismo formato de `app.core.openapi.render` (claves ordenadas, sangría 2). Antes de editarlo se comprobó que el archivo se reescribe idéntico; la prueba `test_openapi_contract.py` lo debe confirmar. `api-v2.md` también se actualizó. Postman no cambia: no guarda las respuestas.
- App: `clients/learner_detail_adapter.py` (nuevo). Da el nombre del tema a los niveles y los intentos, toma los pasos `attempts_exhausted` como intentos agotados (con un tope igual a la regla más los intentos extra), y separa los temas en espera (`on_hold`) de aquellos con los que se puede seguir (`pending` e `in_progress`). Solo lista los intentos entregados. Un código desconocido se omite en lugar de romper la pantalla.
- `LearnerDetail` suma `education_level`, `experience_band` y `job_title`, todos opcionales, así que los fixtures siguen sirviendo. La página arma el perfil con las etiquetas de `components/theme.py`, y solo muestra «Hoja de vida» si llega el dato (la API no la manda).
- Pruebas nuevas: `app/tests/unit/test_learner_detail_adapter.py`, con 7 pruebas y una muestra validada contra el OpenAPI. Además, `api/tests/integration/learning/test_staff_and_ownership.py` verifica `learning_path`.
- Archivos: `api/app/domains/learning_paths/{schemas,controller}.py`, `api/tests/integration/learning/test_staff_and_ownership.py`, `docs/contracts/{openapi-api.json,api-v2.md}`, `app/src/clients/{learner_detail_adapter,ops_staff,models_staff}.py`, `app/src/pages/instructor/learner_detail.py` y `app/tests/unit/test_learner_detail_adapter.py`
- Limitación conocida: la API no dice qué tema espera a cuál. Si hay más de un paso agotado, cada uno muestra todos los temas en espera.

### 2026-11-12 14:11 · PRUEBA · T-012

Sin correr (no autorizado). Revisión manual: sintaxis, largo de línea (100), orden de importaciones y tipos para mypy estricto. Pendiente: `app/scripts/dev.sh all` y `api/scripts/dev.sh all`.

### 2026-11-12 14:13 · INICIO · T-013

D5b (anotación ciega) esperaba la forma de los fixtures. La API devuelve `Page[QueueItem]` sin el nombre del tema, sin el puesto del evaluador y sin cuántos ítems ya anotó.

### 2026-11-12 14:16 · CAMBIO · T-013

Se sigue el patrón del PR 3 (como `GradingQueuePage`).
- API (aditivo): `QueueItem.topic_name`, `QueueItem.evaluator_slot` (el puesto propio si ya anotó, si no el primero libre, y `None` si los dos están ocupados) y la página `AnnotationQueuePage` con `annotated`. El servicio suma `annotated_count` y `_slot_for`; `AnnotationQueueEntry` gana dos campos con valor por defecto, así que nada de lo que ya lo construye cambia. Solo usa métodos que ya tenían los repositorios.
- Contrato: `openapi-api.json` (se quita `Page_QueueItem_`, que nadie más usaba, y entra `AnnotationQueuePage`) y `api-v2.md`.
- App: `annotation_queue_from_api` en `clients/evaluation_adapter.py`. Calcula «X de Y anotadas» (anotados + pendientes), acepta opciones como texto o como objeto con `text`, y no ofrece ítems sin puesto libre o ya anotados. `get_annotation_queue` lo usa; los fixtures pasan sin cambios.
- Pruebas: `app/tests/unit/test_annotation_adapter.py` (5, con la muestra validada contra el OpenAPI), una prueba unitaria del servicio en `api/tests/unit/evaluation/test_evaluation_service.py` y comprobaciones nuevas en `api/tests/integration/evaluation/test_evaluation_api.py`.
- Decisión: mostrar el puesto («Evaluador 2 de 2») le revela al segundo evaluador que alguien ya anotó, pero no qué anotó. Figma lo dibuja así (D5b) y la anotación sigue siendo ciega en el contenido.

### 2026-11-12 14:16 · PRUEBA · T-013

Sin correr (no autorizado). Revisión manual de sintaxis, largo de línea e importaciones. Pendiente: `app/scripts/dev.sh all` y `api/scripts/dev.sh all`, incluida la prueba de deriva del OpenAPI (`test_the_published_openapi_matches_the_code`).

### 2026-11-12 14:17 · INICIO · T-014

Revisión de D5f (calidad de los videos) frente a `GET /learning-paths/{id}/video-quality`.

### 2026-11-12 14:18 · FIGMA · F-012

D5f pide datos que el sistema no recoge (calificación promedio, efecto en el quiz, reportes, índice con 6 pesos, estado por umbrales y comentarios agrupados con IA). La API solo tiene etiquetas, vistas completas e índice bayesiano. No se codifica nada hasta que el dueño decida; T-014 queda ⛔.

### 2026-11-12 14:1x (aprox., entre 14:18 y 14:22) · DECISIÓN · F-012 · T-014

El dueño elige «Ajustar a la API»: D5f muestra lo que de verdad se mide y no se amplía el modelo de datos.

### 2026-11-12 14:22 · CAMBIO · T-014

- API (aditivo): `VideoQualityItem.status` (`measuring`, `recommended` ≥ 0,75, `observation` ≥ 0,60, `under_review`) con `quality_status()` y las constantes `VIDEO_QUALITY_RECOMMENDED` y `VIDEO_QUALITY_OBSERVATION`. También `VideoQualityResponse.min_ratings` (hoy 5, `VIDEO_QUALITY_MIN_RATINGS`). Los umbrales de Figma se aplican al índice bayesiano del ADR 0016. El estado lo decide la API, no la interfaz.
- Contrato: `openapi-api.json` y `api-v2.md`.
- App: `video_quality_from_api` en `clients/evaluation_adapter.py`:
  - índice × 100;
  - `useful_rate` (campo nuevo y opcional de `VideoQualityRow`);
  - vista completa = vistas completas / calificaciones;
  - reportes = calificaciones que no dicen «útil»;
  - etiquetas de queja ordenadas por frecuencia;
  - calificación de 1 a 5, efecto en el quiz y comentarios vacíos.
- Página D5f: muestra «X % útil · n notas» cuando no hay nota de 1 a 5, traduce las etiquetas con `VIDEO_RATING_LABEL` y solo menciona los comentarios si los hay. El texto de ayuda ya no describe el índice de 6 pesos, que no existe. Los fixtures y la prueba de la pantalla (`test_d5f_quality_table_and_decision`) siguen valiendo.
- Pruebas: `app/tests/unit/test_video_quality_adapter.py` (5, con la muestra validada contra el OpenAPI), `test_the_video_status_follows_the_d5f_thresholds` y una comprobación más en `test_content_service.py`, más `status` y `min_ratings` en `test_content_api.py`.
- Nota: Figma dice «10 o más calificaciones»; la API usa 5 (ADR 0016). La pantalla ahora muestra el número que manda la API.

### 2026-11-12 14:22 · PRUEBA · T-014

Sin correr (no autorizado). Revisión manual de sintaxis, largo de línea e importaciones.

### 2026-11-12 14:22 · INICIO · T-015

Comparación estática (con `ast` y el OpenAPI, sin ejecutar el proyecto) de los modelos del administrador contra las respuestas de la API. Hay diferencias en AD1, AD2, AD3, AD4, AD4b y AD5. T-015 se divide en T-015a a T-015f para hacer una pantalla a la vez.

### 2026-11-12 14:2x (aprox., entre 14:22 y 14:27) · BUG · B-003, B-004, B-005

AD1: activar y desactivar mandaban un campo que la API rechaza (422), el alta mandaba `roles` (422) y la lista solo traía los usuarios activos y sin roles.

### 2026-11-12 14:27 · CORRECCIÓN · T-015a · B-003 · B-004 · B-005

Sin cambiar la API, solo con rutas que ya existen:
- `list_users` pide los activos y después los inactivos (`active=true` y `false`) y une los roles con `/roles` y `/user-roles` (todas las páginas, de 100 en 100). Solo usa los roles que la interfaz conoce, en su orden.
- `create_user` hace el alta con nombre y correo y luego `PUT /users/{id}/roles`.
- `set_user_active` usa `/activate` y `/deactivate` y lee los roles con `GET /users/{id}/roles`.
- Archivos: `app/src/clients/ops_staff.py` y `app/src/clients/admin_adapter.py` (nuevo).

### 2026-11-12 14:27 · CAMBIO · T-015b

AD2: `llm_log_from_api` suma los tokens de entrada y salida, y lo vacío queda como texto vacío o 0 (una llamada fallida no rompe la tabla). `llm_summary_from_api` convierte las latencias p50 y p95 a milisegundos enteros. Una llamada sin fecha no se muestra. La página traduce la tarea con `AI_TASK_LABEL` (nuevo en `components/theme.py`, sacado de `prompts/catalog.yaml`) y muestra «—» si falta el modelo o el prompt.

### 2026-11-12 14:27 · PRUEBA · T-015a · T-015b

Sin correr (no autorizado). `app/tests/unit/test_admin_adapter.py`: 8 pruebas con muestras validadas contra el OpenAPI, entre ellas la del cuerpo del alta y las rutas de activación.

### 2026-11-12 14:28 · INICIO · T-015d

AD4 y AD4b frente a `/pilots`: el id del piloto estaba fijo en 1, y la respuesta no traía la ruta, los consentimientos ni los temas con ítems. La vista previa traía `topic_id` como texto, sin nombre y sin el umbral de la final.

### 2026-11-12 14:33 · CAMBIO · T-015d · B-006

- API (aditivo):
  - `PathSummary` y `PilotPopulation.path_summary()` (SQL sobre `learning_paths`: nombre, grupo y umbral de la final);
  - `PilotResponse.learning_path` (`PathRef`);
  - `ReadinessResponse` con `consents_accepted`, `consents_total`, `topics_total` y `topics_with_items`, calculados en `_readiness` con los datos que ya leía;
  - la vista previa suma el `name` de cada paso y `final_pass_threshold`.
- Pruebas de la API: la implementación en memoria de `test_pilot_service.py` suma `path_summary`, y hay comprobaciones nuevas de la ruta, los conteos y la vista previa. En `test_pilot_api.py`, la prueba que comparaba la respuesta de `readiness` completa (`== {"ready": True, "missing": []}`) se cambió para no romperse con los campos nuevos.
- Contrato: `openapi-api.json` (se reutiliza el esquema `PathRef`) y `api-v2.md` (también se documenta `GET /pilots`).
- App:
  - `find_pilot_id()` en el contrato y en los dos clientes: la API real abre el piloto más reciente que no cerró, y los fixtures el 1;
  - `pilot_from_api` (sin sorteo no hay grupos) y `fixed_path_preview_from_api` en `clients/admin_adapter.py`;
  - la página usa el id encontrado y avisa si no hay ninguno (F-013);
  - se quita `DEFAULT_PILOT_ID` de `core/staff_state.py`.
- Nota: «temas con ítems equivalentes» es lo que la API mide hoy (temas con preguntas en el banco). No compara el diagnóstico con la final.

### 2026-11-12 14:33 · FIGMA · F-013

AD4 no tiene un estado «sin piloto». Se muestra un aviso; crear el piloto desde la pantalla queda para que decida el dueño.

### 2026-11-12 14:33 · PRUEBA · T-015d

Sin correr (no autorizado). 7 pruebas nuevas en `app/tests/unit/test_admin_adapter.py`, con las muestras validadas contra el OpenAPI.

### 2026-11-12 14:3x (aprox.) · NOTA · —

A pedido del dueño se revisa `docs/`. Hasta ahora solo se habían usado `docs/contracts/openapi-api.json` y `api-v2.md`. Se leen la Definition of Done, los ADR 0016 y 0017 y `docs/evaluation/metrics.md`. T-012 a T-015 coinciden con ellos, salvo B-007 y F-014.

### 2026-11-12 14:3x (aprox.) · BUG · B-007 · FIGMA · F-014

El conteo de ítems equivalentes de T-015d no seguía `metrics.md`, y el texto de Figma (diagnóstico ↔ final) tampoco coincide con el modelo de datos (final ↔ retención). El dueño pide corregirlo.

### 2026-11-12 14:38 · CORRECCIÓN · B-007 · F-014

- API (aditivo): `ContentFacts.topics_without_equivalents` (SQL: temas sin un `equivalence_group` con dos o más ítems activos de `final` o `retention`) y `ReadinessResponse.topics_with_equivalent_items`. `topics_with_items` se mantiene (sirve para `item_bank`). No se agrega como requisito para iniciar el piloto: eso lo decide el dueño.
- Contrato: `openapi-api.json` y `api-v2.md`.
- App: `pilot_from_api` usa `topics_with_equivalent_items`. El texto de AD4 dice «versiones paralelas de la evaluación final y la prueba de retención». `READINESS_TEXT["item_bank"]` ya no dice «ítems equivalentes»: ahora dice «El banco de preguntas (quiz, diagnóstico o final) está incompleto».
- Pruebas: `test_pilot_service.py` (un caso sin versiones paralelas da 0), `test_pilot_api.py` (los bancos simulados de `fake_results.py` usan un grupo distinto por ítem, así que no tienen versiones paralelas: solo se comprueba que el conteo no pase del total) y `test_admin_adapter.py`.

### 2026-11-12 14:38 · PRUEBA · B-007

Sin correr (no autorizado).

### 2026-11-12 14:38 · INICIO · T-015e

AD5 frente a `/enrollments` y `/courses?mine=false`.

### 2026-11-12 14:42 · CAMBIO · T-015e · B-008

- API (aditivo): `AdminEnrollmentResponse.full_name` y `pilot_consent`. `EnrollmentService.learner_facts()` usa lo que `PlatformReader` ya tenía (`user`, `consent_in_force`), sin puertos nuevos. `_admin` pasa a ser asíncrono y se usa en las cuatro rutas de AD5.
- Contrato: `openapi-api.json` y `api-v2.md`.
- App: `admin_enrollment_from_api` y `admin_enrollments_page_from_api` (un brazo desconocido se muestra vacío). Alta, retiro y movimiento usan el mismo adaptador. `Course.owner_user_id` es nuevo y opcional, y AD5 busca el nombre del dueño entre los usuarios que ya carga; si no lo encuentra, muestra «Usuario N».
- Pruebas: 3 nuevas en `test_admin_adapter.py` (muestra validada contra el OpenAPI) y la comprobación de `full_name` y `pilot_consent` en `test_admin_enrollments_list_withdraw_and_move`.

### 2026-11-12 14:42 · PRUEBA · T-015e

Sin correr (no autorizado).

### 2026-11-12 14:51 · INICIO · T-015c

AD3 frente a `/metrics/evaluation`: la API manda unos 12 valores sueltos sin meta ni estado, y la pantalla muestra 29 métricas, cada una con su meta y su estado.

### 2026-11-12 14:5x (aprox.) · DECISIÓN · T-015c

Al dueño se le preguntó dónde van las metas y el estado. Respuesta: **en la API** (ADR 0017: las reglas van en la API).

### 2026-11-12 14:56 · CAMBIO · T-015c

- API: `app/domains/observability/catalog.py` (nuevo).
  - Tablas `SYSTEM`, `LEARNERS` y `OTHERS` con las 29 métricas de AD3 (código, nombre, prioridad, unidad, meta y comprobación); las metas salen de `docs/evaluation/metrics.md`.
  - `measured()` saca de `EvaluationMetrics` el valor y la muestra de las 12 que ya se calculan: F1, % válidas, κ, fidelidad, P@3, QWK, latencia p95, JSON inválido, costo, aprobación al primer intento, intentos y nDCG@3.
  - Las demás salen `no_data` con «Todavía no se calcula en la API (notebook o piloto)».
- `GET /metrics/evaluation` suma `groups` a lo que ya devolvía (aditivo). La respuesta sigue siendo un `dict` sin esquema, así que `openapi-api.json` no cambia; `api-v2.md` sí.
- Cambio de nombre: la m11 de Figma era «Costo por aprendiz-ruta». La API solo suma el costo del periodo, así que se llama «Costo del LLM» y el costo por aprendiz-ruta queda para el notebook.
- App:
  - `metrics_from_api` en `clients/admin_adapter.py`, que solo usa `groups` y no inventa una cohorte;
  - `metric_text()` en `services/staff_admin.py`, que da formato al número según la unidad (% con un decimal si es menor que 10, s, US$, min);
  - la página AD3 ya no escribe «cohorte 2026-2» a mano: la muestra si el dato llega.
- Pruebas: `api/tests/unit/observability/test_metric_catalog.py` (4), comprobaciones del catálogo en `test_observability_api.py` y 3 pruebas en `app/tests/unit/test_admin_adapter.py`.

### 2026-11-12 14:56 · PRUEBA · T-015c

Sin correr (no autorizado).

### 2026-11-12 14:59 · CAMBIO · —

A pedido del dueño, `HOJA_DE_RUTA.md` suma la sección «Estado por fase (F0 a F11)». Para cada fase da el estado, la evidencia, lo que falta y las tareas que le tocan. Los 9 commits de evidencia del tablero del plan (`eb84c97`, `726fc16`, `e709dd4`, `3e23ac3`, `f81d49d`, `37f44e8`, `995dbd9`, `9000895`, `97ffd44`) se comprobaron en `origin/dev`. El tablero del plan y `checklist.md` siguen desactualizados (B-002).

### 2026-11-12 15:01 · SUBIDA · S-001

`git push -u origin feature/seguimiento-trazabilidad`: 5 commits sobre `dev`. Detalle en [SUBIDAS.md](SUBIDAS.md). La CI arrancó (corrida `43296141612`).

### 2026-11-12 15:02 · CAMBIO · —

Estados actualizados a «⬆ Subido (sin PR)» (nuevo en la leyenda) y registro de S-001.

### 2026-11-12 15:20 · PRUEBA · —

El dueño pide las pruebas antes del PR. En este equipo no hay Docker ni `uv`, así que se usa la CI de la rama. La primera corrida después de S-001 falló en Ruff (lint) en api y app y en los enlaces de docs. Todos los errores eran de esta sesión.

### 2026-11-12 15:31 · PRUEBA · T-012 a T-015, B-001 a B-008

Después de 4 correcciones (S-002), **la CI está en verde**: API con 660 pruebas, app con 621 y ai con 463, más Ruff, formato y mypy estricto en las tres. Las 2 fallas que hubo en las pruebas eran reales y se corrigieron: AD3 había perdido el texto de la cohorte que pide Figma, y el OpenAPI publicado no tenía la descripción nueva de un endpoint.

### 2026-11-12 15:31 · BUG · B-009

pip-audit encuentra 41 vulnerabilidades en `certifi` y `pillow` (api y app). Ya fallaba en `dev`; se corrige en otra rama.
