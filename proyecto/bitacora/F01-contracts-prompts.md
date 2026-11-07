# Bitácora F01 · Prompts y contratos (agente `contracts`, Ola 0)

Rama: `feature/prompts-and-contracts` (sale de `feature/baseline-dev`, `eb84c97`). Publicada en `origin` al cerrar cada bloque.
Fuentes: `PLAN_IMPLEMENTACION_V3.md` (secciones 3, 5.3, 5.4, 13, 15, 18.2, Anexos A y B, Fase 1 de la sección 7) y el notebook `design/04-prueba-mago-de-oz/smartmentor_mago_de_oz_gemini_v2.ipynb`, leído como JSON (44 celdas; no se ejecutó ni se editó; no contiene claves).

## Hecho

| Bloque | Qué | Commit |
| --- | --- | --- |
| 1 | `ai/` mínimo: `pyproject.toml` (Python 3.12, Pydantic v2, pytest, Ruff, mypy estricto), `uv.lock`, `app/domain/contracts/` (10 esquemas `…LLM` y 16 contratos, validaciones de código, grafo de prerrequisitos, registro) y `scripts/export_schemas.py` (idempotente, con `--check`). Esquemas exportados a `prompts/schemas/*.v1.json` y `prompts/schemas/llm/*.v1.json` | `9bc1da0` |
| 2 | 13 prompts `prompts/<id>/v1.md`, `prompts/catalog.yaml` con `sha256` por versión, `prompts/README.md`, 16 ejemplos por contrato y 13 por prompt (`prompts/examples/`), pruebas de contrato (`ai/tests/contract/`) y unitarias (`ai/tests/unit/`), `ai/README.md` | `50ac51c` |
| 3 | `docs/contracts/ai-service-v1.md`, `docs/contracts/api-v2.md`, `docs/contracts/error-codes.md` y esta bitácora | (commit del bloque 3) |

## Desviaciones frente al plan o al brief

| # | Plan o brief | Lo que se hizo | Motivo |
| --- | --- | --- | --- |
| DV-01 | Anexo B: el banco unificado va en `assessment_item.v1.json` | Dos contratos: `assessment_item.v1` (un ítem) y `assessment_item_bank.v1` (resultado de los trabajos de generación: ítems, revisiones y descartados) | Un trabajo devuelve un lote con su revisión automática; un solo ítem no alcanza para ingerirlo |
| DV-02 | Anexo B: `BadgeTextLLM` y `BadgeAssertion` en `badge.v1.json` | `badge_text.v1` (lo que devuelve `badge.compose_text`) y `badge.v1` (aserción Open Badges 2.0, la construye la API) | `ai/` solo redacta el texto (5.4.3); la aserción es de la API |
| DV-03 | Plan 5.4.3: `diagnostic.finalize` devuelve «niveles + objective» | Contrato propio `diagnostic_finalization.v1` | Para que el resultado del trabajo tenga un esquema verificable |
| DV-04 | Notebook: `simulated_student` | Id `simulated_learner` (con `source` que apunta al id original) | Sección 13.2 del plan lo pide explícitamente; los demás ids se conservan |
| DV-05 | Notebook: `course_id` (snake_case) en el syllabus | `course_key` | Evita confundirlo con `courses.id` (bigint) |
| DV-06 | Notebook: `approved_by_teacher` y `teacher_corrections` en `Syllabus`; `confirmed_by_student` en `Objective`; `enrollment_id` en varios contratos | Se quitan de los contratos | La revisión y la confirmación son estado de la API (`topics.review_status`, `PUT …/objective`); `ai/` recibe las referencias en `refs` del trabajo y no necesita ids de personas (DEF-05) |
| DV-07 | Notebook: `question_id`, `text` | `item_id`, `text_answer` | Alineado con `assessment_items` y `attempt_answers` del plan 5.2.1 |
| DV-08 | Notebook: aprobación de la respuesta corta con 60 de 100 | `grading.v1` con `approval_rule` y `min_criteria_ratio` (2/3 por defecto) | C-09 y DEF-21 del plan |
| DV-09 | Plan 5.4.5: `ai/scripts/dev.sh export-schemas` | `uv run python -m scripts.export_schemas` | No se pidió `dev.sh` en esta rama; el agente de `ai/` puede envolver el comando |

## Decisiones

| # | Decisión | Opciones | Motivo |
| --- | --- | --- | --- |
| DC-01 | Esquemas `…LLM` en `prompts/schemas/llm/` y contratos en `prompts/schemas/` | Un solo directorio con sufijo; solo contratos | El front matter apunta a ambos (`output_schema` y `contract`) y el `FakeLlmProvider` necesita el primero |
| DC-02 | Los esquemas `…LLM` son laxos (`extra="ignore"`, sin rangos ni uniones; centinelas `-1` y `""`); los contratos son estrictos (`extra="forbid"`, rangos, `null`) | Un solo modelo por salida | L-07 del plan: Gemini respeta peor uniones y rangos. Las funciones `item_from_llm`, `answer_from_llm`, `syllabus_from_llm`, `grading_from_llm`, `faithfulness_from_llm` convierten |
| DC-03 | Validaciones en dos lugares: invariantes intrínsecas como `model_validator` del contrato (DAG, forma del ítem, rango de citas, pesos que suman 1, clasificación coherente, rangos de videos) y comprobaciones con contexto en `validation.py` (`check_*` devuelven la lista de problemas para el reintento) | Todo en validadores de Pydantic | Las comprobaciones con contexto (ids que existen, rúbrica, número de fragmentos) no caben en el modelo, y la lista de problemas es lo que se le devuelve al LLM |
| DC-04 | `variables.data` y `variables.parameters` en el front matter; toda variable `data` va entre líneas `<<<` y `>>>` y una prueba lo verifica | Delimitar solo el syllabus | 5.4.12 pide delimitar syllabus, fuentes, respuestas y comentarios; delimitar todo lo que no controla el sistema es más simple de verificar |
| DC-05 | `version: 1` entero en el front matter y `meta.prompt_version = "v1"` | `v2.0` del notebook | Primera versión publicada por el repositorio (3.4 del plan) |
| DC-06 | `catalog.yaml` guarda el `sha256` de cada archivo y una prueba lo compara | Hash solo en CI | Así la regla «cambiar el texto obliga a subir la versión» ya se cumple en `pytest` |
| DC-07 | `final_assessment` pide `n_versions` versiones paralelas por ítem (`f<n>_v<k>`, `equivalence_group = eg_<n>`) y `check_final_coverage` exige grupos completos y homogéneos | Generar la retención en otra llamada | L-10 y AD4 piden ítems equivalentes; un solo prompt garantiza el paralelismo |
| DC-08 | Ids en los contratos como cadenas opacas: claves del LLM solo en `syllabus`; en lo demás, el id de la base como texto | Claves de extracción en todo | Los temas que agrega el instructor no tienen clave de extracción |
| DC-09 | `ai/` lee por referencia lo que su usuario de base puede leer (plan 5.2.4) y recibe en `input` lo demás | Todo en línea | Coherente con los permisos D-05; evita mandar el syllabus completo por HTTP |
| DC-10 | `type` de RFC 9457 = `https://smartmentor/errors/<código-en-guiones>` | Otra URI | Es la convención que ya usa `api/app/core/exceptions.py` |
| DC-11 | Ruff local en `ai/pyproject.toml` con las reglas de 14.2 | `extend = "../ruff.toml"` | `ruff.toml` no existe en esta rama (lo crea `feature/repo-standards`) |
| DC-12 | `pass_rule` se renombró a `approval_rule` | `# noqa: S105` | La regla `S` de Ruff lo confundía con una contraseña |
| DC-13 | Ejemplos redactados a mano sobre el curso y la aprendiz ficticia del notebook; los de contrato se derivaron de los de LLM con las funciones de conversión (generador temporal, no versionado) | Dejar ejemplos vacíos | El notebook nunca se ejecutó con el LLM (plan 3.1); los ejemplos son contratos, no evidencia |

## Problemas y lecciones

- El notebook no tiene salidas: los ejemplos no prueban calidad, solo forma. Las primeras salidas reales llegan con el arnés de evaluación (Fase 6).
- Ruff `S105/S106` marca cualquier nombre con «pass» (`pass_rule`); se evita con nombres neutros.
- mypy encontró `scripts/export_schemas.py` dos veces (como script y como módulo) hasta agregar `scripts/__init__.py`.
- Hay que montar la raíz del repositorio (no solo `ai/`) en el contenedor porque las pruebas leen `prompts/`; el `venv` se dejó en `/tmp/venv` del contenedor para no crear `.venv` en el árbol.
- El sandbox del agente no deja ejecutar comandos compuestos con variables que podrían ser `git`; se separaron en comandos simples.

## Métricas

| Métrica | Valor real |
| --- | --- |
| `ruff check` / `ruff format --check` | 0 errores / 27 archivos formateados |
| `mypy --strict` (plugin de Pydantic) | 0 errores en 26 archivos |
| `pytest` | 197 pruebas, 197 pasan (≈ 1,1 s; la corrida completa en contenedor ≈ 5,4 s con la caché de `uv`) |
| Idempotencia de `export_schemas` | Segunda corrida: «26 schemas, 0 updated»; `git diff --exit-code -- prompts/schemas` sin diferencias |
| JSON válidos | 55 de 55 archivos `.json` de `prompts/` con `python3 -I -m json.tool` |
| Esquemas | 26 (16 contratos + 10 `…LLM`), todos válidos como Draft 2020-12 |
| Prompts | 13 (`v1.md`, 509 líneas en total) |
| Ejemplos | 29 (16 de contrato + 13 de LLM), todos validan contra esquema, modelo y validaciones de código |
| Líneas | `ai/app` + `ai/scripts`: 1 724; `ai/tests`: 912; `docs/contracts`: 786 |
| Dependencias resueltas en `uv.lock` | 26 paquetes |

## Impacto en el brief

| Sección del brief | Cambio sugerido para el brief v2 |
| --- | --- |
| Componentes de IA 2 y 7 (diagnóstico y evaluaciones) | Decir que los ítems salen de un banco revisado (B-02) y que cada ítem declara el resultado de aprendizaje que evalúa (`outcome_id`) y, en la final y la retención, su grupo de equivalencia |
| Decisiones técnicas: «salidas estructuradas con esquemas» | Mencionar las dos capas (`…LLM` y contrato), las validaciones de código y el reintento con el error |
| Decisiones técnicas: «versionar los prompts como código» | Agregar el catálogo con hash por versión y la regla de no editar una versión publicada |
| Ética / datos personales | Agregar la regla de datos entre delimitadores (inyección de prompts) y el perfil seudonimizado |
| Vocabulario | Los prompts ya usan «aprendiz» e «instructor» (B-01) |
| Calificación de respuesta corta | Regla de aprobación por proporción de criterios (2/3), no por puntaje de 60 (C-09) |

## Cambios pedidos a archivos compartidos

| Archivo | Cambio | Para quién |
| --- | --- | --- |
| `ai/pyproject.toml` | Cuando exista `ruff.toml` en la raíz (rama `feature/repo-standards`), reemplazar el bloque `[tool.ruff]` por `extend = "../ruff.toml"` y dejar solo `per-file-ignores` | Sesión principal al integrar |
| `.gitignore` | Nada nuevo (ya ignora `.mypy_cache/`, `.ruff_cache/`, `.pytest_cache/`) | — |
| `docker-compose.yml`, `.env.example` | Sin cambios en esta rama. `ai-service-v1.md` asume `AI_PORT`, `AI_SERVICE_AUDIENCE`, `AI_*_BUDGET_USD` y `APP_CONTEXT_PROFILE`, que ya están en el Anexo D del plan | Agentes de infraestructura y de `ai/` |
| `api/app/core/exceptions.py` | Sin cambios; el catálogo reutiliza su forma de `type` y agrega códigos nuevos que la API debe crear en la Fase 3 | Agente de la API |
