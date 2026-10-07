# ADR 0001: PostgreSQL 17 + pgvector como base de datos de SmartMentor

* **Estado:** Aceptado
* **Fecha:** 2026-10-07
* **Ámbito:** Base de datos de SmartMentor (desarrollo local y referencia para entornos gestionados)
* **Autor:** eduar.troyano
* **Fuente:** [`proyecto/brief.md`](../../proyecto/brief.md), secciones "Arquitectura técnica y stack sugerido" y "Modelo de datos principal"
* **Relacionados:** [ADR 0002 (Liquibase)](0002-liquibase-schema-versioning.md), [decisiones pendientes](../../proyecto/decisiones-pendientes.md)

---

## 1. Contexto

El brief define **PostgreSQL con pgvector como única base**: relacional para usuarios, cursos, rutas y evaluaciones, y vectorial para los embeddings de temas, perfiles y fragmentos RAG.

Hace falta un estándar reproducible, mantenible y con soporte oficial. Se evitan tags genéricos (`:latest`) y referencias ambiguas (`PostgreSQL 15+`) para garantizar:

1. **Reproducibilidad:** el mismo comportamiento en el equipo de cada integrante y de cada cohorte.
2. **Paridad con la nube:** la imagen local refleja el servicio gestionado donde se despliegue el MVP (el brief sugiere Supabase, Render o Railway).
3. **Soporte oficial:** alineación con los calendarios de fin de soporte (EOL) de PostgreSQL y las publicaciones de `pgvector`.

---

## 2. Decisión

| Componente | Valor | Justificación |
| :--- | :--- | :--- |
| **Motor** | PostgreSQL 17.x | Madurez, estabilidad y soporte activo hasta noviembre de 2029. |
| **Extensión vectorial** | pgvector 0.8.7 | Última versión de parches (publicada el 2026-10-01). Soporta HNSW, IVFFlat, `halfvec` y cuantización binaria. |
| **Sistema base** | Debian Bookworm | Base estable y conservadora; la misma que la imagen del microservicio. |
| **Imagen Docker** | `pgvector/pgvector:0.8.7-pg17-bookworm` | Versión fijada exacta, sin sorpresas en `docker compose`. |
| **Base de datos** | `smartmentor` | Nombre único en todos los ambientes. |
| **Zona horaria** | `America/Bogota` | Contenedor, servidor y base. Las columnas de fecha son `timestamptz`. |
| **ORM** | SQLAlchemy 2.x (async) | Integración con FastAPI ([estándar del microservicio](../../api/microservice-development-standard.md)). |
| **Versionado de esquema** | Liquibase 5.0.4 | En el mismo repositorio, bajo `database/liquibase/` ([ADR 0002](0002-liquibase-schema-versioning.md)). |

> Cambio respecto a la primera versión de este ADR: se fijó pgvector 0.8.6. Se actualiza a 0.8.7 porque es un parche de la misma serie 0.8.x, sin cambios de formato ni de API.

---

## 3. Justificación: PostgreSQL 17 frente a 18

PostgreSQL 18 está disponible y tiene soporte hasta noviembre de 2030. Aun así, se elige PostgreSQL 17 por estas razones:

### 3.1 Madurez del ecosistema
PostgreSQL 17 lleva más tiempo estabilizándose, con varias versiones de corrección (*minor releases*) y compatibilidad madura con librerías de terceros: SQLAlchemy, asyncpg, PgBouncer, Liquibase y utilidades de respaldo.

### 3.2 Paridad con proveedores gestionados
Los servicios gestionados suelen incorporar una versión *major* nueva con 6 a 12 meses de desfase. PostgreSQL 17 está disponible de forma general en los proveedores habituales.

**Antes de desplegar** se debe verificar que el destino elegido (pendiente D-06) ofrezca PostgreSQL 17 con pgvector 0.8.x.

La imagen de PostgreSQL 18 además cambia la ruta de datos (`/var/lib/postgresql/18/docker`). Eso afectaría el volumen local definido en la sección 5.

### 3.3 Ventana de soporte
El soporte hasta noviembre de 2029 cubre con margen la hoja de ruta de cuatro cohortes del brief.

---

## 4. Matriz comparativa de versiones

| PostgreSQL | pgvector | Fin de soporte (EOL) | Valoración | Criterio de uso |
| :---: | :---: | :---: | :---: | :--- |
| **17.x (elegida)** | **0.8.7** | **Nov. 2029** | ⭐⭐⭐⭐⭐ | Equilibrio entre estabilidad, madurez y compatibilidad con la nube. |
| 18.x | 0.8.7 | Nov. 2030 | ⭐⭐⭐⭐ | Proyectos nuevos sin dependencia de un proveedor gestionado. |
| 16.x | 0.8.7 | Nov. 2028 | ⭐⭐⭐⭐ | Solo si un sistema existente restringe la versión 17. |
| 15.x | 0.8.7 | Nov. 2027 | ⭐⭐⭐ | No recomendada: vida útil reducida. |
| 14.x | 0.8.7 | Nov. 2026 | ⭐⭐ | Obsoleta: fin de soporte inminente. |

---

## 5. Configuración local

### 5.1 Servicio en `docker-compose.yml`

```yaml
name: smartmentor

services:
  postgres:
    image: pgvector/pgvector:0.8.7-pg17-bookworm
    container_name: smartmentor-postgres
    restart: unless-stopped
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}   # sin valor por defecto: viene de .env
      TZ: America/Bogota
      PGTZ: America/Bogota
    command: ["postgres", "-c", "timezone=America/Bogota", "-c", "log_timezone=America/Bogota"]
    ports:
      - "${POSTGRES_PORT:-5442}:5432"   # 5442 en el host: 5432 suele estar ocupado por otros proyectos
    volumes:
      - ./database/data/postgres:/var/lib/postgresql/data   # datos dentro del proyecto (ignorado por git)
      - ./database/bootstrap:/docker-entrypoint-initdb.d:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $${POSTGRES_USER} -d $${POSTGRES_DB}"]
      interval: 10s
      timeout: 5s
      retries: 5
```

Decisiones de la configuración:

- **Volumen dentro del proyecto:** se monta `./database/data/postgres` en lugar de un volumen con nombre, para que los datos queden junto al repositorio. Se usa una subcarpeta porque `initdb` exige un directorio vacío, y `database/data/` contiene un `.gitkeep`.
- **Sin contraseña por defecto:** las credenciales salen siempre de `.env`, que está fuera de git (`.env.example` documenta las variables).
- **Extensión creada por Liquibase:** `CREATE EXTENSION vector` y la zona horaria de la base las aplica el primer changeset ([ADR 0002](0002-liquibase-schema-versioning.md)), no un comando manual.

### 5.2 Verificación

```bash
docker compose up -d postgres

# Versión del motor
docker compose exec postgres psql -U "$POSTGRES_USER" -d smartmentor -c "SELECT version();"

# Zona horaria (esperado: America/Bogota)
docker compose exec postgres psql -U "$POSTGRES_USER" -d smartmentor -c "SHOW timezone;"

# Versión de pgvector (esperado: 0.8.7, después de correr Liquibase)
docker compose exec postgres psql -U "$POSTGRES_USER" -d smartmentor \
  -c "SELECT extversion FROM pg_extension WHERE extname = 'vector';"
```

---

## 6. Ambientes y desacoplamiento

El contenedor es **infraestructura de desarrollo local**. La API (FastAPI) y Liquibase se conectan por el protocolo estándar de PostgreSQL. Así, en otros ambientes basta con cambiar las variables de conexión.

```text
                  DESARROLLO LOCAL                            ENTORNOS GESTIONADOS (STG / PROD)
 ┌──────────────────────────────────────────────┐          ┌──────────────────────────────────────────────┐
 │ Contenedor smartmentor-postgres              │          │ PostgreSQL gestionado (destino: D-06)        │
 │  - pgvector:0.8.7-pg17-bookworm              │          │  - PostgreSQL 17.x + pgvector 0.8.x          │
 └──────────────────────┬───────────────────────┘          └──────────────────────┬───────────────────────┘
                        │ puerto 5432 (5442 en el host local)                     │
                        ▼                                                         ▼
 ┌──────────────────────────────────────────────┐          ┌──────────────────────────────────────────────┐
 │ API FastAPI (SQLAlchemy 2.x)                 │          │ API FastAPI (SQLAlchemy 2.x)                 │
 └──────────────────────────────────────────────┘          └──────────────────────────────────────────────┘
                        ▲ esquema                                                 ▲ esquema
 ┌──────────────────────┴───────────────────────┐          ┌──────────────────────┴───────────────────────┐
 │ Contenedor Liquibase 5.0.4 (compose)         │          │ Misma imagen Liquibase en CI/CD              │
 └──────────────────────────────────────────────┘          └──────────────────────────────────────────────┘
```

Liquibase **no crea la base de datos**: se conecta a una existente. La creación es un paso previo de *bootstrap*, una vez por ambiente; se describe en [`database/README.md`](../../database/README.md).

En servicios gestionados, `CREATE EXTENSION vector` y `ALTER DATABASE ... SET timezone` pueden requerir pasos del proveedor; en Supabase, por ejemplo, la extensión se habilita desde el panel.

---

## 7. Límites relevantes para el diseño

- **Dimensión de los embeddings:** los índices HNSW sobre el tipo `vector` admiten hasta 2000 dimensiones; `halfvec` llega a 4000. La dimensión elegida (provisional: 1024) está en el pendiente D-01 de [decisiones pendientes](../../proyecto/decisiones-pendientes.md).
- **Un solo modelo de embeddings:** temas, perfiles y fragmentos deben usar el mismo modelo, porque se comparan entre sí.

---

## 8. Consecuencias

- **Positivas:**
  - Una sola tecnología de datos, relacional y vectorial, sin un vector store aparte.
  - Entorno reproducible con un solo `docker compose up`.
  - Versiones fijadas y documentadas.
- **Negativas:**
  - Subir a PostgreSQL 18 exigirá migrar el volumen con `pg_upgrade` o con un dump y restauración.
  - La dimensión del vector queda acoplada al modelo de embeddings: cambiarla exige un changeset y recalcular los vectores.

---

## 9. Referencias oficiales

* **PostgreSQL:**
  * [PostgreSQL Versioning Policy](https://www.postgresql.org/support/versioning/): calendario de versiones y fechas de fin de soporte.
  * [PostgreSQL Docker Official Image](https://hub.docker.com/_/postgres): variables `POSTGRES_*`, `docker-entrypoint-initdb.d` y volumen de datos.
* **pgvector:**
  * [pgvector GitHub Repository](https://github.com/pgvector/pgvector): documentación, índices y límites de dimensión.
  * [pgvector Docker Tags](https://hub.docker.com/r/pgvector/pgvector/tags): `0.8.7-pg17-bookworm`.
  * [pgvector Changelog](https://github.com/pgvector/pgvector/blob/master/CHANGELOG.md): historial de versiones.
