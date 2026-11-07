# prompts/

Prompts versionados y esquemas JSON de cada salida de IA de SmartMentor. Es la fuente de verdad que leen `ai/` (para llamar al proveedor de LLM), la API (para validar lo que ingiere) y la app (para conocer la forma de los datos). Los prompts y los esquemas vienen del notebook del Mago de Oz v2 (`design/04-prueba-mago-de-oz/smartmentor_mago_de_oz_gemini_v2.ipynb`, que no se edita), adaptados al vocabulario `learner`/`instructor` (sección 13 del plan) y a los ajustes de la sección 3.4 del plan.

## Estructura

```text
prompts/
├── README.md
├── catalog.yaml                 # id, versión vigente, nombre en español, tarea, esquemas, pantallas, sha256
├── <id>/v1.md                   # un directorio por prompt, un archivo por versión
├── schemas/<contrato>.v1.json   # contratos que ai/ entrega a la API (16)
├── schemas/llm/<nombre>.v1.json # salida que se le pide al proveedor (10)
└── examples/
    ├── <contrato>.json          # una salida válida por contrato
    └── llm/<id>.json            # una respuesta válida del proveedor por prompt (base del FakeLlmProvider)
```

## Formato de un prompt

```markdown
---
id: topic_quiz                      # id en inglés, igual al del notebook v2
version: 1                          # coincide con el nombre del archivo (v1.md)
name_es: Banco del quiz del tema    # lo que muestran C4 y AD2
task: items.generate_quiz_bank      # job_type o tarea de ai/ (plan 5.4.3)
temperature: 0.6
model_tier: default                 # default → AI_LLM_MODEL_DEFAULT; small → AI_LLM_MODEL_SMALL
output_schema: llm/assessment_items_llm.v1.json
contract: assessment_item_bank.v1.json
variables:
  data: [topic, previous_items]     # texto del usuario o de terceros: siempre entre <<< y >>>
  parameters: [topic_id, n_multiple_choice, n_short_answer]  # valores que controla el sistema
source: smartmentor_mago_de_oz_gemini_v2.ipynb · topic_quiz v2.0
---

## system

…

## user

… {n_multiple_choice} …
<<<
{topic}
>>>
```

- Los marcadores son `{nombre}` y se rellenan con `str.format`. No hay otras llaves en el texto.
- El texto de los prompts está en español (es lo que leen los aprendices); ids, campos y valores enumerados, en inglés.

## Reglas

1. **Un archivo publicado no se edita.** Cambiar el texto obliga a crear `v<n+1>.md`, registrar su `sha256` en `catalog.yaml` y subir `current_version`. La prueba `ai/tests/contract/test_prompt_catalog.py` compara cada hash.
2. **Los datos del usuario son datos, no instrucciones** (plan 5.4.12). Toda variable de `variables.data` va en un bloque que empieza con una línea `<<<` y termina con una línea `>>>`, y cada `system` lo recuerda. Antes de rellenar, `ai/` elimina las secuencias `<<<` y `>>>` del texto recibido para que nadie pueda cerrar el bloque.
3. **Datos personales:** nunca se envían nombre, correo ni ids. El perfil va seudonimizado y la hoja de vida en categorías (DEF-05).
4. **Validación de la salida** (plan 5.4.4): el proveedor recibe `output_schema` como salida estructurada → `Model.model_validate_json` → la función `check_*` de `ai/app/domain/contracts/validation.py` → reintento con los problemas encontrados (máximo 2) → `invalid_output`.
5. **Vocabulario:** «aprendiz» e «instructor»; nunca «estudiante» ni «docente» (lo comprueba la misma prueba).

## Esquemas

Los esquemas se generan desde los modelos Pydantic de `ai/app/domain/contracts/` y **no se editan a mano**:

```bash
# desde ai/ (con la imagen uv, ver ai/README.md)
uv run python -m scripts.export_schemas          # escribe prompts/schemas/
uv run python -m scripts.export_schemas --check  # falla si un esquema está desactualizado
```

| Contrato | Lo produce | Lo usa |
| --- | --- | --- |
| `syllabus` | `syllabus.structure` | API: `syllabus_extractions`, `topics`, `learning_outcomes`, `topic_prerequisites` (D2) |
| `assessment_item` | — (elemento del banco) | API: `assessment_items` |
| `assessment_item_bank` | `diagnostic.generate_items`, `items.generate_quiz_bank`, `items.generate_final_bank` | API: `assessment_items` (D5, E3, E6b, E8) |
| `item_review` | `items.review` | API: `assessment_items.auto_review`, `review_status` |
| `diagnostic_result` | `levels.estimate` (síncrona) | API: `diagnostics.level_by_topic` (E4) |
| `diagnostic_finalization` | `diagnostic.finalize` | API: `diagnostics`, `enrollments.objective_*` (U1a, E4) |
| `objective` | `diagnostic.finalize` (parte) | API: `enrollments.objective_*` (E4b) |
| `learning_path` | `path.sequence` (síncrona) | API: `path_steps` (E5) |
| `topic_explanation` | `content.explain_topic`, `content.remedial` | API: `resources` (E6, E7b, D5d) |
| `faithfulness_check` | `content.check_faithfulness` | API: `resources.faithfulness` (D5d) |
| `personalized_example` | `content.personal_example` | API: `resources` (`kind=personal_example`) |
| `video_resource` | `video.collect_candidates`, `video.rank` | API: `video_candidates` (D5e) |
| `grading` | `grading.short_answer` (y la regla de opción múltiple de la API) | API: `attempt_answers` (E7, D5c) |
| `badge_text` | `badge.compose_text` | API: texto del badge (E10) |
| `badge` | API (no `ai/`) | `GET /api/v1/badges/{public_id}/assertion.json` (Open Badges 2.0) |
| `simulated_answers` | `eval.simulate_learner` | Solo el arnés de evaluación |

**Identificadores en los contratos.** `ai/` trata `topic_id`, `outcome_id` e `item_id` como cadenas opacas y devuelve las mismas que recibió. En `syllabus` (antes de que existan filas) son las claves que propone el LLM (`topics.extraction_key`, `learning_outcomes.code`). En los demás trabajos la API envía el id de la base como texto (`"12"`). Los ejemplos usan claves legibles solo para que se entiendan.

## Ejemplos

`examples/` no son salidas reales del LLM (el notebook v2 nunca se ejecutó con el modelo; ver plan 3.1). Se redactaron a mano sobre el curso de ejemplo del notebook (Fundamentos de ML) y la aprendiz ficticia del notebook, y las pruebas garantizan que cumplen su esquema, su modelo y las validaciones de código. Las primeras salidas reales las guarda el arnés de evaluación de `ai/` (Fase 6).
