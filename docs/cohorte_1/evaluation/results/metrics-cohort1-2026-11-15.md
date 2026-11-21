# Métricas de la cohorte 1 con la base real (2026-11-15)

Primera ejecución de `notebooks/metrics_cohort1.ipynb` contra la base compartida (Neon), con el usuario de **solo lectura** `smartmentor_metrics`, el 2026-11-15, después de que el changeset 004 le diera `SELECT` sobre `interaction_events`. Las definiciones, fórmulas y metas son las de [metrics.md](../metrics.md). Este archivo solo trae agregados: no hay correos, nombres ni ids de personas, y el cuaderno ejecutado con la base real no se versiona.

## Lectura honesta de la cohorte

Esta es una **cohorte de desarrollo**: aprendices de prueba y estudiantes simulados, no el piloto. Los números sirven para comprobar que el cálculo funciona con datos reales y para ver qué falta, **no** para afirmar que el sistema cumple o no cumple una meta.

| Dato de la cohorte | Valor |
| --- | --- |
| Inscripciones en la base | 16 (9 marcadas `analysis_included`) |
| Personas distintas entre las 9 inscripciones analizadas | 3 |
| Estado de las 9 analizadas | 7 completadas, 2 en la ruta, 0 abandonadas |
| Brazo del piloto (`pilot_arm`) | Vacío en todas: no hubo sorteo de brazos |
| Llamadas al LLM en el log | 372 (16 inscripciones con llamadas, más las de curso) |

Con 9 inscripciones de 3 personas, las métricas de estudiantes no son independientes entre sí y cualquier intervalo sería enorme. El estado de la tabla siguiente se lee así:

- **Cumple / No cumple:** el valor se calculó y se compara con la meta del brief. Es indicativo; el n va al lado.
- **Sin datos suficientes:** la fuente está vacía o el n queda por debajo de lo que la métrica exige (ítems con al menos 10 respuestas, al menos 3 candidatos por tema, más de 2 pares calificados).

## Métricas del sistema

| Métrica | Valor | n | Meta | Estado |
| --- | --- | --- | --- | --- |
| F1 de temas (syllabus) | 1,000 | 17 temas finales (4 cursos) | F1 ≥ 0,85 | Cumple (ver nota 1) |
| F1 de prerrequisitos (syllabus) | 1,000 | 18 prerrequisitos finales | F1 ≥ 0,85 | Cumple (ver nota 1) |
| % de preguntas válidas | Sin valor | 0 ítems anotados | ≥ 80 % | Sin datos suficientes |
| κ de Cohen del veredicto | Sin valor | 0 ítems con 2 expertos | κ ≥ 0,6 | Sin datos suficientes |
| Discriminación de ítems (mediana y % ≥ 0,2) | Sin valor | 0 ítems con ≥ 10 respuestas (172 respuestas calificadas en 123 ítems) | Discriminación ≥ 0,2 | Sin datos suficientes |
| Fidelidad media del texto generado | 0,807 | 14 recursos | ≥ 0,8 | Cumple por 0,007 (ver nota 2) |
| Precision@3 de videos | Sin valor | 1 juicio, 1 candidato, 0 temas con 3 candidatos | P@3 ≥ 0,7 | Sin datos suficientes |
| nDCG@3 de videos | Sin valor | Igual que P@3 | Reportar | Sin datos suficientes |
| QWK de la calificación automática (muestra aleatoria) | 0,923 | 2 pares | QWK ≥ 0,6 | Sin datos suficientes (ver nota 3) |
| AUC-ROC del diagnóstico | 0,635 | 14 pares (persona, tema) | AUC ≥ 0,7 | No cumple (indicativo) |
| Latencia p50 | 1,8 s | 370 llamadas al proveedor | Reportar | Reportado |
| Latencia p95 | 120,1 s | 370 llamadas al proveedor | < 20 s | No cumple (ver nota 4) |
| JSON inválido | 0,8 % | 372 llamadas (3 `invalid_output`, 0 con `json_valid = false`) | < 2 % | Cumple |
| Costo total | US$ 1,850 | 372 llamadas | Reportar | Reportado |
| Costo medio por inscripción | US$ 0,040 | 16 inscripciones con llamadas | Reportar | Reportado |
| SUS medio | 80,7 (mediana 82,5) | 7 encuestas | SUS ≥ 68 | Cumple (indicativo) |

Notas:

1. El F1 es perfecto porque lo que dejó el instructor coincide con la salida de la IA en los 4 cursos con extracción vigente. Puede ser que el instructor no editó nada (cursos de prueba), así que no mide aún cuánto trabajo evita la IA.
2. La media apenas pasa la meta y 7 de los 14 recursos están bajo 0,8 (mínimo 0,5). Con 14 recursos, el margen de 0,007 no distingue cumplir de no cumplir.
3. Las dos filas de `human_gradings` son de la muestra aleatoria; no hay solicitudes del aprendiz. Con 2 pares y 5 niveles ordinales el kappa no es estable.
4. La latencia incluye los intentos fallidos (59 llamadas con `status = error`, 28 de ellas con más de 100 s, o sea timeouts). Solo con las 308 llamadas exitosas el p95 sigue en 71,5 s y el p50 en 1,7 s. Las tareas lentas son `items.generate_quiz_bank` (p95 120,4 s), `items.generate_final_bank` (120,9 s), `diagnostic.generate_items` (120,1 s) y `content.explain_topic` (78,9 s). El detalle por tarea, curso y momento está en [e8-2026-11-15.md](e8-2026-11-15.md).

## Métricas de los estudiantes

| Métrica | Valor | n | Meta | Estado |
| --- | --- | --- | --- | --- |
| Ganancia de Hake media (por persona) | −0,109 | 7 inscripciones con pre y post | g ≥ 0,3 | No cumple (indicativo, ver nota 5) |
| d de Cohen (personalizada frente a ruta fija) | Sin valor | 0 por brazo | Reportar con IC 95 % | Sin datos suficientes (ver nota 6) |
| Aprobación al primer intento | 57,1 % | 14 pasos con intento | 60 % a 85 % | No cumple (indicativo; 8 de 14) |
| Intentos hasta aprobar (media) | 1,33 | 12 pasos aprobados | ≤ 1,8 | Cumple |
| Finalización | 77,8 % | 9 inscripciones | ≥ 60 % | Cumple (indicativo) |
| Con insignia | 77,8 % | 9 inscripciones | Reportar | Reportado |
| Likert: satisfacción (q1) | 4,43 | 7 encuestas | Media ≥ 4 | Cumple (indicativo) |
| Likert: utilidad percibida (q2) | 4,57 | 7 encuestas | Media ≥ 4 | Cumple (indicativo) |
| Likert: autoeficacia (q3) | 4,43 | 7 encuestas | Media ≥ 4 | Cumple (indicativo) |
| Temas omitidos por persona | 2,33 (21 de 42 pasos) | 9 inscripciones | Reportar | Reportado |
| Minutos ahorrados por persona | Sin valor | 9 inscripciones | Reportar | Sin datos suficientes (ver nota 7) |
| Tiempo en tarea (m27) | Sin valor | 0 eventos en inscripciones analizadas | Reportar | Sin datos suficientes (ver nota 8) |
| Abandono | 0 abandonos | 0 inscripciones abandonadas | Identificar temas críticos | Sin datos suficientes |
| Retención (opcional) | Sin valor | 0 intentos `retention` | Reportar | Sin datos suficientes (no hay segunda medición) |

Notas:

5. La media del pre-test es 69,3 y la del post-test 89,6 (7 personas), pero la media de las ganancias por persona es negativa: unas pocas personas con un pre muy alto y un post menor tiran del promedio (Hake divide por el margen que queda). Además no se pudo confirmar que el diagnóstico y la evaluación final usen ítems equivalentes: el rol de métricas no tiene `SELECT` sobre `assessment_items` (`equivalence_group`). Sin esa equivalencia la ganancia no es comparable.
6. Las 9 inscripciones tienen `pilot_arm` vacío: no hay grupo de comparación, así que no hay d de Cohen ni ganancia por brazo. Eso exige el sorteo con semilla antes del piloto (AD4).
7. `topics.estimated_minutes` es nulo en los 17 temas activos, así que no hay minutos que sumar. El cuaderno antes mostraba 0,0 (la suma de nulos); ahora reporta «sin datos».
8. El rol de métricas ya lee `interaction_events` (hay 42 eventos), pero los 42 pertenecen a inscripciones con `analysis_included = false`; en las 9 analizadas hay 0 eventos de tramo. La regla de m27 no se pudo ejercitar con datos reales.

### Dominio por tema (9 inscripciones analizadas)

En los 14 temas con pasos en la ruta, el porcentaje de pasos con mejor nota ≥ 70 va de 0 % a 66,7 %, con unos 3 pasos por tema (42 pasos en 14 temas). Con ese n, la lista sirve para ver que el cálculo corre, no para decidir qué tema reforzar.

### Equidad (aprobación al primer intento)

| Grupo | n (pasos con intento) | Aprobación al primer intento |
| --- | --- | --- |
| Inglés B1 | 5 | 40,0 % |
| Inglés B2 | 3 | 100,0 % |
| Con hoja de vida | 8 | 62,5 % |
| Sin hoja de vida | 6 | 50,0 % |

Solo hay nivel de inglés en 8 de los 14 pasos y proviene de 3 personas. No se saca ninguna conclusión de equidad.

## Qué no se puede calcular todavía y por qué

| Métrica | Falta |
| --- | --- |
| Calidad de preguntas (% válidas y κ) | `item_annotations` está vacía: faltan las anotaciones de 2 expertos por ítem |
| Psicometría de ítems | Ningún ítem llega a 10 respuestas calificadas (172 respuestas en 123 ítems) |
| Videos (P@3, nDCG@3) | Hay 1 juicio sobre 1 candidato; se necesitan al menos 3 candidatos juzgados por tema |
| QWK | Solo 2 pares de la muestra aleatoria y ninguno de solicitudes del aprendiz |
| Ganancia de Hake comparable | No se verificó la equivalencia de ítems entre diagnóstico y final (sin permiso sobre `assessment_items`) |
| d de Cohen y comparación entre brazos | `pilot_arm` vacío en todas las inscripciones: no hay grupo de comparación |
| Tiempo en tarea (m27) | Los eventos existen pero ninguno es de una inscripción marcada para análisis |
| Minutos ahorrados | `topics.estimated_minutes` nulo |
| Abandono y retención | No hay inscripciones abandonadas ni segunda medición |
| Cualquier métrica «de piloto» | Solo 3 personas distintas y datos de prueba o simulados |

## Cambios al cuaderno y a las consultas que salieron de esta ejecución

La primera ejecución real falló y destapó errores de código (no de permisos ni de datos). Se corrigieron en `notebooks/metrics_data.py` y `notebooks/metrics_cohort1.ipynb`:

- **Forma real de `diagnostics.level_by_topic`:** es el `DiagnosticResult` (`{"level_by_topic": [{"topic_id", "test_score" de 0 a 100 o nulo, ...}], "overall_score", ...}`), no un objeto con el id del tema como clave y `test_score` entre 0 y 1. La consulta de ganancia y la comprobación de forma se ajustaron.
- **Forma real de `survey_responses.likert`:** las claves son `q1`, `q2` y `q3` (satisfacción, utilidad percibida y autoeficacia), no `satisfaction`, `usefulness` y `self_efficacy`.
- **JSON inválido:** `json_valid` es nulo cuando no aplica (error de red o tarea sin JSON) y el cuaderno lo contaba como inválido (35,2 %). Ahora usa la misma definición que la API de observabilidad (`json_valid` falso o `status = invalid_output`): 0,8 %.
- **Datos insuficientes:** las celdas que fallaban con tablas vacías o muy pequeñas (anotaciones, psicometría, videos con menos de 3 candidatos, QWK con menos de 2 pares, SUS, ganancia, eficiencia sin brazos ni minutos) ahora imprimen un aviso y registran la métrica como «sin datos» en el tablero, en vez de romper o dar un valor sin sentido.

El cuaderno guardado en el repositorio se volvió a ejecutar en modo de demostración (datos sintéticos, semilla fija); esos números siguen sin ser resultados del piloto.

## Cómo se ejecutó

Con el usuario `smartmentor_metrics` (solo lectura), la URL de conexión se armó en el entorno del proceso a partir de las variables del `.env` (`METRICS_DATABASE_*` y `DATABASE_*`) y se pasó como `METRICS_DATABASE_URL`; no se escribió en ningún archivo. Las consultas corren con `SET TRANSACTION READ ONLY`. La salida del cuaderno se guardó fuera del repositorio y solo se copiaron los agregados a este informe. Para repetirlo, ver `notebooks/README.md`.
