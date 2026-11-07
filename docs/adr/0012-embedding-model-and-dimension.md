# ADR 0012: Modelo de embeddings y dimensión (cierra D-01)

* **Estado:** Aceptado (DEF-02, decidido por el dueño el 2026-11-07), con la dimensión **768 provisional**: se confirma en P-05 antes de la Fase 5
* **Fecha:** 2026-11-07
* **Autor:** eduar.troyano
* **Fuente:** [plan de implementación v3](../../PLAN_IMPLEMENTACION_V3.md), secciones 3.2, 5.2.5, 5.4.7, 18.1 (G-09), 18.9 y DEF-02; [`proyecto/decisiones-pendientes.md`](../../proyecto/decisiones-pendientes.md), D-01
* **Relacionados:** [ADR 0001](0001-postgres-pgvector.md) (sección 7), [ADR 0007](0007-schema-rebase-v2.md), [ADR 0011](0011-llm-provider.md), [ADR 0013](0013-rag-chunks-in-liquibase-tables.md)

---

## 1. Contexto

SmartMentor usa embeddings para comparar la descripción del aprendiz con cada tema, para recuperar fragmentos de apuntes (RAG) y para ordenar videos. Todos esos vectores se comparan entre sí, así que **deben salir del mismo modelo**.

- D-01 dejó un valor provisional de `vector(1024)` y recomendaba `bge-m3`.
- El notebook v2 del Mago de Oz usa `gemini-embedding-001` con `EMBED_DIM = 768`, `task_type` distinto para documentos y consultas y normalización L2.
- La columna `vector(N)` se escribe en la Fase 2 (G-09): la dimensión no puede esperar a la Fase 5.
- pgvector 0.8.7 indexa con HNSW hasta 2000 dimensiones en `vector` (ADR 0001).

## 2. Decisión

1. **Modelo:** el de embeddings que trae el notebook v2 (de la misma familia que el LLM de [ADR 0011](0011-llm-provider.md)). Un solo proveedor para LLM y embeddings.
2. **Dimensión: 768** en `ai_embeddings.embedding vector(N)`, con `N = EMBEDDING_DIMENSION`. **El 1024 provisional de D-01 se descarta.**
3. **Los vectores viven en una tabla propia, `ai_embeddings`** (`owner_type` en `topic`, `profile`, `video` o `chunk`; `owner_id`; `model`; `embedding`; `content_sha256`), con índice HNSW `vector_cosine_ops`. Salen `topics.embedding` y `enrollments.profile_embedding` ([ADR 0007](0007-schema-rebase-v2.md)).
4. **La columna `model` impide comparar vectores de modelos distintos.**
5. **Puerto `EmbeddingProvider.embed(texts, purpose)`**, con `purpose` en `document`, `query` o `similarity`; configuración en `.env`: `AI_EMBEDDING_PROVIDER`, `AI_EMBEDDING_MODEL` y `EMBEDDING_DIMENSION` (vacías en el ejemplo).
6. **Cambiar de modelo** cuesta un changeset que altera la columna y recrea el índice, más un trabajo `embeddings.reindex`: los vectores se regeneran desde el texto.

## 3. Alternativas descartadas

- **`bge-m3` a 1024 (recomendación de D-01):** costo cero y reproducible, pero exige operar un modelo propio y no coincide con el notebook.
- **`text-embedding-3-large` (OpenAI), propuesto por el dueño:** valorado en el plan (18.9) como no pertinente para el MVP: un segundo proveedor, una segunda clave y un segundo tercero que recibe texto de los aprendices; su dimensión natural (3072) no cabe en un índice HNSW con `vector` sin reducirla; la diferencia de calidad en español no lo justifica. Se puede probar después por el mismo puerto (por ejemplo, con `dimensions=768`), pero **antes de indexar** hay que elegir un solo modelo.
- **Mantener vectores en las tablas de negocio:** acopla la dimensión a varias tablas y mezcla escritores ([ADR 0009](0009-data-ownership-api-and-ai.md)).

## 4. Consecuencias

- **Positivas:** se reutilizan el código y la clave del notebook; 768 cabe con holgura en HNSW y ocupa menos que 1024; un solo lugar para todos los vectores.
- **Negativas y pendientes:**
  - La sección 7 del ADR 0001 (dimensión provisional 1024) queda superada por este ADR.
  - P-05: verificar el modelo vigente y su dimensión antes de la Fase 5; si cambia, changeset y reindexado.
  - La lectura de la respuesta del dueño (modelo del notebook frente a `text-embedding-3-large`) quedó «por confirmar» en `proyecto/decisiones-pendientes.md` (18.4). Si el dueño elige otro modelo, este ADR se reemplaza antes de indexar.
