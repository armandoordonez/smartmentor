# ADR 0002: Versionado del esquema con Liquibase

* **Estado:** Aceptado
* **Fecha:** 2026-10-07
* **Autor:** eduar.troyano
* **Fuente:** [`proyecto/brief.md`](../../proyecto/brief.md), secciones "Modelo de datos principal" y "Gestión del proyecto y continuidad entre grupos"
* **Relacionados:** [ADR 0001](0001-postgres-pgvector.md), [estándar del microservicio](../../api/microservice-development-standard.md), [guía operativa](../../database/liquibase/README.md)

## 1. Contexto

El brief exige un entorno reproducible y un repositorio que cada cohorte reciba y reconstruya en días. El esquema de la base debe poder:

- reconstruirse desde cero en cualquier ambiente;
- evolucionar con trazabilidad (quién, cuándo, por qué);
- revertirse si un cambio falla.

El estándar del microservicio prohíbe migraciones dentro de la API (sin Alembic, sin `create_all`). Por eso el esquema necesita un mecanismo propio.

## 2. Decisión

1. **Liquibase 5.0.4** gestiona todo cambio de esquema: tablas, secuencias, funciones, triggers, índices, comentarios y datos semilla.
2. **Ubicación:** `database/liquibase/`, en el mismo repositorio que la API pero como proyecto hermano, nunca dentro de `api/`. Es la excepción monorepo del estándar.
3. **Ejecución en contenedor:** imagen propia basada en `liquibase/liquibase:5.0.4`, con el driver de PostgreSQL instalado vía `lpm`. Desde la versión 5.0 la imagen oficial no incluye drivers.
4. **Formato XML** para changelogs y changesets.
5. **Orden de arranque** en `docker compose`: `postgres` saludable → `liquibase update` (termina) → `api`.

## 3. Convenciones

| Elemento | Convención |
| --- | --- |
| Estructura | `changelog/db.changelog-master.xml` incluye `changelog/vX.Y.Z/db.changelog-vX.Y.Z.xml`, que incluye `NNN-<accion>.xml` |
| Id de changeset | `vX.Y.Z-NNN-<accion>`, por ejemplo `v1.0.0-004-create-table-users` |
| Autor | `eduar.troyano` (cada integrante usa su propio identificador) |
| `<comment>` del changeset | Español |
| Nombres de tablas, columnas y funciones | Inglés, `snake_case`, tablas en plural |
| `remarks` (COMMENT ON de tablas y columnas) | Inglés |
| Rollback | **Obligatorio y explícito** en cada changeset |
| Cierre de versión | Un changeset `tagDatabase` con la versión (`v1.0.0`). Liquibase exige que sea el único elemento del changeset, así que su comentario en español va como comentario XML encima |
| `logicalFilePath` | Fijo en cada archivo, para que mover archivos no cambie la identidad del changeset |

**Reglas del modelo** que aplican todos los changesets:

- `id bigint` con secuencia explícita `<tabla>_id_seq`.
- `active boolean not null default true`: borrado lógico, sin DELETE desde la API.
- `created_at timestamptz not null default now()`.
- Cada tabla de negocio tiene su tabla `<tabla>_audit` (secuencia `<tabla>_audit_id_seq`) y su trigger `<tabla>_audit_trg`. El trigger invoca la función común `audit_row_change()`.

## 4. Reglas de evolución

1. **Nunca se edita un changeset ya aplicado.** Liquibase guarda su checksum en `databasechangelog` y se detiene si cambia. Toda corrección va en un changeset nuevo.
2. **Cambios en caliente con el patrón expandir y contraer.** Para renombrar o eliminar columnas o tablas que la API usa:
   1. agregar lo nuevo sin quitar lo viejo;
   2. desplegar la API que usa lo nuevo;
   3. eliminar lo viejo en un changeset posterior.
3. **Toda tabla nueva** se crea junto con su `<tabla>_audit`, sus secuencias y su trigger, en el mismo changeset.
4. **Respaldo antes de un cambio delicado:** `database/scripts/backup.sh`.
5. **Los modelos SQLAlchemy reflejan el esquema** y no lo definen. Un test de integración detecta desalineación entre modelos y esquema.

## 5. Fuera del alcance de Liquibase

**Crear la base de datos.** Liquibase se conecta a una base existente. Además, `CREATE DATABASE` no puede ejecutarse dentro de una transacción y exige estar conectado a otra base.

La creación es un paso de *bootstrap* idempotente, una vez por ambiente:
- `database/bootstrap/01-create-database.sql`;
- `database/scripts/bootstrap.sh` para ejecutarlo en otros ambientes.

Ver [`database/README.md`](../../database/README.md).

## 6. Consecuencias

- **Positivas:**
  - Esquema reproducible y auditable.
  - Rollback probado con `update-testing-rollback`.
  - El mismo artefacto (la imagen) sirve en local y en CI/CD.
  - Cada cohorte hereda el historial completo.
- **Negativas:**
  - Los modelos SQLAlchemy se mantienen a mano en paralelo al changelog.
  - XML es verboso.
  - Las funciones PL/pgSQL y el tipo `vector` requieren bloques `<sql>`/`<createProcedure>`.

## 7. Referencias

- [Liquibase: introducción](https://docs.liquibase.com/community/implementation-guide-5-0-4/intro-to-liquibase)
- [Liquibase: qué es un changelog](https://docs.liquibase.com/community/user-guide-5-0-4/what-is-a-changelog)
- [Liquibase y Docker](https://docs.liquibase.com/workflows/liquibase-community/using-liquibase-and-docker.html)
- [Imagen `liquibase/liquibase`](https://hub.docker.com/r/liquibase/liquibase)
