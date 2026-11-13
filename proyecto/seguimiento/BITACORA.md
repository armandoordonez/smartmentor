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

### 2026-11-12 16:51 · PRUEBA · T-012 a T-015

El dueño quiere probar los cambios antes del PR. Se levanta el stack local desde `feature/seguimiento-trazabilidad`: `.env` nuevo a partir de `.env.example` (ignorado por git; secretos de `scripts/gen-secrets.sh`) y `AI_SERVICE_MODE=fake` (IA simulada, sin Gemini). Corre `scripts/local-up.sh --no-ai --with-admin`. La primera vez la máquina virtual se quedó sin memoria (5,3 GB y sin swap) mientras construía las imágenes. Se terminó a mano: `docker compose up -d --no-build app` y `keycloak/scripts/seed-dev-users.sh --with-admin`. Los 5 contenedores quedaron sanos con unos 1 GB en total (Keycloak se lleva 730 MB). La app redirige al login de Keycloak. La prueba manual la hace el dueño.

### 2026-11-12 17:00 · CAMBIO · —

El dueño pasa su `.env` real y se reemplaza el local (ignorado por git; la copia anterior queda en el scratchpad de la sesión, fuera del repo). Cambia esto: la base es la compartida en **Neon** (también la de Keycloak), `AI_SERVICE_MODE=http` con **Gemini real** (topes de 5 USD al día y 30 al mes) y correo con Mailpit. La rama no trae migraciones (`git diff origin/dev -- database/` vacío), así que Liquibase no cambió el esquema de Neon. Primero se construyó la imagen `ai` sola, para no quedarse sin memoria, y después `scripts/local-up.sh --no-build --with-admin`. Quedan 6 contenedores sanos (app, api, ai, ai-worker, keycloak, mailpit), con unos 870 MB en total. Los usuarios de desarrollo ya existían en el Keycloak compartido: no se tocaron.

### 2026-11-12 17:25 · PRUEBA · T-012 a T-015

Prueba manual del dueño con la API real. AD1 (Usuarios y roles) y AD2 (Log LLM): sin problemas. D4 (Detalle de aprendiz): el nivel por tema salía en «670 %» → B-010. Creó el curso «curso claude code» desde un syllabus: D5 salía vacía hasta pulsar «Aprobar y publicar». **No es un bug:** `POST /courses/{id}/publish` es el que encola la generación de preguntas y recursos (`api/app/domains/courses/service.py`). Falta que la pantalla lo explique → M-006.

### 2026-11-12 17:30 · BUG · B-010

Corregido en `learner_detail_adapter.py`: el nivel se pasa de 0–100 a 0–1. La muestra de la prueba ahora usa la escala de la API y verifica el valor. `pytest tests/unit/test_learner_detail_adapter.py` y las pruebas de UI de D4: 11 en verde; Ruff y formato en verde.

### 2026-11-12 17:39 · CAMBIO · —

El dueño pide que la sesión dure 3 horas. El access token del realm duraba 5 min (`accessTokenLifespan: 300`) y la app no lo renueva, así que mostraba A7 «Tu sesión expiró». La sesión SSO se cerraba a los 30 min sin uso. En `keycloak/realm/smartmentor-realm.json` ambos pasan a 10 800 s (3 h); el máximo de la sesión SSO sigue en 10 h. Ese archivo solo se importa cuando el realm no existe, así que el Keycloak compartido no cambia hasta que se aplique a mano. **Costo:** un token robado vale 3 h en lugar de 5 min. Lo correcto a mediano plazo es que la app renueve el token con el refresh token.

### 2026-11-12 18:05 · CAMBIO · —

Sesión de 3 h aplicada en el Keycloak compartido (con aprobación del dueño): `accessTokenLifespan` 300 → 10 800. El realm tenía `ssoSessionIdleTimeout` en 108 000 (30 h, no los 1 800 del archivo del repo) y quedó en 10 800. Al intentar devolverlo a 108 000, el control de permisos bloqueó el comando dos veces. El dueño tiene el comando para hacerlo él. El máximo de la sesión sigue en 10 h.

### 2026-11-12 18:10 · CAMBIO · —

Nuevo `scripts/simulate-learners.py` (sin commit), a pedido del dueño: crea 4 aprendices en Keycloak (`aprendiz1` a `aprendiz4.smartmentor@yopmail.com`, con la contraseña `SEED_USERS_PASSWORD`; aciertan el 92, 78, 62 y 45 %) y recorre por la API cada ruta publicada, guiado por `next_action`. Las respuestas correctas se leen como administrador. Si un paso agota los intentos, el administrador habilita uno más.

### 2026-11-12 18:15 · PRUEBA · —

Prueba con el aprendiz 1 en MLOps (ruta 4). Diagnóstico, objetivo y 2 pasos aprobados; un tema se omitió por dominado. Se detiene en la final con `409 There are no unseen approved final items`. Causa: **ninguno de los 3 cursos publicados tiene preguntas de la final aprobadas**, y «Curso de Claude Code» (curso 5) no tiene nada aprobado, ni el diagnóstico. El diagnóstico de MLOps solo tiene 1 ítem aprobado, así que con una sola pregunta el nivel queda en 0 o 100. El dueño decide aprobar las preguntas en D5 como instructor. Después se corre el script con los 4 aprendices.

### 2026-11-12 18:40 · CAMBIO · —

El dueño pide que el token se renueve y que la sesión dure 3 h. Streamlit 1.65 solo expone los tokens `id` y `access` (`expose_tokens`), no el refresh token. Por eso la renovación repite `st.login` cuando el access token vence: mientras la sesión SSO de Keycloak siga viva, vuelve con un token nuevo sin pedir contraseña ni OTP. Para evitar un ciclo de redirecciones, solo se renueva si el token vencido se emitió hace más de 2 min (`should_renew_silently`, con 4 pruebas nuevas en `test_core.py`). Limitación: después de renovar, la app vuelve a su página de inicio (Streamlit redirige a la raíz). El texto de A7 pasa de «30 minutos» a «3 horas» (F-015).

Keycloak compartido: `accessTokenLifespan` 10 800 → 300 (token corto otra vez), `ssoSessionIdleTimeout` y `ssoSessionMaxLifespan` 10 800, y `clientSessionMaxLifespan` 18 000 → 10 800 (Keycloak no deja que supere el máximo de SSO). En `smartmentor-realm.json` quedan 300 y 10 800, y `ssoSessionMaxLifespan` 10 800.

### 2026-11-12 18:40 · CAMBIO · D5

A pedido del dueño, se aprueba en D5 como el instructor dueño (`PATCH /items/{id}` y `PATCH /resources/{id}/review`, lo mismo que hacen los botones) todo lo que estaba «Por revisar» en los cursos publicados. Los ítems `auto_rejected` no se tocan. Curso 2: 80 preguntas y 1 recurso. Curso 4: 93 preguntas. Curso 5: 244 preguntas y 8 recursos. Efecto: la tasa de aceptación de ítems (AD3) queda inflada por esta aprobación en bloque.

### 2026-11-12 18:40 · PRUEBA · —

Corre `scripts/simulate-learners.py` con los 4 aprendices en las rutas 2, 4 y 5. El resultado se anota al terminar. La máquina virtual se quedó sin memoria una vez durante la sesión (pytest en un contenedor más el stack): las pruebas se corren con el stack quieto.

### 2026-11-12 19:40 · PRUEBA · —

Simulación de los 4 aprendices en las rutas 2, 4 y 5. Valentina (92 %) obtuvo las 3 insignias. Andrés (78 %) obtuvo 2. Camila (62 %) y Julián (45 %) obtuvieron 1 cada uno. Todas las inscripciones que no terminaron se detuvieron en un reintento de la final por **B-011**. Hubo 2 errores más, que no son del producto: un `503 AI_SERVICE_UNAVAILABLE` momentáneo (la IA no respondió a una consulta y a la siguiente sí) y un `401` porque el script no renovaba el token de 5 min. El script ahora renueva el token y reintenta los 503.

### 2026-11-12 19:40 · BUG · B-011

Corregido con la opción que eligió el dueño, igual que el quiz. Si en un reintento quedan menos de 10 preguntas no vistas, o no queda ninguna, `start_final` pide `items.generate_final_bank` (una versión, 1 respuesta corta) y responde `202`. Las preguntas que pasan la revisión automática entran `approved`, marcadas `on_demand`. La llave del trabajo es `enrollment:<id>:attempt:<n>`: a lo sumo una generación por intento, así que no hay ciclo. Nuevo `FinalBankIngestor`: los bancos generados al publicar siguen yendo al ingestor de contenido.

En la app, E8 y el «Reintentar» de E9 muestran «Preparando preguntas nuevas para tu evaluación final» y después piden el intento con una clave nueva. OpenAPI regenerado y `api-v2.md` actualizado.

Pruebas:
- **app:** Ruff, formato y mypy en verde; **628 pruebas en verde** (3 nuevas para B-011, 4 de la renovación del token y 1 de B-010).
- **api:** Ruff, formato y mypy en verde; unitarias con 445 en verde y 2 que fallan solo en este equipo (`test_core.py` de la URL de la base: el `.env` real con `DATABASE_SSL=true` se cuela en la prueba; en la CI pasan).
- **api, integración:** sin correr aquí. `prepare-test-db` usaría el `.env`, que apunta a Neon. Hay una prueba nueva (`test_a_final_retake_without_unseen_items_answers_202_until_they_are_ingested`) y se ajustó la del flujo completo. Las corre la CI.

Se reconstruyó la imagen de la API para probar en vivo.

### 2026-11-12 20:06 · PRUEBA · B-011

Primera prueba en vivo de la corrección. Funcionó: Camila repitió la final de Extracción con preguntas nuevas y la aprobó (90 %). También salió un error propio: si las preguntas nuevas seguían siendo menos de 10, la API volvía a pedir el banco con la misma llave pero con otra entrada; `ai/` respondía 422 y la API lo devolvía como 503. Se corrigió así: las preguntas generadas guardan en `auto_review` para qué inscripción e intento se pidieron, no se vuelven a pedir para ese intento, y la llave incluye cuántas preguntas había. Se reconstruyó la API y se repitió la prueba sin errores: Andrés aprobó la final de Extracción (80 %), y Julián generó preguntas nuevas dos veces en MLOps.

**Resultado final de los 4 aprendices** (todos hicieron diagnóstico, objetivo, temas con reintentos y encuesta donde aprobaron):

| Aprendiz | Extracción | MLOps | Claude Code |
| --- | --- | --- | --- |
| Valentina (92 %) | Insignia | Insignia | Insignia |
| Andrés (78 %) | Insignia | Insignia | Insignia |
| Camila (62 %) | Insignia | Insignia | 3 intentos de la final usados, sin aprobar |
| Julián (45 %) | 3 intentos de la final usados, sin aprobar | 3 intentos de la final usados, sin aprobar | Insignia |

Los que agotaron la final quedan en `final_ready` con `next_action` `none` (E9c): el instructor puede darles intentos extra. Se reconstruyó también la imagen de la app (B-010, renovación del token y B-011).

### 2026-11-12 20:17 · SUBIDA · —

PR 6 abierto hacia `dev` (<https://github.com/armandoordonez/smartmentor/pull/6>), con la aprobación del dueño. Los estados «⬆ Subido (sin PR)» pasan a «🔼 PR 6 abierto».

### 2026-11-13 10:11 · SUBIDA · —

El PR 6 se fusionó en `dev` el 2026-11-12 21:11 (`42b14df`; GitHub lo registra a las 02:11 UTC del 13). T-001, T-002, T-012 a T-015e, B-001, B-003 a B-008, B-010 y B-011 quedan «✔ En `dev`». El trabajo sigue en la rama nueva `feature/hoja-de-ruta-f6-f7`, creada desde `dev` actualizado.

### 2026-11-13 10:18 · PRUEBA · T-010

Revisión del PR 5 (`fix/flujo-aprendiz`, de Alexander Amador, en borrador) a pedido del dueño, sin tocar su rama:

- **Fusión con `dev` actual** (ya con el PR 6): limpia, sin conflictos (`git merge-tree`). En una copia temporal de `dev` con el PR 5 fusionado, la app pasa Ruff, formato y mypy, y **730 pruebas en verde**. La copia ya se borró.
- **Su CI** está en verde, salvo los `audit` (B-009), pero corrió sobre la base vieja (`b91ab9c`).
- **Pendientes del PR que ya resolvió el PR 6:** el arreglo del PR 4 (503 al enviar el quiz, B-001), «Detalle del aprendiz» con la API real para dar intentos extra (T-012) y la renovación del token de 5 min.
- **Pendientes que siguen abiertos:**
  - ver en el navegador la calificación de una respuesta corta hasta «¡Tema aprobado!» y la evaluación final (por la API ya lo recorrió la simulación de 4 aprendices);
  - «Reintentar» para trabajos fallidos fuera del quiz;
  - el 401 durante el sondeo de trabajos, que ahora se debería resolver con la renovación silenciosa, pero hay que verificarlo.
- **Hallazgo que reporta y se confirma:** `api-v2.md` §7 dice que `GET /jobs/{id}` devuelve el `next_action` de la inscripción, pero la API nunca llena ese campo (`JobResponse.next_action` siempre es `null`) → **B-012**.
- **Forma:**
  - los 3 commits no tienen cuerpo ni el pie de coautoría que pide la plantilla;
  - la descripción del PR cierra con «Generated with Claude Code» y un enlace a una sesión, que la regla 19.4 del plan no permite.

Para sacarlo de borrador basta con actualizarlo con `dev`, hacer la verificación en el navegador que falta y ajustar la forma. Lo decide Alexander.

### 2026-11-13 10:19 · PRUEBA · T-030, T-032

Evidencia de F6 a partir del log del LLM (AD2, `GET /llm-call-logs/summary`): 354 llamadas a Gemini en las 10 tareas de `ai/`, por un total de US$ 1,83. No hubo ningún 429, así que T-030 queda resuelto. T-032 pasa a ◐: el recorrido de punta a punta se hizo por la API; falta hacerlo con el syllabus real y por la UI del aprendiz. El p95 de 120 s en las tareas de bancos de preguntas parece un límite de tiempo → M-007. La tabla está en la hoja de ruta.

### 2026-11-13 10:22 · PRUEBA · T-015f, T-016, T-017

- **T-017 ✔:** las pantallas del instructor que faltaban ya leen la API real. Con el cliente de la app (dentro del contenedor y con datos reales) se leyeron bien los temas, el grafo y el panel de la ruta de los cursos 2, 4 y 5, y Mis cursos (10 de 10). Crear un curso, subir el syllabus y publicar ya los probó el dueño en la UI. No se guardó la configuración de una ruta (D3b) para no cambiar los cursos compartidos.
- **T-015f ✔:** C4 no tiene ruta en la API; es una copia de `prompts/catalog.yaml` y coincide (13 prompts, versión 1 y los mismos nombres). Falta una prueba que avise si se desincronizan → M-008.
- **T-016 ◐:** E5b depende del PR 5.

No hubo cambios de código.

### 2026-11-13 10:31 · BUG · B-013

El dueño decide subir el timeout de las llamadas al LLM de 120 a 240 s (`ai_llm_timeout_seconds`). El lease de los trabajos (`ai_job_lock_seconds`) no se renueva mientras el trabajo corre, y una llamada se intenta hasta 3 veces (3 x 240 s = 720 s, más las esperas). Con el lease de 900 s, un trabajo lento se podía vencer y otro trabajador lo tomaría y lo correría dos veces. Por eso el lease pasa a 1800 s; eso solo retrasa la recuperación cuando un trabajador se cae. Los dos son ajustes internos con valor por defecto, sin variable en `.env.example` (`scripts/check-env-coherence.py`: coherente). Se actualizó `ai/README.md`.

Pruebas de `ai/`: Ruff y mypy en verde, 463 en verde y 10 omitidas (las de PostgreSQL). Se reconstruyó la imagen y se reiniciaron `ai` y `ai-worker`; dentro del contenedor, timeout 240.0 y lease 1800. El efecto se mide en la próxima generación de un curso, en el log del LLM (AD2).

### 2026-11-13 10:40 · CAMBIO · B-012, M-008, T-020, T-003

- **B-012:** `api-v2.md` §7 ahora dice lo que hace la API: `next_action` de `GET /jobs/{id}` siempre es `null` y la app vuelve a leer la inscripción. Sin cambios de código.
- **M-008:** prueba nueva `app/tests/unit/test_prompt_catalog_sync.py`, que compara C4 con `prompts/catalog.yaml` (lo lee con una expresión regular, porque la app no tiene PyYAML).
- **T-020:** las 6 pantallas de carga ya mostraban el error con «Reintentar» y «Volver». Faltaban pruebas para U1b y para preparar las preguntas de la final, y se agregaron. Al principio la de U1b falló, pero no era un bug: `AppTest` vuelve a la página de inicio cuando se navega con `switch_page`, así que la prueba ahora abre el quiz directamente.
- **T-003 (B-002):** en `proyecto/checklist.md` se marcaron 38 tareas, cada una con su evidencia, sin cambiar responsables: el avance pasa de 28 % a 60 %. También se actualizaron «Dónde estamos frente al cronograma» y la lectura del avance. `HANDOFF.md` quedó reescrito con el estado real (antes era del 2026-10-07). Se actualizaron la línea de estado de `app/README.md` y el CHANGELOG, con una sección del plan v3.

### 2026-11-13 10:46 · CAMBIO · T-020

El dueño aprueba el estado de error de las pantallas de carga tal como está: mensaje de error con el avance guardado, «Reintentar» y «Volver». F-001 queda ✔ y T-020 también.

### 2026-11-13 10:52 · PRUEBA · T-034

Empieza la revisión visual frente a Figma. Se levanta una segunda copia de la app con datos de ejemplo en el puerto 8502 (`.claude/launch.json`, configuración «app-fixtures-8502»); la del 8501 sigue con la API real. Se bajaron de Figma las capturas de E1, E5, D1 y AD1 (4 llamadas al MCP).

### 2026-11-13 10:52 · BUG · B-014

En E1 no había tarjetas ni barra superior. En el navegador, `--bg-surface` no estaba definida y en el documento no había ningún `<style>` propio, ni en la app de ejemplo ni en la real del 8501. Causa: los comentarios de `roles.css` (`role-<rol>`) y `layout.css` (`.st-key-<nombre>`). `st.html` manda el CSS al frontend, que lo sanea con DOMPurify, y DOMPurify descarta el `<style>` entero si su texto parece tener una etiqueta. Se cambió a `{rol}` y `{nombre}`. Prueba nueva `test_the_css_has_nothing_that_looks_like_an_html_tag`: falla sin el arreglo y pasa con él (78 en `test_styles.py`). Con el arreglo, `--bg-surface` vale `#ffffff` y las tarjetas son blancas. **La interfaz llevaba desde el 2026-11-07 sin sus estilos**; las pruebas no lo notaban porque `AppTest` no pasa por DOMPurify.

### 2026-11-13 10:52 · PRUEBA · T-034 (E1, D1, AD1)

Primera pasada de E1, D1 y AD1: 9 diferencias (V-001 a V-009, en `FIGMA.md`). E1 queda muy cerca de Figma. Las más visibles son de patrón y se repiten en muchas pantallas: los botones de la página debajo del título en lugar de a la derecha (V-002) y la barra superior que no va de lado a lado (V-001). V-006 (el color de «En revisión») lo decide el dueño.

### 2026-11-13 11:18 · CAMBIO · T-034, B-014

El dueño pide corregir V-001 a V-009, con «En revisión» en azul.

- **V-001 (barra superior):** primero se probó con `width: 100vw` y márgenes negativos, pero salía un scroll horizontal de 5 px, porque el contenedor con scroll de Streamlit descuenta la barra vertical. Queda con el fondo pintado por `box-shadow`, recortado con `clip-path`, y la línea inferior con `border-image-outset`. Ninguno de los dos cuenta para el scroll y no hace falta usar selectores internos. Verificado: de 0 a 1280 px y sin desborde, en E1, AD1 y Mi progreso.
- **V-002:** `render_page_header_with_actions` en `components/layout.py`, con título y subtítulo a la izquierda y un contenedor alineado a la derecha para las acciones. Se usa en D1 y AD1.
- **V-003, V-007:** sin negrita en la primera columna de D1 y AD1; D1 muestra el nombre del instructor como subtítulo.
- **V-004, V-005:** tablas blancas; nombre de la tarjeta de E1 en semibold, con un contenedor `path-title-{id}`.
- **V-006:** `in_review` pasa a `blue`.
- **V-008, V-009:** celdas nuevas en `render_table`: `Badges`, una insignia por rol con su color, y `PlainText`. Escapar `@` y `.` en Markdown no evitaba el enlace `mailto:`; con `st.text` ya no aparece. El ayudante `plain()` de las pruebas ahora quita los escapes de Markdown, porque compara con lo que se ve en pantalla.
- **Hallazgo nuevo, V-010:** los tamaños de `tokens.css` están en `rem`, y la raíz de Streamlit es de 14 px, así que todo sale un 12,5 % más pequeño que en Figma. No se tocó: cambia toda la interfaz.

Pruebas: Ruff, formato y mypy en verde; **632 en verde**. Tras el último cambio de CSS, `test_styles.py` y `test_components.py` pasan (101). Se reconstruyó la app real del 8501. Para ver los cambios de `components/` hay que reiniciar el servidor de revisión del 8502, porque Streamlit no vuelve a cargar los módulos importados.

### 2026-11-13 11:19 · CAMBIO · T-034

El dueño decide dejar los tamaños de letra como están (V-010): los tokens siguen en `rem`, con la base de 14 px de Streamlit. V-010 queda como diferencia aceptada.

### 2026-11-13 11:34 · PRUEBA · T-034 (E6, D3, AD2, AD3)

Segunda pasada, con 4 capturas más de Figma (8 llamadas en total).

- **E6:** 3 diferencias de distribución (V-011 a V-013). No se corrigen ahora, porque el PR 5 reescribe `topic.py`; se harán después de fusionarlo. V-014 queda aceptada.
- **D3 (V-015):** acciones a la derecha, sin negrita, «Omitido» violeta y «Abandonada» ámbar, valores de los temas críticos en rojo (qué tema es crítico lo dice la API: `critical_topic_ids`) y «Temas críticos» en un aviso ámbar. V-016 queda aceptada.
- **AD2 (V-017):** sin negrita en la primera columna.
- **AD3 (V-018):** colores de prioridad, estado a la derecha, «No cumple» rojo, insignia de datos de ejemplo y tarjeta blanca. La prueba frente a Figma detectó el orden equivocado de la insignia y el botón, y se corrigió. V-019 (3 columnas) queda aceptada por la regla de `app/CLAUDE.md`.

Pruebas: Ruff, formato y mypy en verde; **632 en verde**. Verificado en el navegador (D3 y AD3). Se reconstruyó la app real del 8501.

### 2026-11-13 12:37 · PRUEBA · T-034 (D2, D4, D5, AD4, AD5)

Tercera pasada, con 5 capturas más de Figma (13 llamadas en total). Los colores de D2d salieron de `estructura-pantallas.json`, sin otra llamada.

- **D2 y D2d (V-020):** Bloom como insignia de color, «Corregido» ámbar y «Agregado por ti» violeta en la tabla y en el grafo, acciones a la derecha y resumen en tarjeta.
- **D4 (V-021):** acciones a la derecha, perfil y nivel lado a lado, y nivel con barras. E4 no cambia.
- **D5 (V-022):** contadores como insignias, sin negrita y «Anotar preguntas» como botón principal.
- **AD4 (V-024):** cuatro tarjetas en dos filas y cajas de color para los grupos.
- **AD5 (V-023):** insignias de grupo y consentimiento, «Inscribir aprendiz» como principal y aviso ámbar.
- V-025 reúne lo que se acepta (clic en filas, acciones que la API no tiene, color del botón por rol).

Se actualizó la prueba del grafo (`test_components.py`), que esperaba el color anterior. Verificado en el navegador del 8502.

### 2026-11-13 13:35 · PRUEBA · T-034 (D5b a D5f, A6, A7)

Cuarta pasada, con 7 capturas más de Figma (20 llamadas en total). Los colores de D5f salieron de `estructura-pantallas.json`.

- **D5b (V-026):** barra de avance, pregunta en caja gris con la respuesta correcta en verde, criterios en una línea y nota ciega en violeta.
- **D5c (V-027):** respuesta y nota del LLM en dos columnas.
- **D5d (V-028):** fidelidad y versión en una línea, aviso ámbar y botones repartidos.
- **D5e (V-029):** candidatos y respaldo en dos tarjetas.
- **D5f (V-030):** índice en negrita, «En revisión» ámbar y dos tarjetas lado a lado.
- **A6:** coincide. **A7 (V-031):** tarjeta blanca con el botón a todo el ancho; también la usa la pantalla previa al login.
- V-032 reúne lo que se acepta (paneles laterales y ventanas, color por fila, color de las etiquetas).

Verificado en el navegador del 8502 (D5b, D5c, D5e y D5f). A7 no tiene escenario de demostración: se revisa con sus pruebas y con la pantalla previa al login del 8501.

### 2026-11-13 14:07 · PRUEBA · B-009 (Streamlit 1.66)

El dueño pide probar Streamlit 1.66 para poder subir `pillow` a 13. Con `streamlit[auth]>=1.66,<1.67` se resuelven Streamlit 1.66.1 y `pillow` 13.0.0, y `pip-audit` de `app/` queda sin vulnerabilidades. Ruff, formato y mypy en verde.

Falla 1 de 632 pruebas: `test_a3b_decision_travels_back_to_the_checkbox`. La causa, confirmada con un script mínimo en 1.65.0 y 1.66.1: en 1.66, si una ejecución termina en `st.stop()`, Streamlit no descarta el valor de los widgets con `key` que no se dibujaron. Al volver de A3b, la casilla del piloto trae su valor viejo y pisa la decisión. Hay 32 páginas con `st.stop()` y varias con pasos (consentimiento, nuevo curso, encuesta final, quiz y evaluación final), así que el cambio no se aplicó en el PR 7: se revirtió y la migración va en su propia rama, después del PR 5.

### 2026-11-13 14:33 · BUG · B-015 y B-016 (hoja de vida y redirecciones del aprendiz)

El dueño encontró dos fallas en la copia de revisión (8502): guardar la hoja de vida daba un `ValidationError` de Pydantic, y «Continuar» llevaba a otra página que lo devolvía.

- **B-015:** el perfil vive en la sesión; cuando Streamlit recarga `clients/models.py`, los `Language` del perfil son de la clase vieja y `ProfileUpdate` los rechaza. `services/profile.py` los rearma desde sus campos.
- **B-016:** la inscripción queda en `profiling` hasta que se guarda la descripción. La API real la mueve a `diagnosing` en `PUT /me/profile`, pero el cliente de ejemplo no lo hacía: E2b seguía el `next_action` (E2) y el diagnóstico devolvía al perfil. El cliente de ejemplo ahora hace esa transición, como el contrato, y E2 salta E2b si ya hay hoja de vida.
- **Revisión de las demás redirecciones:** solo tres páginas comprueban el `next_action` antes de mostrarse (E3, E4 y E8). E4 acepta editar el objetivo desde E5 y E8 acepta el reintento desde E9: no hay otro ciclo.

Pruebas: Ruff y mypy en verde; **635 en verde** (3 nuevas). Recorrido en el navegador: consentimiento → catálogo → E2 → E2b con inglés B1 → E3 sin rebote. Se reiniciaron la copia de revisión (8502) y la app real (8501).

### 2026-11-13 15:34 · BUG · B-017 y B-018 (aprendiz con la API real)

- **B-017:** con la API real, «Rutas» (E1) mostraba «El servicio no está disponible». La API respondía 200, pero `LearningPathCard` de la app no tenía la forma del OpenAPI (6 errores de validación). Viene de `6783086` y lo corrige el PR 5. Se probó el PR 5 sobre el PR 7 en una copia aparte (`prueba/pr5-sobre-pr7`, local, sin subir): 737 pruebas en verde y el modelo lee las 3 rutas reales. El 8501 corre esa copia; el dueño confirmó que el aprendiz carga.
- **B-018:** el diagnóstico tardaba de 3,6 a 5,5 s por clic. Medido en el log de la API: cada acción recargaba la página y pedía otra vez `GET /me/enrollments/14` y `GET …/diagnostic` (unos 1,8 s cada uno); «Siguiente» suma `PUT …/diagnostic/answers`. La lentitud de cada petición viene de unas 16 consultas seguidas a Neon (us-east-2, unos 110 ms de ida y vuelta). La hoja del diagnóstico va ahora en un `st.fragment` (`render_question_sheet(rerun_scope="fragment")`); entregar sí recarga la página. 60 pruebas del aprendiz en verde.

### 2026-11-13 15:53 · BUG · B-019 («No lo sé» del diagnóstico)

El dueño confirmó en el 8501 que elegir una respuesta ya no recarga la página (B-018), pero «No lo sé» parecía no hacer nada. Ahora guarda y avanza, y al volver a la pregunta se ve lo elegido. 60 pruebas del aprendiz en verde; en la copia de prueba (PR 5 sobre PR 7), 737. Al copiar la prueba a esa copia se borraron dos pruebas del PR 5; se detectó con `git diff` y se restauró antes de correr la suite.

### 2026-11-13 16:14 · BUG · B-020 y B-021 (objetivo del aprendiz)

- **B-020:** el 422 al confirmar el objetivo venía de `origin` en el cuerpo de `PUT /me/enrollments/{id}/objective` (`ObjectiveUpdate` rechaza campos de más). Se quitó, y el editor conserva un verbo propuesto que no está en la lista («Construir»). 39 pruebas nuevas o relacionadas en verde; en la copia de prueba, 739.
- **B-021:** «Editar el objetivo» dejó la página en «Conectando». Sin peticiones a la API después del clic y con el proceso de la app usando CPU sin parar; no se reproduce con datos de ejemplo ni en `AppTest`. No se pudo inspeccionar el proceso. Se reinició el 8501 con B-020 corregido para volver a probar.

### 2026-11-13 16:18 · PRUEBA · B-020 y B-021

El dueño confirmó en el 8501 que «Confirmar y ver mi ruta» y «Editar el objetivo» funcionan después del reinicio con B-020 corregido. B-021 queda en observación.

### 2026-11-13 16:35 · BUG · B-022 (recarga al elegir en el quiz)

El dueño vio en el quiz la misma recarga que tenía el diagnóstico. El arreglo de B-018 debió ir desde el principio en la hoja compartida y no en una sola página. Ahora `render_question_sheet` pone la hoja en su propio fragmento por defecto (quiz, final y retención) y el diagnóstico sigue con su fragmento completo. Se hizo en `core/question_flow.py`, que el PR 5 no toca, para no chocar con su reescritura de `quiz.py` y `final_assessment.py`. Pruebas: 637 en verde en la rama y 739 en la copia de prueba. 8501 reconstruido.

### 2026-11-13 16:49 · BUG · B-023 (el catálogo saltaba al quiz)

El dueño confirmó que el quiz ya no recarga la página al elegir (B-022). Encontró que «Ver ruta» siempre lo llevaba al quiz abierto. El catálogo ahora abre la ruta (E5) cuando la inscripción ya está en la ruta. 739 pruebas en verde en la copia de prueba; 8501 reconstruido.

### 2026-11-13 16:52 · PRUEBA · B-023

El dueño confirmó en el 8501 que «Ver ruta» del catálogo muestra la ruta (E5) con el quiz empezado.
