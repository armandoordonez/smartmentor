# Conjunto de oro de la evaluación

Referencias humanas con las que se comparan las salidas de la IA (Fase 9). **Este directorio solo
contiene la estructura y plantillas con los encabezados. No hay datos reales versionados** y no
debe haberlos: ni nombres, ni correos, ni texto de respuestas de aprendices.

## Qué va en cada carpeta

| Carpeta | Contenido | Quién lo produce | Métrica que alimenta | Tabla equivalente |
| --- | --- | --- | --- | --- |
| `syllabus/` | Temas y prerrequisitos correctos de cada syllabus de evaluación | Instructor | F1 de temas y prerrequisitos (meta 0,85) | `topics`, `topic_prerequisites` |
| `item_annotations/` | Rúbrica de 50 a 100 ítems aplicada por 2 expertos | Dos expertos (`evaluator_slot` 1 y 2) | % de preguntas válidas (meta 80 %) y κ (meta 0,6) | `item_annotations` |
| `short_answer_grading/` | Calificación humana de una muestra aleatoria de respuestas cortas | Persona calificadora | QWK (meta 0,6) | `human_gradings` |
| `video_relevance/` | Juicio de pertinencia de los videos candidatos de cada tema | Dos jueces (`judge_slot` 1 y 2) | P@3 (meta 0,7) y nDCG@3 | `video_relevance_judgments` |

La fuente primaria de estos datos es la base de datos del piloto (tablas de la última columna): los
expertos anotan desde la aplicación (pantalla D5b) y el cuaderno
`notebooks/metrics_cohort1.ipynb` los lee de allí. Los archivos CSV de este directorio son la
**copia de respaldo anonimizada** que se puede versionar o compartir con el director, y la forma de
cargar anotaciones hechas fuera de la aplicación.

## Formato

Archivos CSV en UTF-8, con coma, una fila por registro, encabezado en inglés idéntico al de las
plantillas `*.template.csv`. Los booleanos son `true` o `false`; `verdict` es `valid` o `invalid`.

| Archivo | Columnas | Notas |
| --- | --- | --- |
| `syllabus/gold_syllabus.template.csv` | `course_key`, `kind` (`topic` o `prerequisite`), `key` | Un tema es su `id` en *snake_case*; un prerrequisito es `prerequisito>tema` |
| `item_annotations/item_annotations.template.csv` | `assessment_item_id`, `evaluator_slot` (1 o 2), `single_correct`, `clear_stem`, `bloom_ok`, `plausible_distractors`, `verdict`, `comment` | Un ítem es válido si **ambos** expertos dicen `valid`. El `comment` no debe llevar datos personales |
| `short_answer_grading/human_gradings.template.csv` | `attempt_answer_id`, `sample_type` (`random` o `learner_request`), `grader_slot`, `criteria_met`, `criteria_total`, `score` (0 a 100) | **Sin el texto de la respuesta.** Solo el identificador opaco |
| `video_relevance/video_relevance.template.csv` | `topic_key`, `youtube_video_id`, `rank`, `judge_slot` (1 o 2), `is_relevant` | `rank` es la posición del recomendador; el juez no la ve al juzgar |

## Reglas

1. **Sin datos personales.** Los evaluadores se identifican con una ranura (`evaluator_slot`,
   `judge_slot`, `grader_slot`), nunca con nombre ni correo. Los ítems y las respuestas con un
   identificador opaco.
2. **Independencia.** Cada experto anota sin ver al otro ni la salida de la IA; el kappa solo vale
   si los juicios son independientes.
3. **Muestra aleatoria.** Para el QWK la muestra sale al azar de `attempt_answers` calificadas por el
   juez LLM; las solicitudes de revisión del aprendiz (`learner_request`) se guardan aparte porque
   están sesgadas hacia los desacuerdos.
4. **Tamaños mínimos del brief.** 50 a 100 ítems por 2 expertos; al menos los 3 primeros candidatos
   de cada tema para los videos.
5. Los datos reales entran por la aplicación o por la carga que haga la API, no por commit. Si hay
   que respaldar un CSV, se guarda fuera del repositorio.
