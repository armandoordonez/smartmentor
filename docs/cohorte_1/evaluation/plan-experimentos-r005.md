# Plan de los experimentos de R-005 (fase actual)

Plan acordado con el dueño el 2026-11-16 para ejecutar los experimentos que se alcanzan en esta fase de [`R-005`](../trazabilidad/TRAZABILIDAD.md). Va junto a `TRAZABILIDAD.md` y se actualiza con cada experimento.

## 1. Alcance

| Experimento | Meta | Estado en este plan |
| --- | --- | --- |
| E1, E8 | Ya ejecutados | Fuera del plan ([`e8-2026-11-15.md`](results/e8-2026-11-15.md)) |
| **E2** Estructuración del syllabus | F1 ≥ 0,85 | **Entra** |
| **E3** Preguntas válidas | ≥ 80 % válidas y κ ≥ 0,6 | **Entra** |
| **E5** Fidelidad y cobertura del RAG | Fidelidad ≥ 0,8 | **Entra** (la condición con lecturas depende de que lleguen) |
| **E6** Videos por tema | P@3 ≥ 0,7 | **Entra** (herramienta lista: [`e6-videos.md`](e6-videos.md)) |
| **E7** Juez del sistema frente a un juez de referencia | QWK ≥ 0,6 | **Entra** |
| E4, E9, E10 | Dependen del piloto | Migrados a la siguiente fase ([`TRAZABILIDAD.md`](../trazabilidad/TRAZABILIDAD.md)) |

## 2. Decisiones del dueño (2026-11-16)

1. Los jueces y anotadores son **dos agentes de IA afinados como jueces**, no personas.
2. Tope de gasto de IA del sistema: **US$ 3 en total**, ampliable a **US$ 4 o 5** si mejora los experimentos (se pide aviso antes de pasar de 3).
3. E5: las lecturas de la condición «syllabus + apuntes» las aporta el dueño; E5 va al final por eso.
4. Para E7 se usa **un agente** como estudiante de prueba nuevo.
5. E5 entra en el plan.
6. Orden: E3 y E6 primero, luego E2 y E7, E5 al final.
7. **Modelos:** solo Opus o Sonnet, según el papel. Nunca Fable.
8. **Nombres:** todo lo que se crea para los experimentos lleva el prefijo `experimento_` (ver sección 4).

## 3. Lo que hay que decir al reportar (límites)

- Los jueces son agentes de IA (Claude), **no expertos humanos**. Los resultados se reportan como «jueces-agente, versión MVP, datos de prueba, indicativos». Un κ entre dos jueces-agente mide su acuerdo, no la validez frente a un experto.
- **E7 no es «juez LLM contra humano»:** es el juez del sistema (que corre con el proveedor configurado, hoy Gemini) contra un juez de referencia de otra familia (Claude Opus). Se reporta como acuerdo entre jueces. Las respuestas vienen de estudiantes simulados o de prueba, de **solo 8 ítems de respuesta corta**.
- **E6:** los jueces solo ven los metadatos del video (título, canal, duración, idioma y, si se exporta, la descripción), no el contenido. Es una limitación de la pertinencia que se juzga.
- **E2:** el patrón de oro lo arma un agente-instructor a ciegas a partir del texto del syllabus. Solo el de AD1 lo puede revisar el dueño, que conoce el curso.
- **Calibración humana opcional (recomendada):** 15 a 20 elementos por experimento revisados por una persona del equipo permiten decir cuánto se parece el juez-agente a una persona. Si no se hace, se dice.
- Tamaños de muestra y versiones (prompts, modelos, commit de `dev`, fecha) se registran en cada resultado.

## 4. Convención de nombres

Todo lo que se cree para los experimentos lleva el prefijo `experimento_` en el nombre visible y en el correo, para distinguirlo de los usuarios de los recorridos y del piloto. Los usuarios que ya existen no se renombran.

| Qué | Nombre visible | Correo (variable en `.env.example`) |
| --- | --- | --- |
| Estudiante de prueba (E7) | `experimento_estudiante` | `experimento_estudiante.smartmentor@yopmail.com` (`SEED_EXPERIMENT_LEARNER_EMAIL`) |
| Instructor | `experimento_instructor` | `experimento_instructor.smartmentor@yopmail.com` (`SEED_EXPERIMENT_INSTRUCTOR_EMAIL`) |
| Evaluador 1 (juez 1) | `experimento_evaluador_1` | `experimento_evaluador_1.smartmentor@yopmail.com` (`SEED_EXPERIMENT_EVALUATOR_1_EMAIL`) |
| Evaluador 2 (juez 2) | `experimento_evaluador_2` | `experimento_evaluador_2.smartmentor@yopmail.com` (`SEED_EXPERIMENT_EVALUATOR_2_EMAIL`) |
| Cursos creados | `experimento_` + nombre | p. ej. `experimento_Análisis de datos I` |
| Archivos de resultados | `docs/cohorte_1/evaluation/results/` | `e3-AAAA-MM-DD.md` (se cita el prefijo en el texto) |

Los evaluadores existen como cuentas porque anotan por la aplicación (D5b y D5c), que guarda `evaluator_slot` y `judge_slot`. Los crea el script `scripts/dev-seed-recorrido-users.sh` ampliado, sin SQL y con la contraseña `SEED_USERS_PASSWORD` (misma regla de siempre: solo por entorno).

## 5. Agentes, papeles y modelos

| Papel | Modelo | Qué hace | Por qué |
| --- | --- | --- | --- |
| **Juez 1** (`experimento_evaluador_1`) | **Opus** | Anota ítems (E3), juzga videos (E6) y califica respuestas (E7) a ciegas | Mejor juicio en tareas de evaluación |
| **Juez 2** (`experimento_evaluador_2`) | **Sonnet** | Lo mismo, en un contexto aparte | Un modelo distinto baja el riesgo de errores correlacionados, y con ello el de un κ inflado |
| **Agente-instructor** (`experimento_instructor`) | **Opus** | Arma el patrón de oro de E2 a ciegas | Es la tarea de más criterio |
| **Agente-estudiante** (`experimento_estudiante`) | **Sonnet** | Recorre la aplicación y responde con calidad variada (E7) | Es manejo de interfaz, no juicio |
| **Preparación y cálculo** | **Sonnet** | Scripts, exportaciones, ejecuciones y métricas | Es trabajo mecánico y verificable |
| **Revisión final** | Opus (el orquestador) | Verifica números, límites y que se cumpla este plan | Responsabilidad del reporte |

**Afinado de los jueces (antes de contar nada):**

1. Cada juez recibe un perfil fijo con la rúbrica de [`metrics.md`](metrics.md) y el formato exacto de salida (el CSV de `data/eval/gold/`).
2. **A ciegas:** no ven el `rank` del recomendador, ni el veredicto o puntaje del sistema, ni lo que anotó el otro juez. Cada juez trabaja en su propio contexto y no se comunica con el otro.
3. **Prueba de práctica de 5 elementos** que no se cuentan: se revisa que entiendan la rúbrica y el formato.
4. **Auto-consistencia:** el 10 % de los elementos se repite, mezclado, para medir si el mismo juez responde igual dos veces.
5. Cada decisión lleva una frase de motivo, que sirve para auditar los desacuerdos.
6. El orden de los elementos y las muestras salen al azar con **semilla fija** registrada.
7. Los jueces no escriben datos personales en ninguna parte (regla de `data/eval/gold/README.md`).

## 6. Reglas comunes

- Las anotaciones entran **por la aplicación** (D5b, D5c, D5e) o por la carga de la API, nunca por commit. Los CSV con datos reales no se versionan.
- Solo flujo normal de usuario: no se borra nada, no se toca la base ni Keycloak directamente, no se usa el simulador de aprendices.
- Tope de IA del sistema: US$ 3 (hasta 5 con aviso). Se mide con `GET /api/v1/llm-call-logs/summary` antes y después de cada experimento y se detiene al 90 % del tope.
- Cada experimento deja un resultado en `docs/cohorte_1/evaluation/results/` (como el de E8) y una nota en [`TRAZABILIDAD.md`](../trazabilidad/TRAZABILIDAD.md) y en G-001 cuando toque pantallas.
- Los agentes no suben a `dev` ni a `stage` ni a `main`; los cambios de código siguen el flujo de ramas y PR.

## 7. Cada experimento

### E3 · Preguntas válidas

- **Entrada:** 80 ítems sacados al azar (semilla fija) de los 340 de los cuatro cursos publicados (ids 2, 4, 5 y 8), con muestra repartida entre cursos y temas.
- **Procedimiento:** los dos jueces anotan cada ítem a ciegas con los cuatro criterios (`single_correct`, `clear_stem`, `bloom_ok`, `plausible_distractors`) y un veredicto `valid` o `invalid`, por D5b.
- **Métrica:** % de ítems con todos los veredictos válidos, κ de Cohen y κ por criterio (`v_item_validity`).
- **Resultado:** `e3-AAAA-MM-DD.md`.
- **Costo de IA del sistema:** ninguno (solo lectura y anotación).

### E6 · Videos por tema

- **Entrada:** los candidatos de los temas publicados. Hoy hay 28 para 17 temas, y E6 pide al menos 3 por tema.
- **Paso previo:** «Buscar videos de nuevo» en D5e por tema, para que cada candidato tenga `search_position` (B-064).
- **Procedimiento:** exportar y generar las hojas ciegas con `python -m eval.video_experiment export`, que los dos jueces llenen, e importar.
- **Métrica:** κ de los jueces, P@3 y nDCG@3 de las cuatro ordenaciones (al azar, orden de YouTube, solo similitud y puntaje vigente).
- **Resultado:** `e6-AAAA-MM-DD.md`.
- **Costo:** la búsqueda y los embeddings de los videos nuevos; pequeño, a medir.

### E2 · Estructuración del syllabus

- **Entrada:** los dos syllabus reales de `ai/docs/syllabus/` (cursos `experimento_` nuevos o los v2 existentes; se decide al armar).
- **Procedimiento:** el agente-instructor escribe a ciegas la lista de temas y prerrequisitos de cada syllabus (formato de `gold_syllabus.template.csv`). Luego se extrae con **2 modelos × 3 repeticiones** y se compara.
- **Métrica:** precisión, recall y F1 de temas y de prerrequisitos (`set_f1`), por modelo.
- **Resultado:** `e2-AAAA-MM-DD.md`.
- **Costo de IA del sistema:** unas 12 extracciones, de US$ 0,10 a 0,15.
- **Verificado (2026-11-16):** `POST /courses/{id}/extractions` **no deja elegir el modelo** y las repeticiones con el mismo texto salen de la caché (`ai_generation_cache`), así que no serían independientes. Además re-extraer reemplaza los temas del curso. Por eso **no se usa la API**: se escribe un script pequeño (`ai/eval/syllabus_experiment.py`, con rama y PR) que usa `EvalWorld.structure_syllabus`, que tiene caché nueva en cada proceso, y corre 6 procesos por syllabus. Los dos modelos son `gemini-3.8-flash` y `gemini-3.5-flash-lite` (los dos tienen precio en `ai/config/prices.yaml`), cambiando `AI_LLM_MODEL_DEFAULT` solo en el entorno del script. No toca la base, la API ni los contenedores.
- **Emparejamiento:** el F1 del sistema compara ids `snake_case` inventados por el LLM, y un patrón de oro a ciegas casi nunca los repite. El agente-instructor escribe el oro como **nombres** de temas y prerrequisitos, y el emparejamiento con cada extracción se hace por nombre con un juez (Opus), antes de calcular `set_f1` (`ai/app/domain/metrics.py`). Se reporta cuántos emparejó.
- **Syllabus:** son los dos PDF de `ai/docs/syllabus/` del equipo del dueño (carpeta ignorada por git; no están en `dev`).

### E7 · Juez del sistema frente a un juez de referencia

- **Entrada:** las respuestas cortas ya calificadas por el juez del sistema (unas 118, de 8 ítems) más las que genere **un agente-estudiante** (`experimento_estudiante`) respondiendo con calidad variada. Si hace falta más variedad, se evalúa publicar un curso con más ítems de respuesta corta (pide aviso de costo).
- **Procedimiento:** el juez de referencia (juez 1, Opus) califica a ciegas al menos 50 respuestas, desde D5c, sin ver el puntaje del sistema. Las solicitudes de revisión del aprendiz se guardan aparte, como pide el README del conjunto de oro.
- **Métrica:** QWK entre el puntaje del sistema y el del juez de referencia (`qwk`).
- **Resultado:** `e7-AAAA-MM-DD.md`, con el límite de la sección 3.
- **Costo:** el estudiante de prueba, de unos centavos.

### E5 · Fidelidad y cobertura del RAG

- **Entrada:** 5 o 6 temas de un curso publicado, en dos condiciones: **(A)** solo el syllabus y **(B)** syllabus más 2 o 3 lecturas aportadas por el dueño. R-010 permite agregar y quitar los apuntes en el mismo curso.
- **Procedimiento:** subir las lecturas, regenerar los temas (`POST /resources/{id}/regenerate`) y medir; desactivar las lecturas (`PATCH …/materials/{id}/deactivate`), regenerar de nuevo y medir. La caché no estorba porque cambian los fragmentos. Se guarda el texto y la fidelidad de cada versión antes de la siguiente.
- **Fidelidad:** **RAGAS no existe en el repositorio** (el cuaderno lanza `NotImplementedError`). Se usa la fidelidad del verificador propio (`resources.faithfulness`, ya medida) y, para no evaluarse con el mismo modelo, una **verificación independiente de los jueces-agente** sobre una muestra de afirmaciones frente a sus fragmentos. Los dos valores se reportan por separado. La cobertura la valoran los dos jueces a ciegas.
- **Métrica:** fidelidad (meta ≥ 0,8), cobertura por condición.
- **Resultado:** `e5-AAAA-MM-DD.md`.
- **Costo estimado:** unos US$ 0,10 por 12 textos (estimación, no medida).
- **Puerta:** si las lecturas no llegan, E5 se ejecuta solo con la condición A y se dice.

## 8. Orden y puertas

| Paso | Qué | Puerta para pasar al siguiente |
| --- | --- | --- |
| 0 | Crear las cuentas `experimento_` (PR del script) y confirmar versiones | Cuentas verificadas con `GET /me` |
| 1 | Afinar los dos jueces (práctica y auto-consistencia) | Los dos entienden la rúbrica |
| 2 | **E3** y **E6** en paralelo | Resultado y métricas revisados |
| 3 | **E2** y **E7** | Verificación de los modelos de E2 resuelta |
| 4 | **E5** | Lecturas recibidas y costo medido |
| 5 | Consolidar | Resultados en `TRAZABILIDAD.md`, G-001 y la tabla de resultados |

## 9. Verificación previa (2026-11-16, solo lectura)

1. **E2:** resuelto con un script propio (ver E2). Cuesta unos US$ 0,10 en `gemini-3.8-flash`; el modelo pequeño, menos.
2. **E6:** la búsqueda de videos no tiene tope diario en el código. Buscar de nuevo los 17 temas gasta de 1.700 a 3.400 unidades de YouTube (100 por búsqueda), de las 10.000 diarias por defecto; hay que mirar en Google Cloud cuánta cuota queda, porque el repositorio no lo dice.
3. **E5:** RAGAS no existe; se sustituye como se explica en E5. Regenerar un texto cuesta unos US$ 0,008 (estimado).

## 10. Después

Con los resultados se actualizan la fila R-005 de `TRAZABILIDAD.md` y las métricas del cuaderno `notebooks/metrics_cohort1.ipynb`. Lo que no se alcance pasa a la siguiente fase con su motivo.
