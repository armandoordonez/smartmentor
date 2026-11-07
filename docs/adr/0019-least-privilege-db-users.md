# ADR 0019: Usuarios de base de datos con mínimo privilegio (cierra D-05)

* **Estado:** Propuesto. Lo cierra la Fase 2 (bootstrap y changeset de permisos), con la propiedad de los datos del [ADR 0009](0009-data-ownership-api-and-ai.md)
* **Fecha:** 2026-11-07
* **Autor:** eduar.troyano
* **Fuente:** [plan de implementación v3](../../PLAN_IMPLEMENTACION_V3.md), secciones 5.2.3, 5.2.4, 5.6 (notebook de métricas) y Anexo D; [`proyecto/decisiones-pendientes.md`](../../proyecto/decisiones-pendientes.md), D-05
* **Relacionados:** [ADR 0001](0001-postgres-pgvector.md), [ADR 0002](0002-liquibase-schema-versioning.md), [ADR 0005](0005-keycloak-postgres-realm-versioned.md), [ADR 0007](0007-schema-rebase-v2.md), [ADR 0018](0018-personal-data-protection.md)

---

## 1. Contexto

Hoy Liquibase y la API usan el mismo usuario dueño (`POSTGRES_USER`). Con ese usuario, un error o una inyección en la API podría alterar el esquema o borrar la auditoría. La arquitectura v3 suma un segundo servicio que escribe en la base (`ai/`) y un notebook de métricas que solo lee. D-05 proponía separar un dueño y un usuario de la aplicación; el [ADR 0009](0009-data-ownership-api-and-ai.md) fija qué tablas escribe cada servicio.

## 2. Decisión

1. **Cuatro usuarios en la base `smartmentor`:**

   | Usuario | Lo usa | Permisos |
   | --- | --- | --- |
   | `smartmentor_owner` | Liquibase | Dueño del esquema: crea y altera objetos |
   | `smartmentor_api` | API | Lectura y escritura en las tablas de negocio; solo lectura en `llm_call_logs`, `ai_jobs` y las vistas |
   | `smartmentor_ai` | `ai/` y `ai-worker` | Escritura en las tablas `ai_*`, `document_chunks`, `source_documents` y `llm_call_logs`; lectura de `topics`, `learning_outcomes`, `courses` y `syllabus_documents` |
   | De solo lectura | Notebook de métricas | `SELECT` sobre las tablas y vistas que calculan las métricas |

2. **Los usuarios se crean en el bootstrap** (`database/bootstrap/`) y **los permisos se otorgan en un changeset** de `v2.0.0` (`0xx-db-roles-grants.xml`), con rollback.
3. **Ningún usuario de servicio puede alterar el esquema** ni escribir en las tablas `_audit` fuera del trigger; la purga de supresión usa un procedimiento con permiso explícito ([ADR 0018](0018-personal-data-protection.md)).
4. **Credenciales en `.env`** (variables nuevas, vacías en `.env.example`), por ejemplo `AI_DATABASE_USER` y `AI_DATABASE_PASSWORD`. El compose se niega a arrancar si falta una obligatoria.
5. **La base `keycloak` y su rol no cambian** (ADR 0005).

## 3. Alternativas descartadas

- **Un solo usuario dueño para todo:** es lo actual; aceptable en desarrollo, no con datos reales.
- **Dos usuarios (dueño y aplicación), como proponía D-05:** no separa a `ai/` de la API, así que la propiedad de los datos quedaría solo como convención.
- **Seguridad por filas (RLS):** más fina, pero la autorización por pertenencia ya la hace la API y el costo de mantener políticas no se justifica en el MVP.

## 4. Consecuencias

- **Positivas:** la regla de un escritor por tabla la verifica la base; un fallo en un servicio no altera el esquema; el notebook no puede modificar datos.
- **Negativas y pendientes:**
  - Cada tabla nueva exige su `GRANT` en el changeset correspondiente; hay que verificarlo en la revisión.
  - Más variables y secretos que gestionar en `.env`.
  - En un servicio gestionado (ADR 0020) la creación de roles puede requerir pasos del proveedor.
