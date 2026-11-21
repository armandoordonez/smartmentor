# Anexo D · Experimentos de la cohorte 1

Índice de los experimentos que la cohorte alcanzó, los que no y lo que cada uno concluye. Es el soporte de la [sección 10 del brief de la cohorte](../../../proyecto/cohorte_1/brief.md#10-evaluación-métricas-y-resultados). Las definiciones de las métricas están en [`docs/cohorte_1/evaluation/metrics.md`](../evaluation/metrics.md) y el plan en [`PLAN_EXPERIMENTOS_R005.md`](../evaluation/plan-experimentos-r005.md).

> **Dos advertencias de lectura.** (1) Los códigos de experimento (E2, E3, E5…) **no** son los códigos de pantalla de Figma (E1 a E15 del aprendiz): son listas distintas. (2) Todos los resultados usan **jueces-agente** (Claude Opus y Sonnet), a ciegas y sobre datos de prueba: son indicativos, no equivalen a expertos humanos ni a un piloto.

## 1. Experimentos alcanzados

| Experimento | Qué mide | Cómo se hizo | Resultado | Meta | Cumple | Documento |
| --- | --- | --- | --- | --- | --- | --- |
| E2 | Estructuración del syllabus | 12 extracciones (syllabus reales, dos modelos) frente al grafo que dejó el instructor | F1 de temas 1,000; de prerrequisitos 0,694 (`flash-lite`) y 0,578 (`flash`) | F1 ≥ 0,85 | ✔ temas · ✖ prerrequisitos | [e2](../evaluation/results/e2-2026-11-16.md) |
| E3 | Calidad de las preguntas | 80 ítems al azar de 4 cursos, dos jueces a ciegas con rúbrica de 4 criterios | 28,8 % válidas con ambos; κ 0,704. Falla casi siempre `plausible_distractors` | ≥ 80 % y κ ≥ 0,6 | ✖ calidad · ✔ acuerdo | [e3](../evaluation/results/e3-2026-11-16.md) |
| E3b | Calidad tras B-062 | 40 ítems por brazo generados fuera de línea, antes y después de `topic_quiz` v2 con formato y mezcla en código | 32,5 % → 60,0 % válidas; correcta repartida en las 4 posiciones; κ 0,264 | ≥ 80 % y κ ≥ 0,6 | ✖ (mejora) | [e3b](../evaluation/results/e3b-2026-11-16.md) |
| E3c | `topic_quiz` v3 frente a v2 | 30 ítems por brazo y jueces con una instrucción de calibración común | 26,7 % → 30,0 %; claves erróneas de 4/4 a 0/1; κ 0,452. Dentro del ruido | ≥ 80 % y κ ≥ 0,6 | ✖ (mejora pequeña) | [e3c](../evaluation/results/e3c-2026-11-16.md) |
| E5 | Fidelidad del RAG con y sin lecturas | Curso 2, 3 temas, regeneración con solo el syllabus y con 5 lecturas | Fidelidad media 0,889 (ETL/ELT: 0,667). Las lecturas no entraron al top-4: comparación sin concluir | ≥ 0,8 | ✔ media | [e5](../evaluation/results/e5-2026-11-16.md) |
| E5b | E5 con `AI_RAG_TOP_K` = 10 | Misma base con 10 fragmentos | Entran 4 de 30 fragmentos de lecturas; fidelidad 0,919 (solo syllabus) y 0,974 (con lecturas), con una generación por celda: sin concluir | ≥ 0,8 | ✔ media · sin concluir | [e5b](../evaluation/results/e5b-2026-11-16.md) |
| E6 | Videos recomendados por tema | Candidatos de YouTube re-ordenados, juzgados a ciegas | P@3 0,718; κ 0,766 | P@3 ≥ 0,7 | ✔ | [e6](../evaluation/results/e6-2026-11-16.md) |
| E7 | Juez del sistema frente a un juez de referencia | Respuestas cortas calificadas por Gemini y por un juez Claude | QWK 0,998, con muestra polarizada (casi sin respuestas parciales) | QWK ≥ 0,6 | ✔ con salvedad | [e7](../evaluation/results/e7-2026-11-16.md) |
| E8 | Desempeño técnico y costo | Log real del LLM | p95 de generación 120,1 s; calificación 2,1 s; cierre del diagnóstico 9,2 s; JSON inválido 0,8 %; US$ 1,85 en 372 llamadas | p95 < 20 s y JSON < 2 % | ✖ generación · ✔ camino del aprendiz · ✔ JSON | [e8](../evaluation/results/e8-2026-11-15.md) |
| Cohorte de desarrollo | Métricas de los aprendices | Cuaderno sobre la base real, 9 inscripciones de 3 personas | Hake −0,109; SUS 80,7; finalización 77,8 % (no afirman efectos) | Ver brief base | Solo comprueba el cálculo | [metrics-cohort1](../evaluation/results/metrics-cohort1-2026-11-15.md) |

Resumen en una sola página: [`resumen-r005-2026-11-16.md`](../evaluation/results/resumen-r005-2026-11-16.md).

## 2. Experimentos no alcanzados

| Experimento | Qué mide | Por qué no se alcanzó |
| --- | --- | --- |
| E4 | Validez del diagnóstico (AUC ≥ 0,7) | Necesita los datos del piloto. Con la cohorte de desarrollo el AUC fue 0,635 sobre 14 pares |
| E9 | Prueba con 5 o 6 empleados (g ≥ 0,3 y SUS ≥ 68) | Es parte del piloto con usuarios reales |
| E10 | Revisión del reporte con la organización | Depende de E9 y del interlocutor |
| E11 | Piloto comparativo con grupo de control (unos 175 por brazo) | Fase posterior |
| Calibración humana de E3, E6 y E7 | Contraste de los jueces-agente con una persona | Requiere a una persona: las hojas ciegas de 15 elementos por experimento están preparadas |
| E5 concluyente | Efecto de las lecturas en la fidelidad | Faltan 3 a 5 repeticiones por condición, más temas y un verificador independiente |
| E7 con respuestas parciales | Comportamiento del juez fuera de los extremos | La muestra salió polarizada: 58 de 60 respuestas eran 0 o 100 |

## 3. Costo y reproducibilidad

- Los experimentos costaron unos US$ 0,16 de IA de un tope de US$ 3 hasta E7, más lo de E5b (US$ 0,128) y de B-062 (entre US$ 1,6 y 2,3, con los jueces estimados y no medidos).
- Los datos de cada experimento, las colas ciegas y las claves están en la máquina de quien los ejecutó (no se versionan: contienen syllabus reales). Los resultados y el método sí están en `docs/cohorte_1/evaluation/results/`.
- Las cuentas y los recursos creados para los experimentos llevan el prefijo `experimento_`.
