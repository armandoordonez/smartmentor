# ADR 0015: Banco de ítems pre-generado y revisado

* **Estado:** Propuesto. Lo cierra DEF-09 (decide el director; cambio moderado B-02 del brief) antes de la Fase 2
* **Fecha:** 2026-11-07
* **Autor:** eduar.troyano
* **Fuente:** [plan de implementación v3](../../PLAN_IMPLEMENTACION_V3.md), secciones 3.5 (L-02, L-03, L-10), 5.2.1, 5.4.3, 15.1 (B-02) y DEF-09
* **Relacionados:** [ADR 0008](0008-ai-service-architecture.md), [ADR 0010](0010-async-jobs-postgres-pull-ingestion.md), [ADR 0011](0011-llm-provider.md)

---

## 1. Contexto

El brief pide «preguntas regeneradas en cada intento» para que no se memorice la misma pregunta. Generar con el LLM en el momento del intento tiene problemas:

- el aprendiz espera al LLM y la meta de latencia no se cumple;
- nadie revisa las preguntas antes de que las vea el aprendiz, aunque la pantalla E8 promete preguntas «revisadas por tu instructor»;
- la psicometría (dificultad, discriminación, κ entre anotadores) necesita comparar el mismo ítem entre aprendices;
- el costo crece por aprendiz y no por tema.

El notebook ya genera el quiz desde los resultados de aprendizaje, sin el texto de estudio (L-02), y tiene un prompt de revisión que descarta ítems sin una sola respuesta correcta (L-03).

## 2. Decisión

1. **Banco de ítems en `assessment_items`**, generado al publicar el curso y revisado por el instructor: `topic_id`, `learning_outcome_id`, `source` (`diagnostic`, `topic_quiz`, `final`, `retention`), `item_type` (`multiple_choice`, `short_answer`), `bloom_level`, `difficulty`, `stem`, `options`, `correct_option`, `model_answer`, `rubric`, `equivalence_group`, `review_status`, `auto_review`, `prompt_version` y `ai_job_id`.
2. **Cada intento toma ítems que el aprendiz no ha visto** sobre los mismos resultados de aprendizaje; los ítems usados quedan en `assessment_attempts.item_ids` y las respuestas en `attempt_answers`.
3. **Tareas de `ai/`:** `diagnostic.generate_items`, `items.generate_quiz_bank`, `items.generate_final_bank` (con `equivalence_group` para el pre-test y el post-test) e `items.review`, que corre antes de que el instructor vea el banco.
4. **Tamaño inicial:** 3 intentos × 5 ítems × 1,5 de margen ≈ 23 ítems por tema.
5. **Si el banco se agota**, `items.generate_quiz_bank` corre bajo demanda y la API responde 202 (U1b).
6. **Opción múltiple calificada por regla;** respuesta corta con el LLM como juez a temperatura 0 y rúbrica literal; regla de aprobación configurable (por defecto 2 de 3 criterios, DEF-21).

## 3. Alternativas descartadas

- **Generar por intento y guardar en caché:** cumple la letra del brief, pero el aprendiz espera al LLM, el instructor no revisa antes y los ítems no se comparan entre aprendices.
- **Banco sin revisión humana:** más rápido, pero contradice lo que promete E8 y la validez que mide el brief (% de preguntas válidas).

## 4. Consecuencias

- **Positivas:** el intento no espera al LLM; el instructor revisa antes de publicar; la anotación ciega (κ), la dificultad y la discriminación se calculan sobre ítems compartidos; el costo es por tema; los ítems equivalentes permiten una ganancia de Hake válida (L-10).
- **Negativas y pendientes:**
  - Hay que generar y revisar unos 23 ítems por tema y curso antes de abrir la ruta.
  - Un tema con pocos resultados de aprendizaje repite más.
  - La intención del brief (no memorizar la pregunta) se conserva, pero el texto cambia: se registra en el brief v2 (B-02).
