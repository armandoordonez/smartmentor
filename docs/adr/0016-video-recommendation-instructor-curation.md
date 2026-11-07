# ADR 0016: Recomendación de videos por tema con curaduría del instructor

* **Estado:** Propuesto. Lo cierran DEF-07 (fuente y licencia de videos y transcripciones) y la Fase 5; requiere verificar las condiciones de la API de YouTube (P-06)
* **Fecha:** 2026-11-07
* **Autor:** eduar.troyano
* **Fuente:** [plan de implementación v3](../../PLAN_IMPLEMENTACION_V3.md), secciones 3.5 (L-08, L-09), 4 (informe de sistemas recomendadores), 5.2.1, 5.4.9, 15 (B-08) y DEF-07
* **Relacionados:** [ADR 0008](0008-ai-service-architecture.md), [ADR 0012](0012-embedding-model-and-dimension.md)

---

## 1. Contexto

El brief pide reordenar videos de YouTube por similitud entre la transcripción y el tema, y medir P@3 y nDCG@3 con juicio de expertos. Hay tres insumos:

- el notebook v2 reordena por coseno usando solo título y descripción, con filtro de 4 a 30 minutos (L-09); sin clave de YouTube ni lista del instructor, el tema queda sin video (L-08);
- Figma v3 agrega curaduría (D5e), calidad de videos (D5f) y retroalimentación del aprendiz (E6);
- un informe de otra materia propone un recomendador híbrido **por aprendiz** con TF-IDF, evaluado con datos simulados (plan 4).

La API de YouTube restringe la descarga de subtítulos; sus términos no se verificaron (P-06).

## 2. Decisión

1. **Ranking por tema, compartido entre aprendices**, como pide el brief y como permite la caché por tema.
2. **Cadena:** `VideoSearchProvider` (YouTube Data API con `relevanceLanguage` y `videoEmbeddable`) → filtros de duración e idioma (configurables) → caracterización con la lista cerrada de subtemas del tema → embeddings ([ADR 0012](0012-embedding-model-and-dimension.md)) → puntaje = similitud con el tema más ajustes de idioma y duración → **top 3 para el instructor**.
3. **Transcripción detrás de un puerto (`TranscriptProvider`).** Por defecto, `metadata_transcripts` (título, descripción y capítulos); subtítulos solo si DEF-07 confirma que el uso es permitido. La fuente queda en `video_candidates.characterization_source`.
4. **Curaduría del instructor (D5e):** juicio «Pertinente / No pertinente» (`video_relevance_judgments`), «usar este», respaldos y videos agregados a mano (`origin = instructor`). **La lista de respaldo del instructor es obligatoria.**
5. **Tablas:** `video_candidates` (con `status` `candidate`, `in_use`, `backup`, `rejected`), `video_relevance_judgments` y `video_feedback`.
6. **El índice de calidad no se muestra al aprendiz antes de que califique** (C-08, sesgo de conformidad).
7. **P2:** índice de calidad bayesiano con la etiqueta «Midiendo» y reordenamiento por aprendiz (idioma y duración) entre los candidatos aprobados.

## 3. Alternativas descartadas

- **Recomendación por aprendiz según los conceptos que falló (informe):** el diagnóstico es por tema y resultado de aprendizaje, no por concepto, y el brief pide ranking por tema.
- **TF-IDF:** el proyecto ya tiene embeddings y pgvector; el propio informe recomienda pasar a embeddings.
- **Depender de subtítulos y comentarios de YouTube:** riesgo legal y de disponibilidad sin verificar.
- **Relevancia por calificación simulada:** el brief mide con juicio de expertos.

## 4. Consecuencias

- **Positivas:** ningún tema queda sin video (respaldo del instructor); la métrica P@3 y nDCG@3 sale de juicios reales; el costo es por tema.
- **Negativas y pendientes:**
  - Sin transcripción, la similitud se calcula con metadatos y puede ser menos precisa que lo que pide el brief.
  - Antes de calcular P@3 hay que medir el acuerdo entre dos expertos (κ).
  - El cambio frente al brief (curaduría y respaldos) se registra en el brief v2 (B-08).
