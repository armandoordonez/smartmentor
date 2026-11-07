# ADR 0007: Re-base del esquema como `v2.0.0`

* **Estado:** Aceptado (decisión del dueño del 2026-11-07, DEF-03)
* **Fecha:** 2026-11-07
* **Autor:** eduar.troyano
* **Fuente:** [plan de implementación v3](../../PLAN_IMPLEMENTACION_V3.md), secciones 5.2.1 a 5.2.3, 15 (B-05 y B-06) y DEF-03
* **Relacionados:** [ADR 0001](0001-postgres-pgvector.md), [ADR 0002](0002-liquibase-schema-versioning.md), [ADR 0005](0005-keycloak-postgres-realm-versioned.md), [ADR 0019](0019-least-privilege-db-users.md), [ADR 0021](0021-neutral-roles-and-label-glossary.md)

---

## 1. Contexto

El esquema vigente (`v1.0.0` con 19 changesets y 14 tablas, y `v1.0.1` con el administrador sembrado) se escribió para el prototipo de la Fase 0. El prototipo de Figma v3 y la prueba «Mago de Oz» exigen un modelo distinto:

- **13 de las 14 tablas cambian** y se agregan unas 20 (consentimiento, hoja de vida, banco de ítems, anotaciones, calificación humana, videos, piloto, trabajos de IA; plan 5.2.1).
- Varias columnas de `v1` desaparecen o pasan a tablas propias: `raw_syllabus`, `topics.learning_outcomes jsonb`, `topics.embedding`, `enrollments.profile_embedding`.
- **No hay datos que conservar:** las bases de cada PC solo tienen datos de prueba.
- La semilla de roles cambia de vocabulario (ADR 0021).

El ADR 0002 prohíbe editar un changeset aplicado. Hay dos caminos: evolucionar con `v1.1.0+` o rehacer el esquema como `v2.0.0`.

## 2. Decisión

1. **Se rehace el esquema como `v2.0.0`.** La evolución incremental empieza después, cuando haya datos del piloto.
2. **`v1.x` no se edita: se retira.** El maestro deja de incluir `v1.0.0` y `v1.0.1`, esos archivos se borran en el mismo commit y el último estado queda en git con la etiqueta `schema-v1-final`.
3. **Estructura de `database/liquibase/changelog/v2.0.0/`:** `001-extensions-and-timezone.xml`, `002-audit-function.xml`, un archivo por tabla (`NNN-create-table-<tabla>.xml`, con su `_audit`, secuencias y trigger), vistas, índices vectoriales, roles de base de datos ([ADR 0019](0019-least-privilege-db-users.md)), semillas de roles y del administrador, y `tag-v2.0.0`. Ids `v2.0.0-NNN-<accion>`, `logicalFilePath` fijo y rollback explícito (convenciones del ADR 0002).
4. **Reglas del modelo que se mantienen:** `id bigint` con secuencia propia, `active`, `created_at`, `<tabla>_audit` con trigger, `timestamptz`, nombres y `remarks` en inglés. **Se agrega `updated_at timestamptz`** a las tablas que cambian.
5. **Tablas sin `_audit`** (append-only o de volumen alto): `interaction_events`, `ai_generation_cache`, `ai_embeddings`, `document_chunks` y `llm_call_logs`.
6. **Vistas de solo lectura** para los tableros: `v_path_step_metrics`, `v_llm_cost_summary` y `v_item_validity`.
7. **Script `database/scripts/reset-app-schema.sh`:** termina las conexiones, borra y recrea `smartmentor` y `smartmentor_test`, ejecuta el bootstrap y `liquibase update`. **Nunca toca la base `keycloak` ni borra `database/data/postgres`**, pide confirmación y acepta `--yes`.
8. **Procedimiento:** respaldo con `backup.sh` (las dos bases), etiqueta `schema-v1-final`, re-base, y verificación con `liquibase update-testing-rollback` y la preparación de la base de pruebas. Vaciar la base local de cada PC requiere la autorización del dueño.

## 3. Alternativas descartadas

- **Evolucionar `v1.1.0+`:** respeta igual la regla de no editar changesets, pero exige unos 45 changesets (ALTER, cambios de CHECK, migración de `jsonb` a tablas, renombres con expandir y contraer) para migrar datos que nadie necesita. El historial quedaría con columnas que nacen y mueren, más difícil de leer para la cohorte siguiente.
- **Editar los changesets de `v1.0.0`:** viola el ADR 0002 (Liquibase detecta el cambio de checksum y se detiene).

## 4. Consecuencias

- **Positivas:**
  - Unos 30 changesets escritos de una vez; un esquema que se lee de corrido.
  - Cada tabla nueva queda trazada a una pantalla o a una métrica del brief (Anexo A del plan).
  - La base `keycloak` y su realm no cambian (base aparte, ADR 0005); el administrador se vuelve a enlazar por correo verificado.
- **Negativas y pendientes:**
  - Cada PC debe vaciar su base `smartmentor` (datos de prueba) con el script de reinicio.
  - Los modelos SQLAlchemy y las pruebas de la API se reescriben contra el esquema nuevo (Fase 3).
  - La dimensión de `ai_embeddings.embedding` entra en el esquema desde la Fase 2 ([ADR 0012](0012-embedding-model-and-dimension.md)).
  - El brief describe 14 tablas y un esquema evolutivo; el cambio se registra en el brief v2 (B-05 y B-06).
