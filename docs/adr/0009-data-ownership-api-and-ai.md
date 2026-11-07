# ADR 0009: Propiedad de los datos: la API escribe el negocio y `ai/` sus tablas

* **Estado:** Propuesto. Lo cierra DEF-12 (valor por defecto del plan) con la aprobación de los contratos de la Ola 0, antes de la Fase 2
* **Fecha:** 2026-11-07
* **Autor:** eduar.troyano
* **Fuente:** [plan de implementación v3](../../PLAN_IMPLEMENTACION_V3.md), secciones 0 (punto 5 de la recomendación), 5.2.1, 5.2.4, 5.3.3 y DEF-12
* **Relacionados:** [ADR 0008](0008-ai-service-architecture.md), [ADR 0010](0010-async-jobs-postgres-pull-ingestion.md), [ADR 0019](0019-least-privilege-db-users.md)

---

## 1. Contexto

Con dos servicios (la API y `ai/`) sobre la misma base PostgreSQL, cualquiera de los dos podría escribir cualquier tabla. Si `ai/` escribiera directamente temas, ítems o recursos:

- las reglas de negocio (estados, revisión del instructor, pertenencia) quedarían repartidas en dos servicios;
- la auditoría (`_audit`) registraría cambios hechos fuera de la API;
- dos escritores sobre la misma fila podrían pisarse.

## 2. Decisión

1. **Un escritor por tabla.**
   - **La API** escribe todas las tablas de negocio (usuarios, cursos, temas, rutas, inscripciones, ítems, recursos, videos, piloto, encuestas, alertas, eventos).
   - **`ai/`** escribe solo sus tablas: `ai_jobs`, `ai_generation_cache`, `ai_embeddings`, `source_documents`, `document_chunks` y `llm_call_logs`.
2. **`ai/` lee lo que necesita** de las tablas de negocio: `topics`, `learning_outcomes`, `courses` y `syllabus_documents`.
3. **Los resultados de `ai/` entran al negocio por la API:** la API valida el resultado del trabajo contra el contrato y lo escribe en sus tablas en una transacción idempotente ([ADR 0010](0010-async-jobs-postgres-pull-ingestion.md)).
4. **La API solo lee** `llm_call_logs`, `ai_jobs` y las vistas, para los tableros (AD2, AD3).
5. **La regla se hace cumplir en la base** con usuarios de mínimo privilegio (`smartmentor_api` y `smartmentor_ai`, [ADR 0019](0019-least-privilege-db-users.md)), no solo por convención.

## 3. Alternativas descartadas

- **`ai/` escribe directamente las tablas de negocio:** más rápido de construir, pero duplica reglas y deja el estado del negocio fuera del control de la API.
- **`ai/` llama a la API para escribir (modelo push):** exigiría que `ai/` tenga credenciales para llamar a la API y que la API exponga endpoints de escritura internos. Se prefiere que la API consulte e ingiera (ADR 0010).
- **Bases separadas por servicio:** aislamiento total, pero impide las consultas conjuntas que necesita la IA (temas y resultados de aprendizaje) y complica el entorno de una cohorte.

## 4. Consecuencias

- **Positivas:** las reglas de negocio y la auditoría viven en un solo lugar; los permisos de la base lo verifican; la ingesta es idempotente.
- **Negativas y pendientes:**
  - La API debe implementar la ingesta de cada tipo de trabajo (un traductor por contrato).
  - Hay una latencia extra entre que `ai/` termina y la API ingiere (consulta cada 2 s o barrido cada 60 s).
  - Si DEF-12 cambia, cambian los permisos del ADR 0019.
