# 4. Prueba de prompts «Mago de Oz»

Actividad 4 de la Fase 0. El equipo genera a mano con el LLM el syllabus estructurado, el diagnóstico y un tema, y los muestra en el prototipo. Resultado esperado: **primeros ejemplos reales de salida y esquemas JSON**.

Estado según el [análisis](../README.md#análisis-detallado-del-prototipo-de-figma): el contenido del prototipo es verosímil y trazable, pero no hay evidencia de que venga del LLM ni hay esquemas JSON. Esta carpeta guarda la evidencia; los esquemas y los prompts van en [`prompts/`](../../prompts/README.md), que es donde los lee la capa de IA.

| Archivo | Contenido |
| --- | --- |
| [`smartmentor_mago_de_oz_gemini_v2.ipynb`](smartmentor_mago_de_oz_gemini_v2.ipynb) | **Versión vigente.** Notebook de la prueba con Gemini y embeddings, documentado frente al brief: contratos alineados con la API, prompts versionados, revisión automática y humana de ítems, recorrido completo de una estudiante simulada y paquete para el repositorio |
| [`smartmentor_mago_de_oz_gemini.ipynb`](smartmentor_mago_de_oz_gemini.ipynb) | Versión 1, se conserva como referencia de la evaluación de abajo |
| [`mago_de_oz.md`](mago_de_oz.md) | Explicación de qué es la prueba y por qué el análisis la dejó en ⚠️ |

## Evaluación del notebook frente a la rúbrica

Revisión del 2026-10-08 de [`smartmentor_mago_de_oz_gemini.ipynb`](smartmentor_mago_de_oz_gemini.ipynb). La rúbrica sale de la actividad 4 del brief («el equipo genera a mano con el LLM el syllabus estructurado, el diagnóstico y un tema, y los muestra en el prototipo»; herramienta: notebook + LLM; resultado: primeros ejemplos reales de salida y esquemas JSON) y del criterio de salida de la fase («esquemas JSON de cada salida de IA definidos y versionados en el repositorio»).

**Cumplimiento actual: 37,5 %** ⚠️

El notebook está bien diseñado y cubre todo el flujo, pero **no se ha ejecutado**: las 40 celdas tienen `execution_count` vacío y ninguna salida, y no existe `mago_de_oz_out/` ni nada en [`prompts/`](../../prompts/README.md). Por eso no hay evidencia de que el LLM haya producido algo, que es justamente lo que pide la actividad. Puntaje por criterio: ✅ = 100 %, ⚠️ = 50 %, ❌ = 0 %.

| # | Criterio | Peso | Estado | Evidencia en el notebook | Puntos |
| --- | --- | --- | --- | --- | --- |
| 1 | Se usa un notebook con un LLM real | 10 | ✅ | Gemini (`google-genai`) con salida estructurada (`response_json_schema`), validación con Pydantic y reintentos | 10 |
| 2 | Syllabus estructurado generado con el LLM | 10 | ⚠️ | Prompt `syllabus_estructurado v1.0`, verificación del DAG (ids únicos, prerrequisitos existentes, sin ciclos) y celda de correcciones del docente. Implementado, sin ejecutar | 5 |
| 3 | Diagnóstico generado con el LLM | 10 | ⚠️ | 3 preguntas por tema (Recordar, Aplicar, Analizar), nivel ponderado por dificultad y perfil semántico con embeddings. Implementado, sin ejecutar | 5 |
| 4 | Un tema completo: explicación, video y quiz | 10 | ⚠️ | Explicación con RAG y citas `[n]`, verificación de fidelidad, video reordenado por embeddings y quiz desde los resultados de aprendizaje. Sin ejecutar; sin `YOUTUBE_API_KEY` ni lista del docente, el tema queda sin video | 5 |
| 5 | Ejemplos reales de salida guardados | 15 | ❌ | El código las guarda en `mago_de_oz_out/salidas/` y en `llm_log.jsonl`, pero no hay ninguna salida | 0 |
| 6 | Esquemas JSON de cada salida definidos | 15 | ⚠️ | 10 contratos en Pydantic (syllabus, diagnóstico, objetivo, ruta, explicación, video, quiz, calificación, evaluación final, badge Open Badges) que cubren las 9 salidas de la tabla de abajo. Los `.v1.json` solo se generan al ejecutar | 7,5 |
| 7 | Esquemas versionados en el repositorio | 10 | ❌ | Ningún archivo de esquema en [`prompts/`](../../prompts/README.md) | 0 |
| 8 | Prompts versionados | 5 | ⚠️ | 10 prompts con versión `v1.0` dentro del notebook, que viaja en `meta` de cada salida; todavía no están en `prompts/` | 2,5 |
| 9 | Salidas mostradas en el prototipo | 10 | ❌ | Ya existen `fuente_unica_laura.json` y la función `pantallas()`, que derivan los datos de las pantallas de una sola fuente (esto resuelve las inconsistencias del prototipo), pero nada se ha llevado a Figma ni a `app/src/clients/sample_seed.py` | 0 |
| 10 | Registro de ejecuciones (modelo, prompt, tokens, costo, latencia, JSON válido) | 5 | ⚠️ | `llm_log.jsonl` y métricas de JSON inválido y latencia p95 frente a las metas del brief. Sin ejecutar y con `PRECIOS_USD_POR_MILLON` vacío, así que el costo saldría nulo | 2,5 |
| | **Total** | **100** | | | **37,5** |

### Qué falta para llegar al 100 %

| Paso | Criterios que cierra | Cumplimiento |
| --- | --- | --- |
| Ejecutar el notebook completo con `GEMINI_API_KEY`, llenar los precios y guardarlo **con sus salidas** en esta carpeta | 2, 3, 4, 5, 6 y 10 | 77,5 % |
| Copiar `mago_de_oz_out/schemas/` y `prompts/` a [`prompts/`](../../prompts/README.md), y `salidas/` a `data/ejemplos/` | 7 y 8 | 90 % |
| Cargar `fuente_unica_laura.json` en el prototipo (Figma y `sample_seed.py`) | 9 | 100 % |

### Observaciones

- **Nombres de campos en español.** Los esquemas usan nombres como `enunciado`, `nivel_bloom` o `respuesta_correcta`, pero la regla del repositorio es código y JSON en inglés. Hay que decidir antes de versionarlos, porque luego los usan la API y la app.
- **El modelo por defecto es `gemini-3.5-flash`.** Hay que confirmar que esté disponible para la clave con la celda que lista los modelos.
- **Las respuestas vienen de un estudiante simulado con LLM.** El brief lo acepta como respaldo, pero no sustituye la prueba de usabilidad: el pre-test y el post-test no usan ítems equivalentes, así que la ganancia de Hake que calcula es solo ilustrativa (el mismo notebook lo advierte).
- **Puntos a favor que van más allá de la rúbrica:** validación de los contratos con `jsonschema` (como lo haría la integración continua), caché por hash de entrada, verificación de fidelidad del RAG y una fuente única de datos con dos escenarios coherentes (`en_curso` y `final`).

## Versión 2 del notebook

La v2 corrige los problemas encontrados al revisar la estructura y los prompts de la v1 frente al brief:

| Problema en la v1 | Corrección en la v2 |
| --- | --- |
| La explicación del tema recibía el perfil del estudiante, así que se generaba una por estudiante, contra la «caché por tema» y el «recurso compartido» del brief | `topic_explanation` es por tema y sin datos del estudiante; la personalización pasa a `personalized_example` (corto) y `remedial_explanation` (tras fallar el quiz) |
| Campos de los esquemas en español | Campos en inglés alineados con la API: `bloom_level` (`remember`…`create`), `learning_outcomes`, `prerequisites`, estados `pending`/`in_progress`/`passed`/`failed`/`skipped`, umbrales y puntajes de 0 a 100, log con los campos de `llm_logs` |
| Sin juicio humano sobre las preguntas | Prompt `item_review` (una sola respuesta correcta, claridad, Bloom, alineación) que descarta ítems inválidos, y exportación a CSV para 2 expertos y para calificar respuestas cortas a mano, con cálculo de kappa de Cohen y QWK |
| El quiz recibía el texto de estudio | Se genera solo desde los resultados de aprendizaje |
| Sin «No lo sé» en el diagnóstico | El estudiante simulado puede usarlo, como en E3 |
| Obligaba a inventar `horas_estimadas` | `estimated_hours` = 0 si el syllabus no lo indica |
| E4 clasificaba sin cortes definidos | `mastered` ≥ 80, `to_reinforce` 50 a 79, `to_learn` < 50 (propuesta de la decisión 4 de los casos de uso) |
| El repaso de la final fallaba si una pregunta caía en un tema omitido | La final solo usa temas de la ruta |
| El orden topológico podía alterar el orden de las unidades | Respeta el orden del syllabus cuando los prerrequisitos lo permiten |

Cada sección del notebook explica qué parte del brief cumple (actividad 4 de la Fase 0, criterio de salida, componentes de IA 1 a 7, decisiones técnicas y métricas) y qué pantalla del prototipo alimenta.

**Verificación.** La v2 se ejecutó de punta a punta con un cliente de Gemini simulado, sin red ni API key, para comprobar el código: 48 de 48 salidas cumplen su esquema, los dos escenarios de pantallas son coherentes, y se recorren los caminos de tema omitido, ítem descartado, quiz no aprobado con refuerzo, final no aprobada con repaso dirigido y badge. Esa ejecución **no cuenta como evidencia**: las salidas eran sintéticas. La evaluación de arriba sigue vigente hasta ejecutar la v2 con Gemini y guardarla con sus salidas.

## Protocolo

1. Poner el syllabus real del piloto junto al notebook v2 (`syllabus.txt`, `.md` o `.pdf`) y las fuentes en `fuentes/`.
2. Ejecutar el notebook completo: cada salida se pide con salida estructurada y su esquema, se valida y queda en `mago_de_oz_out_v2/outputs/`.
3. Cada llamada queda en `llm_log.jsonl` (modelo, versión del prompt, tokens, costo, latencia, JSON válido). No hace falta llenarlo a mano.
4. Si una salida no cumple su esquema, se corrige el prompt (subiendo su versión), no la salida.
5. Dos expertos llenan `review/items_for_experts.csv` y se califica a mano `review/short_answers_for_human_grading.csv`; se vuelve a correr la sección 13.
6. Pasar las pantallas (`screens_in_progress.json`, `screens_final.json`) al prototipo (Figma y `app/src/clients/sample_seed.py`) sin editarlas. Si hay que editarlas, anotar qué y por qué: eso también es un hallazgo.
7. Guardar el notebook con sus salidas y copiar el paquete de la sección 17 al repositorio.

## Salidas y esquemas

Contratos de la v2. Los esquemas se escriben en Pydantic, se exportan a JSON Schema y se versionan en `prompts/schemas/`.

| Contrato | Pantallas | Campos principales | Esquema | Evidencia |
| --- | --- | --- | --- | --- |
| `syllabus` | D2 | `topics[]`: `name`, `learning_outcomes[]`, `bloom_level`, `prerequisites[]`; `default_objective`, `approved_by_teacher` | `prompts/schemas/syllabus.v2.json` | [ ] |
| `diagnostic` | E3, E4 | `questions[]` (`stem`, `options[]`, `correct_option`, `rationale`), `item_reviews[]`, `answers[]` (con `dont_know`), `level_by_topic[]` (`level`, `classification`, `skip`) | `prompts/schemas/diagnostic.v2.json` | [ ] |
| `objective` | E4 | `statement`, `bloom_verb`, `content`, `criterion`, `focus_topics[]` | `prompts/schemas/objective.v2.json` | [ ] |
| `learning_path` | E5, D3 | `steps[]`: `step_order`, `status`, `score`, `attempts` | `prompts/schemas/learning_path.v2.json` | [ ] |
| `topic_explanation` | E6 | `sections[]` con citas `[n]`, `sources[]`, `faithfulness`, `audience` | `prompts/schemas/topic_explanation.v2.json` | [ ] |
| `personalized_example` | E6 | `example`, `connection` | `prompts/schemas/personalized_example.v2.json` | [ ] |
| `video_resource` | E6 | `candidates[]` con `similarity`, `selected` | `prompts/schemas/video_resource.v2.json` | [ ] |
| `quiz` | E6 | `questions[]`: `type`, `stem`, `options[]`, `correct_option`, `model_answer`, `rubric[]`; `item_reviews[]` | `prompts/schemas/quiz.v2.json` | [ ] |
| `grading` | E7, D4 | `results[]` (`score`, `grader`, `feedback`, `rubric_detail`), `score`, `passed` | `prompts/schemas/grading.v2.json` | [ ] |
| `final_assessment` | E8, E9 | `questions[]` por tema, `topics_assessed[]` | `prompts/schemas/final_assessment.v2.json` | [ ] |
| `badge` | E10, E12 | Open Badges 2.0: `recipient`, `badge.issuer`, `badge.criteria`, `issuedOn`, `evidence` | `prompts/schemas/badge.v2.json` | [ ] |

## Mínimo para cerrar la actividad

El brief pide tres: **syllabus estructurado, diagnóstico y un tema** (explicación y quiz). Las demás salidas pueden quedar con esquema y sin ejemplo real.

## Registro de ejecuciones

| Fecha | Salida | Modelo | Prompt (versión) | Tokens | Costo (USD) | Latencia (s) | ¿JSON válido? | ¿Editada a mano? |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| | | | | | | | | |
