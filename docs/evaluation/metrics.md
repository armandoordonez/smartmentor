# Métricas de evaluación

Definición, fórmula, origen de los datos, meta del brief e interpretación de cada métrica. Las
metas son las **orientativas** de la sección «Métricas y evaluación» del brief; cada cohorte puede
ajustarlas con datos. El cálculo está en `ai/app/domain/metrics.py` (funciones puras, solo
biblioteca estándar, con pruebas contra valores a mano en `ai/tests/unit/test_metrics.py`) y se
ejecuta de arriba abajo en `notebooks/metrics_cohort1.ipynb`.

Los nombres de tabla y columna son los del esquema `v2.0.0` y las consultas de
`notebooks/metrics_data.py` se probaron contra ese esquema (PostgreSQL desechable con datos mínimos). Dos
columnas son `jsonb` libre cuya forma fija la API, no el esquema: `diagnostics.level_by_topic` (objeto con el
id del tema como clave y `test_score` de 0 a 1 por tema) y `survey_responses.likert` (objeto con
`satisfaction`, `usefulness` y `self_efficacy`, de 1 a 5). Están marcadas `SUPUESTO` y el cuaderno falla con un
mensaje claro (`UnexpectedShapeError`) si la forma real es otra. El primer intento de un tema sale de
`assessment_attempts` (`assessment_type = 'topic'`, `attempt_number = 1`, `passed`), porque `path_steps` no
guarda ese dato; el estado aprobado de un paso es `passed`.

## Cómo se ejecuta

| Modo | Condición | Resultado |
| --- | --- | --- |
| Cohorte real | `METRICS_DATABASE_URL` en el entorno, con el usuario de **solo lectura** `smartmentor_metrics` (`METRICS_DATABASE_USER` y `METRICS_DATABASE_PASSWORD` del `.env`) | Métricas con el n real; el cuaderno solo imprime agregados |
| Demostración | Sin `METRICS_DATABASE_URL` | Datos sintéticos con semilla (`notebooks/synthetic_data.py`); **no son resultados del piloto** |

Instrucciones y comandos: `notebooks/README.md`.

## Métricas del sistema

### Estructuración del syllabus: F1 de temas y prerrequisitos

| Campo | Detalle |
| --- | --- |
| Función | `set_f1(predicted, gold)` |
| Fórmula | `P = TP / |predichos|`, `R = TP / |finales|`, `F1 = 2PR / (P + R)`. Los temas se comparan por su `id`; un prerrequisito es el par `prerrequisito>tema` |
| Tabla | `syllabus_extractions.raw_output` (extracción vigente, `is_current`) frente a `topics` y `topic_prerequisites` (lo que dejó el instructor, sin los eliminados) |
| Meta | F1 ≥ 0,85 |
| Interpretación | Mide cuánto del trabajo del instructor evita la IA. La precisión baja indica temas inventados; el recall bajo, temas omitidos. Dos conjuntos vacíos dan 1,0; uno solo vacío da 0 |

### Calidad de preguntas: % de válidas y kappa de Cohen

| Campo | Detalle |
| --- | --- |
| Funciones | `valid_question_rate(verdicts_by_item)`, `cohen_kappa(a, b)` |
| Fórmulas | Válidas: `100 · ítems con todos los veredictos «valid» / ítems`. Kappa: `κ = (po − pe) / (1 − pe)`, con `po` el acuerdo observado y `pe` el esperado por azar según las marginales |
| Tabla | `item_annotations` (`verdict`, y los cuatro criterios `single_correct`, `clear_stem`, `bloom_ok`, `plausible_distractors`); vista `v_item_validity` |
| Meta | ≥ 80 % válidas y κ ≥ 0,6 |
| Interpretación | κ < 0,4 es acuerdo débil: la rúbrica es ambigua y el % de válidas no es confiable. Un κ alto con muchos inválidos es un problema del generador, no de los expertos. Se reporta κ por criterio para ver cuál no se entiende |

### Psicometría de ítems: dificultad y discriminación

| Campo | Detalle |
| --- | --- |
| Funciones | `item_difficulty(correct)`, `item_discrimination(item_correct, total_scores)`, `point_biserial` |
| Fórmulas | Dificultad `p = correctas / respuestas`. Discriminación: correlación punto-biserial `r = (m1 − m0)/s · √(p(1 − p))` entre acertar el ítem y el puntaje total del intento **sin ese ítem** (corregida) |
| Tabla | `attempt_answers` (`is_correct`) de los intentos de la cohorte; el total sale de sumar los aciertos de cada intento |
| Meta | Discriminación ≥ 0,2 |
| Interpretación | Dificultad muy cerca de 0 o 1 no informa. Discriminación ≤ 0 marca un ítem defectuoso (clave equivocada o ambiguo) que el instructor debe retirar. Se exige un mínimo de 10 respuestas por ítem; con menos es ruido |

### Texto generado (RAG): fidelidad

| Campo | Detalle |
| --- | --- |
| Cálculo | Media de `resources.faithfulness` (proporción de afirmaciones respaldadas por las fuentes) |
| Tabla | `resources.faithfulness`, `resources.unsupported_claims` |
| Meta | Fidelidad ≥ 0,8 |
| Interpretación | Se complementa con RAGAS (relevancia de la respuesta y precisión del contexto) y revisión manual de una muestra. RAGAS necesita un LLM y red: el cuaderno lo deja apagado (`SHOW_RAGAS`) y se corre aparte |

### Recomendación de videos: Precision@3 y nDCG@3

| Campo | Detalle |
| --- | --- |
| Funciones | `precision_at_k(relevances, k)`, `ndcg_at_k(relevances, k)` |
| Fórmulas | `P@k = relevantes en las k primeras / k`. `DCG@k = Σ rel_i / log2(i + 1)`, `nDCG@k = DCG@k / DCG ideal` (el ideal ordena todos los candidatos juzgados) |
| Tabla | `video_relevance_judgments` unida a `video_candidates` (`rank`, por tema) |
| Meta | P@3 ≥ 0,7 |
| Interpretación | Relevancia binaria: la mayoría de los jueces lo marca pertinente. Para nDCG se usa la proporción de jueces. Se reporta la línea base de azar (fracción de candidatos pertinentes) para que P@3 se lea contra algo; si no supera al azar, el recomendador no aporta |

### Calificación automática: QWK

| Campo | Detalle |
| --- | --- |
| Función | `quadratic_weighted_kappa(a, b, min_rating, max_rating)` |
| Fórmula | `QWK = 1 − Σ w·O / Σ w·E`, con `w_ij = (i − j)² / (K − 1)²`, `O` los conteos observados y `E` los esperados por azar |
| Tabla | `human_gradings.score` frente a `attempt_answers.score` donde `grader = 'llm_judge'`. Los puntajes 0 a 100 se redondean a 5 niveles (0, 25, 50, 75, 100) |
| Meta | QWK ≥ 0,6 |
| Interpretación | Penaliza más los desacuerdos grandes que los pequeños. Vale la muestra **aleatoria**; las solicitudes de revisión del aprendiz (`learner_request`) se reportan aparte porque se concentran en desacuerdos |

### Validez del diagnóstico: AUC-ROC

| Campo | Detalle |
| --- | --- |
| Función | `auc_roc(scores, labels)` |
| Fórmula | Probabilidad de que un caso positivo tenga mayor puntaje que uno negativo (estadística de Mann-Whitney, empates a 0,5) |
| Tabla | `diagnostics.level_by_topic` (nivel estimado por tema) frente a si la persona aprobó el quiz del tema al primer intento (`path_steps`) |
| Meta | AUC ≥ 0,7 |
| Interpretación | 0,5 es azar. Por debajo de 0,5 el diagnóstico está invertido. Se calcula sobre pares (persona, tema) que intentaron el quiz; las personas no son independientes entre sí, de modo que con pocos participantes el valor es indicativo |

### Eficiencia de la personalización

| Campo | Detalle |
| --- | --- |
| Cálculo | Temas con `inclusion_reason = 'skipped_mastered'` por persona y la suma de `estimated_minutes` de los temas omitidos |
| Tabla | `path_steps`, `topics`, brazo de `enrollments.pilot_arm` |
| Meta | Reportar |
| Interpretación | El ahorro solo cuenta si no hay pérdida de aprendizaje: se lee junto a la ganancia de Hake de ambos brazos |

### Desempeño técnico y costo

| Campo | Detalle |
| --- | --- |
| Funciones | `percentile`, `latency_percentiles` |
| Fórmulas | p50 y p95 por interpolación lineal (igual que `numpy.percentile`). JSON inválido: `100 · llamadas con json_valid = false / llamadas`. Costo: suma de `cost_usd` por inscripción y por tarea |
| Tabla | `llm_call_logs` (`latency_ms`, `json_valid`, `from_cache`, `cost_usd`, `task`); vista `v_llm_cost_summary` |
| Meta | p95 < 20 s, JSON inválido < 2 %, costo: reportar |
| Interpretación | La latencia excluye las respuestas de caché (no llamaron al proveedor). Cada intento de llamada es una fila, así que un reintento por JSON inválido cuenta. Se reporta por tarea porque la media global oculta la tarea lenta |

### Usabilidad: SUS

| Campo | Detalle |
| --- | --- |
| Función | `sus_score(responses)` |
| Fórmula | Ítems impares aportan `r − 1`, ítems pares `5 − r`; la suma se multiplica por 2,5 (0 a 100) |
| Tabla | `survey_responses.sus_items` (10 enteros de 1 a 5) |
| Meta | SUS ≥ 68 |
| Interpretación | 68 es la media histórica de la escala; 80 o más es excelente. Con 15 a 30 personas el intervalo es ancho: se reporta con el n |

## Métricas de los estudiantes

### Ganancia de aprendizaje: Hake

| Campo | Detalle |
| --- | --- |
| Funciones | `hake_gain(pre, post)`, `mean_hake_gain(pairs)` |
| Fórmula | `g = (post − pre) / (100 − pre)` por persona; luego se promedia. Quien tiene `pre = 100` no tiene margen y queda fuera del promedio (no se inventa un valor) |
| Tabla | Pre: promedio de `test_score` de `diagnostics.level_by_topic`. Post: mejor nota de la evaluación final (`assessment_attempts`). Ítems equivalentes por `assessment_items.equivalence_group` |
| Meta | g ≥ 0,3 (media) |
| Interpretación | Hake corrige el techo: quien parte alto necesita menos puntos para ganar lo mismo. Sin ítems equivalentes entre pre y post la ganancia no es comparable |

### Tamaño del efecto: d de Cohen

| Campo | Detalle |
| --- | --- |
| Funciones | `cohens_d(treatment, control)`, `cohens_d_with_ci(...)` |
| Fórmula | `d = (m_t − m_c) / s_p`, con `s_p` la desviación estándar combinada. IC 95 % por bootstrap percentil (2000 remuestreos por grupo, semilla fija) |
| Tabla | Ganancias por persona de `enrollments.pilot_arm` (`personalized` frente a `fixed`) |
| Meta | Reportar con IC 95 % |
| Interpretación | 0,2 pequeño, 0,5 mediano, 0,8 grande (orientativo). Con grupos de 10 a 15 personas el IC es muy ancho: si incluye 0, no se puede afirmar efecto. Es descriptivo, no una prueba de hipótesis |

### Recorrido de la ruta

| Métrica | Cálculo | Tabla | Meta |
| --- | --- | --- | --- |
| Aprobación al primer intento | % de pasos con intentos cuyo primer intento aprobó | `assessment_attempts` (intento 1 del quiz del tema) unida a `path_steps`; vista `v_path_step_metrics` | Entre 60 % y 85 % |
| Intentos por tema | Media de `attempts_used` en los pasos aprobados | `path_steps` | ≤ 1,8 |
| Dominio por tema | % de pasos con mejor nota ≥ 70 | `path_steps.best_score` | Reportar por tema |
| Finalización y certificación | % de inscripciones con `status = 'completed'` y % con insignia | `enrollments`, `badges` | Finalización ≥ 60 % |
| Abandono | Primer tema sin terminar (`pending`, `in_progress`, `blocked`, `on_hold`) de cada inscripción con `status = 'abandoned'` | `path_steps` | Identificar temas críticos |
| Percepción | Media de cada escala Likert (1 a 5) | `survey_responses.likert` | Media ≥ 4 |
| Tiempo en tarea | Minutos por tema y por ruta | `interaction_events` | Reportar. **Pendiente en el cuaderno**: depende del contrato de eventos de la interfaz |
| Retención (opcional) | Nota del post-test diferido (2 a 4 semanas) | `assessment_attempts` (`retention`) | Reportar. Solo si hay segunda medición |

Una aprobación al primer intento por encima de 85 % indica quizzes demasiado fáciles; por debajo de
60 %, demasiado difíciles o un diagnóstico que ubica mal.

### Equidad

Tasa de aprobación al primer intento por nivel de inglés (`user_profiles.languages`) y por tener o no
hoja de vida (`resume_completed_at`). No tiene meta: una diferencia grande entre grupos señala que
el contenido o el recomendador favorece a alguno (sección 4.2 del plan).

## Convenciones de las funciones

- Entrada vacía o series de largo distinto: `ValueError` (no hay valor razonable).
- División por cero con un valor límite natural: se devuelve y se documenta (kappa con una sola
  etiqueta común: 1,0; F1 con ambos conjuntos vacíos: 1,0; punto-biserial sin variación: 0,0).
- Sin valor natural: `None` (Hake con `pre = 100`) o `ValueError` (AUC con una sola clase).
- El bootstrap usa `random.Random(seed)`: mismo resultado para la misma semilla.

## Límites que hay que decir al reportar

- Con 15 a 30 participantes, todas las estimaciones tienen intervalos amplios; se reporta el n junto
  a cada valor y se evita hablar de «significancia».
- Las comparaciones entre brazos solo valen si el sorteo con semilla se hizo antes del inicio del
  piloto (AD4) y `analysis_included` marca a quienes entran al análisis.
- Si se complementa con estudiantes simulados (`eval.simulate_learner`), sus resultados se reportan
  aparte y nunca se mezclan con los de personas reales.
