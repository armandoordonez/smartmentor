# 4. Prueba de prompts «Mago de Oz»

Actividad 4 de la Fase 0. El equipo genera a mano con el LLM el syllabus estructurado, el diagnóstico y un tema, y los muestra en el prototipo. Resultado esperado: **primeros ejemplos reales de salida y esquemas JSON**.

Estado según el [análisis](../README.md#análisis-detallado-del-prototipo-de-figma): el contenido del prototipo es verosímil y trazable, pero no hay evidencia de que venga del LLM ni hay esquemas JSON. Esta carpeta guarda la evidencia; los esquemas y los prompts van en [`prompts/`](../../prompts/README.md), que es donde los lee la capa de IA.

## Protocolo

1. Elegir un syllabus real (1 o 2 del piloto) y guardar su texto en `entradas/`.
2. Para cada salida de la tabla, ejecutar el prompt en el notebook ([`notebooks/`](../../notebooks/)) con salida estructurada y el esquema correspondiente.
3. Guardar la respuesta cruda del LLM en `salidas/<salida>-<fecha>.json` y anotar modelo, versión del prompt, tokens, costo y latencia en el registro de abajo.
4. Validar el JSON contra el esquema. Si falla, anotarlo (cuenta para la métrica de JSON inválido) y corregir el prompt, no la salida.
5. Pasar la salida al prototipo (Figma o `app/src/clients/sample_seed.py`) sin editarla a mano. Si hay que editarla, anotar qué y por qué: eso también es un hallazgo.

## Salidas y esquemas

Campos mínimos observados en las pantallas del prototipo. El esquema definitivo se escribe en Pydantic y se exporta a JSON Schema.

| Salida | Pantalla | Campos mínimos | Esquema | Evidencia |
| --- | --- | --- | --- | --- |
| `syllabus` | D2 | temas[]: `title`, `learning_outcomes[]`, `bloom_level`, `prerequisites[]` | `prompts/schemas/syllabus.json` | [ ] |
| `diagnostic_question` | E3 | `topic_id`, `bloom_level`, `prompt`, `options[]`, `answer`, `rationale` | `prompts/schemas/diagnostic_question.json` | [ ] |
| `diagnostic_result` | E4 | por tema: `score`, `classification` (dominado, por reforzar, por aprender) | `prompts/schemas/diagnostic_result.json` | [ ] |
| `learning_objective` | E4 | `verb` (Bloom), `content`, `criterion`, `text` | `prompts/schemas/learning_objective.json` | [ ] |
| `topic_explanation` | E6 | `body` con citas `[n]`, `sources[]`, `prompt_version` | `prompts/schemas/topic_explanation.json` | [ ] |
| `quiz` | E6, E8 | `questions[]`: `type` (opción múltiple o respuesta corta), `prompt`, `options[]`, `answer`, `rubric` | `prompts/schemas/quiz.json` | [ ] |
| `quiz_grading` | E7 | por pregunta: `score`, `feedback`; total y `passed` | `prompts/schemas/quiz_grading.json` | [ ] |
| `final_assessment` | E8, E9 | `questions[]` por tema, temas débiles para el repaso | `prompts/schemas/final_assessment.json` | [ ] |
| `badge` | E10 | Open Badges: `issuer`, `criteria`, `issuedOn`, `recipient`, `evidence` | `prompts/schemas/badge.json` | [ ] |

Los nombres de archivo y de campo siguen la regla del repositorio: código en inglés, documentación en español. El nombre definitivo de cada esquema se fija con el responsable de IA y datos.

## Mínimo para cerrar la actividad

El brief pide tres: **syllabus estructurado, diagnóstico y un tema** (explicación y quiz). Las demás salidas pueden quedar con esquema y sin ejemplo real.

## Registro de ejecuciones

| Fecha | Salida | Modelo | Prompt (versión) | Tokens | Costo (USD) | Latencia (s) | ¿JSON válido? | ¿Editada a mano? |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| | | | | | | | | |
