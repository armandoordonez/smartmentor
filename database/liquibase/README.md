# database/liquibase/

Versionado del esquema de la base `smartmentor` con **Liquibase 5.0.4**. La decisión y sus reglas están en el [ADR 0002](../../docs/adr/0002-liquibase-schema-versioning.md); este documento explica cómo operarlo.

## 1. Cómo funciona

Liquibase aplica a PostgreSQL los cambios descritos en los **changelogs** (archivos XML). Cada cambio es un **changeset** con un `id` y un `author`.

En la propia base mantiene dos tablas de control:

| Tabla | Para qué sirve |
| --- | --- |
| `databasechangelog` | Registra cada changeset aplicado: id, autor, archivo, fecha, **checksum (MD5)** y tag. |
| `databasechangeloglock` | Bloqueo para que dos ejecuciones no apliquen cambios al mismo tiempo. |

En cada ejecución compara los changelogs con `databasechangelog` y **aplica solo lo pendiente**. Si un changeset ya aplicado fue modificado, su checksum no coincide y Liquibase **se detiene**. Por eso las correcciones siempre van en un changeset nuevo.

### Ejecución en contenedor

- **Imagen propia** ([`Dockerfile`](Dockerfile)) basada en `liquibase/liquibase:5.0.4`. Desde la versión 5.0 la imagen oficial no trae drivers, así que se instala el de PostgreSQL con `lpm add postgresql --global`.
- **Contenedor de ejecución única:** arranca, ejecuta el comando y termina (`restart: "no"`). No queda corriendo.
- **Changelogs desde git:** se montan de solo lectura desde `database/liquibase/changelog/`. El contenido siempre sale del repositorio, no de la imagen.
- **Conexión por variables de entorno**, tomadas de `.env` en el compose:
  - `LIQUIBASE_COMMAND_URL=jdbc:postgresql://postgres:5432/smartmentor`
  - `LIQUIBASE_COMMAND_USERNAME`
  - `LIQUIBASE_COMMAND_PASSWORD`
  - `LIQUIBASE_COMMAND_CHANGELOG_FILE=db.changelog-master.xml` (relativo a `/liquibase/changelog`, que es el directorio montado)

### Integración con `docker compose up`

```text
postgres (healthcheck OK) ──► liquibase update (termina con código 0) ──► api
```

La API solo arranca si Liquibase terminó bien (`service_completed_successfully`), así que nunca encuentra un esquema desactualizado. Si no hay cambios pendientes, Liquibase termina en segundos.

> Liquibase **no crea la base de datos**: necesita que `smartmentor` exista. Ver "Arranque en tres niveles" en [`database/README.md`](../README.md).

## 2. Estructura y convenciones

```text
changelog/
├── db.changelog-master.xml          # punto de entrada: incluye cada versión en orden
├── v1.0.0/                          # modelo de datos inicial
│   ├── db.changelog-v1.0.0.xml      # incluye los changesets de la versión en orden
│   ├── 001-extensions-and-timezone.xml
│   ├── 002-audit-function.xml
│   ├── 003-create-table-roles.xml
│   ├── ...
│   └── 019-tag-v1.0.0.xml
└── v1.0.1/                          # usuario administrador inicial
    ├── db.changelog-v1.0.1.xml
    ├── 001-seed-admin-user.xml
    └── 002-tag-v1.0.1.xml
```

| Elemento | Convención |
| --- | --- |
| Id | `vX.Y.Z-NNN-<accion>`, por ejemplo `v1.0.0-004-create-table-users` |
| Autor | `eduar.troyano` (cada integrante usa su propio identificador) |
| `<comment>` del changeset | Español: qué hace y por qué |
| Tablas, columnas, funciones | Inglés, `snake_case`, tablas en plural |
| `remarks` de tablas y columnas | Inglés (generan `COMMENT ON`) |
| `<rollback>` | **Obligatorio y explícito** |
| `logicalFilePath` | Fijo en cada archivo (`vX.Y.Z/NNN-<accion>.xml`) |
| Cierre de versión | Changeset final con `<tagDatabase tag="vX.Y.Z"/>`. Liquibase exige que sea el **único** elemento del changeset (no admite `<comment>`), así que su comentario en español va como comentario XML (`<!-- -->`) justo encima |

**Reglas del modelo:**

- `id bigint` con secuencia `<tabla>_id_seq`, más `active` y `created_at`.
- Toda tabla nueva se crea junto con su `<tabla>_audit`, la secuencia `<tabla>_audit_id_seq` y el trigger `<tabla>_audit_trg`, en el mismo changeset.

## 3. Escenarios y comandos

Todos se ejecutan desde la raíz del repositorio. `run --rm` crea un contenedor temporal que se borra al terminar; postgres y la API siguen corriendo.

| Escenario | Comando |
| --- | --- |
| Primer arranque del entorno | `docker compose up -d` |
| Aplicar cambios pendientes (con todo arriba) | `docker compose run --rm liquibase update` |
| Ver qué falta aplicar | `docker compose run --rm liquibase status --verbose` |
| Ver el SQL que se ejecutaría, sin aplicarlo | `docker compose run --rm liquibase update-sql` |
| Historial de lo aplicado | `docker compose run --rm liquibase history` |
| Validar la sintaxis de los changelogs | `docker compose run --rm liquibase validate` |
| Probar el rollback de lo pendiente (aplica, revierte y reaplica) | `docker compose run --rm liquibase update-testing-rollback` |
| Revertir hasta una versión etiquetada | `docker compose run --rm liquibase rollback --tag=v1.0.0` |
| Revertir los últimos N changesets | `docker compose run --rm liquibase rollback-count --count=1` |
| Ver el SQL de un rollback, sin ejecutarlo | `docker compose run --rm liquibase rollback-sql --tag=v1.0.0` |
| Liberar un bloqueo que quedó colgado (ejecución interrumpida) | `docker compose run --rm liquibase release-locks` |
| Reconstruir la imagen (cambio del Dockerfile) | `docker compose build liquibase` |
| Ejecutar contra otro ambiente (CI/CD o base gestionada) | ver abajo |

### Flujo para un cambio nuevo

1. Crear `changelog/vX.Y.Z/NNN-<accion>.xml` con la plantilla de la sección 5 e incluirlo en `db.changelog-vX.Y.Z.xml`. Si es una versión nueva, se incluye en el master.
2. `docker compose run --rm liquibase validate`
3. `docker compose run --rm liquibase update-sql`, para revisar el SQL.
4. Si el cambio es delicado: `./database/scripts/backup.sh`
5. `docker compose run --rm liquibase update`
6. Si cambian columnas que usa la API, actualizar `models.py` y `docker compose up -d --build api`.
7. Antes del PR: `docker compose run --rm liquibase update-testing-rollback` sobre una base de prueba, para comprobar el rollback.

### Otro ambiente

La misma imagen sirve para cualquier ambiente; solo cambian las variables de conexión:

```bash
docker compose build liquibase
docker run --rm \
  -v "$PWD/database/liquibase/changelog:/liquibase/changelog:ro" \
  -e LIQUIBASE_COMMAND_URL="jdbc:postgresql://<host>:5432/smartmentor" \
  -e LIQUIBASE_COMMAND_USERNAME="<usuario>" \
  -e LIQUIBASE_COMMAND_PASSWORD="<password>" \
  -e LIQUIBASE_COMMAND_CHANGELOG_FILE="db.changelog-master.xml" \
  smartmentor-liquibase update
```

## 4. Cambios con la base y la API en ejecución

| Tipo de cambio | En caliente | Cuidado |
| --- | --- | --- |
| Agregar tabla, columna nullable, comentario o datos semilla | Seguro | La API actual lo ignora. |
| Agregar columna `NOT NULL` | Con cuidado | Requiere `defaultValue`; si no, falla con filas existentes. |
| Índice sobre una tabla grande | Con cuidado | Bloquea escrituras. Usar `CREATE INDEX CONCURRENTLY` en un `<sql>` dentro de un changeset con `runInTransaction="false"`. |
| Renombrar o eliminar columna o tabla | Peligroso | La API en ejecución la sigue usando y falla. Usar expandir y contraer. |
| Cambiar la dimensión de `vector` | Peligroso | Hay que recalcular los embeddings y recrear el índice HNSW (pendiente D-01). |

**Expandir y contraer**, para renombrar o eliminar sin cortar el servicio:

1. Agregar lo nuevo sin quitar lo viejo, y copiar los datos si hace falta.
2. Desplegar la API que usa lo nuevo.
3. En un changeset posterior, eliminar lo viejo.

**Auditoría:**
- Una columna nueva **no** exige cambiar `<tabla>_audit`, porque guarda la fila completa en `jsonb`.
- Una tabla nueva **sí** exige crear su `_audit`, sus secuencias y su trigger.

## 5. Plantilla de un changeset nuevo

```xml
<?xml version="1.0" encoding="UTF-8"?>
<databaseChangeLog
        xmlns="http://www.liquibase.org/xml/ns/dbchangelog"
        xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
        xsi:schemaLocation="http://www.liquibase.org/xml/ns/dbchangelog
                            http://www.liquibase.org/xml/ns/dbchangelog/dbchangelog-latest.xsd"
        logicalFilePath="v1.1.0/001-add-column-users-phone.xml">

    <changeSet id="v1.1.0-001-add-column-users-phone" author="eduar.troyano">
        <comment>Agrega el teléfono de contacto del usuario (opcional).</comment>

        <addColumn tableName="users">
            <column name="phone" type="varchar(30)" remarks="User contact phone number"/>
        </addColumn>

        <rollback>
            <dropColumn tableName="users" columnName="phone"/>
        </rollback>
    </changeSet>

</databaseChangeLog>
```

## 6. Problemas frecuentes

| Síntoma | Causa | Solución |
| --- | --- | --- |
| `Validation Failed: checksum changed` | Se editó un changeset ya aplicado | Revertir la edición y crear un changeset nuevo. Solo en local y sin datos valiosos: `clear-checksums`. |
| `Waiting for changelog lock...` | Una ejecución anterior se interrumpió | `docker compose run --rm liquibase release-locks` |
| `FATAL: database "smartmentor" does not exist` | La base no existe (Liquibase no la crea) | `./database/scripts/bootstrap.sh` |
| `Driver class not found` | Imagen sin el driver | `docker compose build liquibase` |
| `permission denied to create extension "vector"` | El usuario no tiene privilegios (nube) | Habilitar la extensión desde el proveedor o con un usuario administrador. |

## 7. Referencias

- [Liquibase: introducción](https://docs.liquibase.com/community/implementation-guide-5-0-4/intro-to-liquibase)
- [Liquibase: qué es un changelog](https://docs.liquibase.com/community/user-guide-5-0-4/what-is-a-changelog)
- [Liquibase y Docker](https://docs.liquibase.com/workflows/liquibase-community/using-liquibase-and-docker.html)
- [Imagen `liquibase/liquibase`](https://hub.docker.com/r/liquibase/liquibase)
