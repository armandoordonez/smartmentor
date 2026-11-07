# ADR 0013: Fragmentos RAG y fuentes en tablas de Liquibase (cierra D-04)

* **Estado:** Propuesto. Lo cierran la Fase 2 (tablas) y la Fase 5 (RAG), con las fuentes y licencias de DEF-08
* **Fecha:** 2026-11-07
* **Autor:** eduar.troyano
* **Fuente:** [plan de implementación v3](../../PLAN_IMPLEMENTACION_V3.md), secciones 5.2.1, 5.4.7, 15 (B-04) y DEF-08; [`proyecto/decisiones-pendientes.md`](../../proyecto/decisiones-pendientes.md), D-04
* **Relacionados:** [ADR 0002](0002-liquibase-schema-versioning.md), [ADR 0009](0009-data-ownership-api-and-ai.md), [ADR 0012](0012-embedding-model-and-dimension.md)

---

## 1. Contexto

El brief pide RAG sobre libros abiertos y apuntes del instructor, y sugiere LlamaIndex. El pendiente D-04 señaló el conflicto: `PGVectorStore` de LlamaIndex crea sus propias tablas, mientras el ADR 0002 exige que **todo el esquema lo gestione Liquibase**. Además, la fidelidad del contenido (métrica del brief) necesita saber de qué fuente salió cada fragmento y con qué licencia.

## 2. Decisión

1. **Dos tablas creadas por Liquibase y escritas solo por `ai/`** ([ADR 0009](0009-data-ownership-api-and-ai.md)):
   - `source_documents`: `course_id`, `title`, `url`, `license`, `sha256`;
   - `document_chunks`: `source_document_id`, `chunk_index`, `text`, `token_count`.
2. **El vector del fragmento va en `ai_embeddings`** con `owner_type = chunk` ([ADR 0012](0012-embedding-model-and-dimension.md)), no en `document_chunks`.
3. **Sin `_audit`** en `document_chunks` (volumen alto y regenerable desde la fuente; justificado en el [ADR 0007](0007-schema-rebase-v2.md)).
4. **Fragmentación como el notebook:** unos 900 caracteres por párrafo. **Recuperación top-k = 4** por coseno en pgvector, con una consulta SQL.
5. **LlamaIndex no se usa en el MVP.** Se puede agregar después detrás del mismo puerto sin que cree tablas.
6. **Fuentes registradas con su licencia** (DEF-08: apuntes del instructor y libros abiertos). El texto recuperado va entre delimitadores en el prompt y se trata como dato (inyección de prompts, plan 5.4.12).

## 3. Alternativas descartadas

- **LlamaIndex con `PGVectorStore` creando sus tablas:** rompe el ADR 0002 y deja tablas sin versionar ni rollback.
- **Un almacén vectorial aparte:** contradice la decisión de una sola base relacional y vectorial (ADR 0001).
- **Configurar LlamaIndex para usar tablas de Liquibase (propuesta original de D-04):** viable, pero agrega una dependencia grande para lo que es una consulta SQL.

## 4. Consecuencias

- **Positivas:** todo el esquema sigue en Liquibase; la recuperación es una consulta legible y fácil de probar; la licencia y el origen de cada fragmento quedan registrados para la fidelidad.
- **Negativas y pendientes:**
  - El código de fragmentación y recuperación es propio; si se necesitan técnicas avanzadas (re-ranking, consultas híbridas), hay que implementarlas o incorporar LlamaIndex detrás del puerto.
  - Las fuentes reales y sus licencias las entrega el validador del curso (DEF-08, Fase 5).
  - El brief menciona LlamaIndex: el cambio se registra en el brief v2 (B-04).
