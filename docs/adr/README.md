# docs/adr/

Decisiones de arquitectura (ADR), una por archivo. Se numeran en orden (`NNNN-titulo.md`) y no se borran: una decisión reemplazada se marca como "Reemplazada por ADR NNNN".

Los ADR nuevos se escriben con la [plantilla](_template.md). Estados:

- **Propuesto:** redactado a partir del plan, pendiente de la decisión que se indica en su cabecera (definición DEF o fase).
- **Aceptado:** decidido por el dueño del proyecto.
- **Reemplazado:** sustituido por otro ADR, que se enlaza.

| ADR | Título | Estado |
| --- | --- | --- |
| [0001](0001-postgres-pgvector.md) | PostgreSQL 17 + pgvector como base de datos | Aceptado |
| [0002](0002-liquibase-schema-versioning.md) | Versionado del esquema con Liquibase | Aceptado |
| [0003](0003-api-domain-first-layout.md) | Organización del microservicio por dominio | Aceptado |
| [0004](0004-authentication-keycloak-bearer.md) | Autenticación con Keycloak y bearer tokens | Aceptado; complementado por 0014 |
| [0005](0005-keycloak-postgres-realm-versioned.md) | Keycloak sobre PostgreSQL y realm versionado | Aceptado; sección 3 modificada el 2026-11-07 |
| [0006](0006-frontend-streamlit.md) | Interfaz de usuario con Streamlit | Aceptado; complementado por 0017 |
| [0007](0007-schema-rebase-v2.md) | Re-base del esquema como `v2.0.0` | Aceptado |
| [0008](0008-ai-service-architecture.md) | Microservicio de IA (`ai/`): arquitectura, contrato y puertos | Propuesto (B-03) |
| [0009](0009-data-ownership-api-and-ai.md) | Propiedad de los datos: la API escribe el negocio y `ai/` sus tablas | Propuesto (DEF-12) |
| [0010](0010-async-jobs-postgres-pull-ingestion.md) | Trabajos asíncronos en PostgreSQL sin broker e ingesta por consulta | Propuesto (Fase 4) |
| [0011](0011-llm-provider.md) | Proveedor de LLM (cierra D-02) | Aceptado (DEF-01) |
| [0012](0012-embedding-model-and-dimension.md) | Modelo de embeddings y dimensión (cierra D-01) | Aceptado (DEF-02; 768 provisional) |
| [0013](0013-rag-chunks-in-liquibase-tables.md) | Fragmentos RAG y fuentes en tablas de Liquibase (cierra D-04) | Propuesto (Fases 2 y 5, DEF-08) |
| [0014](0014-service-to-service-auth-client-credentials.md) | Autenticación entre servicios con *client credentials* y endurecimiento de Keycloak | Propuesto (Fases 3 y 8; DEF-13 y DEF-27 ya decididas) |
| [0015](0015-pregenerated-item-bank.md) | Banco de ítems pre-generado y revisado | Propuesto (DEF-09) |
| [0016](0016-video-recommendation-instructor-curation.md) | Recomendación de videos por tema con curaduría del instructor | Propuesto (DEF-07) |
| [0017](0017-frontend-rebuilt-from-figma-v3.md) | Interfaz rehecha desde Figma v3 (complementa el ADR 0006) | Aceptado |
| [0018](0018-personal-data-protection.md) | Protección de datos personales: consentimiento, supresión y auditoría (Ley 1581) | Propuesto (DEF-05) |
| [0019](0019-least-privilege-db-users.md) | Usuarios de base de datos con mínimo privilegio (cierra D-05) | Propuesto (Fase 2) |
| [0020](0020-deployment-target.md) | Destino de despliegue (cierra D-06) | Propuesto (DEF-16) |
| [0021](0021-neutral-roles-and-label-glossary.md) | Roles neutros (`learner`, `instructor`, `admin`) y glosario de etiquetas | Aceptado (DEF-23) |

Las decisiones aún abiertas están en [`proyecto/decisiones-pendientes.md`](../../proyecto/decisiones-pendientes.md); la fuente de los ADR 0007 a 0021 es el [plan de implementación v3](../../PLAN_IMPLEMENTACION_V3.md).
