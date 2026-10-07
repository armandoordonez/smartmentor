# Architecture Decision Record (ADR): Estandarización de PostgreSQL + pgvector para Desarrollo Local

* **Estado:** Aprobado
* **Fecha:** Octubre 2026
* **Ámbito:** Arquitectura de Microservicios / Entorno de Desarrollo Local
* **Autores:** Equipo de Arquitectura de Software

---

## 1. Contexto

Para el desarrollo local de microservicios con capacidades de búsqueda vectorial y generación aumentada por recuperación (RAG), se requiere definir un estándar reproducible, mantenible y soportado oficialmente para **PostgreSQL** y la extensión **`pgvector`**.

Se identificó la necesidad de evitar configuraciones genéricas (como tags `:latest` o referencias ambiguas tipo `PostgreSQL 15+`) para garantizar:
1. **Reproducibilidad:** Mismo comportamiento en los entornos de desarrollo de todos los ingenieros.
2. **Compatibilidad Cloud (Environment Parity):** Paridad estricta entre las imágenes Docker locales y los servicios de base de datos administrados en entornos superiores.
3. **Soporte Oficial:** Alineación estricta con los calendarios de soporte (EOL) y publicaciones del proyecto `pgvector`.

---

## 2. Decisión

Se establece como estándar corporativo oficial para desarrollo local la siguiente combinación:

* **PostgreSQL Engine:** `17.x`
* **Vector Extension:** `pgvector 0.8.6`
* **Base OS (Docker Image):** Debian Bookworm (`bookworm`)
* **Imagen Docker Oficial:** `pgvector/pgvector:0.8.6-pg17-bookworm`

### Resumen del Estándar

| Componente | Valor Seleccionado | Justificación / Observación |
| :--- | :--- | :--- |
| **Database Engine** | PostgreSQL 17.x | Madurez, estabilidad y soporte activo hasta Nov. 2029. |
| **Vector Extension** | pgvector 0.8.6 | Versión estable con soporte para HNSW, IVFFlat e indexación binaria. |
| **Base OS** | Debian Bookworm | Base altamente estable, conservadora y recomendada para entornos enterprise. |
| **Docker Image Tag** | `0.8.6-pg17-bookworm` | Pinned exacto para eliminar imprevistos en ejecuciones `docker compose`. |
| **ORM Framework** | SQLAlchemy 2.x | Integración a nivel de aplicación Python / FastAPI. |
| **Schema Migrations** | Liquibase | Administración externa al repositorio de aplicación. |

---

## 3. Justificación Técnica: PostgreSQL 17 vs. PostgreSQL 18

Aunque **PostgreSQL 18** está disponible y cuenta con soporte hasta noviembre de 2030, se ha seleccionado **PostgreSQL 17** como estándar por las siguientes razones:

### 3.1. Madurez del Ecosistema
PostgreSQL 17 cuenta con un recorrido de estabilización mayor, ofreciendo múltiples versiones de corrección de errores (*minor releases*) y compatibilidad madura con librerías de terceros, ORMs (SQLAlchemy, PgBouncer) y utilidades de monitoreo.

### 3.2. Paridad con Proveedores Cloud (AWS, GCP, Azure)
Los servicios administrados de bases de datos (como AWS RDS, Cloud SQL o Azure Database) suelen incorporar las versiones *major* más recientes con un desfase de 6 a 12 meses respecto a su lanzamiento oficial. PostgreSQL 17 se encuentra en estado **General Availability (GA)** en la mayoría de plataformas cloud, garantizando que el contenedor local refleje fielmente el comportamiento de producción.

### 3.3. Ventana de Soporte Oficial
PostgreSQL 17 cuenta con soporte activo garantizado hasta **noviembre de 2029**, lo que ofrece una ventana operativa de 3 a 4 años, más que suficiente para el ciclo de vida inicial de los microservicios antes de requerir un *upgrade* de infraestructura.

---

## 4. Matriz Comparativa de Versiones

| Opción PostgreSQL | pgvector | Fin de Soporte Oficial (EOL) | Valoración | Criterio de Uso |
| :---: | :---: | :---: | :---: | :--- |
| **17.x (Recomendada)** | **0.8.6** | **Nov. 2029** | ⭐⭐⭐⭐⭐ | **Estándar Oficial:** Balance perfecto entre estabilidad, madurez y compatibilidad Cloud. |
| **18.x** | **0.8.6** | **Nov. 2030** | ⭐⭐⭐⭐⭐ | **Innovación:** Válida para proyectos *greenfield* o de investigación sin dependencias Cloud estrictas. |
| **16.x** | **0.8.6** | **Nov. 2028** | ⭐⭐⭐⭐ | **Conservadora:** Adecuada si existen sistemas heredados que restringen la v17. |
| **15.x** | **0.8.6** | **Nov. 2027** | ⭐⭐⭐ | **No Recomendada:** Ventana de vida útil reducida para proyectos nuevos. |
| **14.x** | **0.8.6** | **Nov. 2026** | ⭐⭐ | **Legacy / Deprecada:** Próxima a fin de soporte oficial. |

---

## 5. Configuración y Despliegue Local

### 5.1. Archivo `docker-compose.yml`

```yaml
services:
  postgres:
    image: pgvector/pgvector:0.8.6-pg17-bookworm
    container_name: microservice-postgres
    restart: unless-stopped
    environment:
      POSTGRES_DB: microservice_db
      POSTGRES_USER: microservice_user
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-postgres_secret}
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U microservice_user -d microservice_db"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
```

### 5.2. Comandos de Activación y Verificación

Ejecutar las siguientes instrucciones tras iniciar el contenedor mediante `docker compose up -d`:

```bash
# 1. Habilitar la extensión vectorial en la base de datos objetivo
docker exec -it microservice-postgres \
  psql -U microservice_user -d microservice_db \
  -c "CREATE EXTENSION IF NOT EXISTS vector;"

# 2. Verificar la versión activa del motor PostgreSQL
docker exec -it microservice-postgres \
  psql -U microservice_user -d microservice_db \
  -c "SELECT version();"

# 3. Validar la versión instalada de pgvector
docker exec -it microservice-postgres \
  psql -U microservice_user -d microservice_db \
  -c "SELECT extversion FROM pg_extension WHERE extname = 'vector';"
```

---

## 6. Arquitectura de Entornos y Desacoplamiento

El contenedor Docker de PostgreSQL + pgvector se concibe **exclusivamente como infraestructura de desarrollo local**. La aplicación (FastAPI) y la herramienta de migraciones (Liquibase) interactúan con la base de datos a través de protocolos estándar, permitiendo desacoplar el entorno local de los entornos administrados.

```
                  DESARROLLO LOCAL                            ENTORNOS SUPERIORES (STG / PROD)
 ┌──────────────────────────────────────────────┐          ┌──────────────────────────────────────────────┐
 │ Container Docker Local                       │          │ PostgreSQL Administrado                      │
 │  - Image: pgvector:0.8.6-pg17-bookworm       │          │  - AWS RDS / Cloud SQL / Azure DB            │
 │  - PG Engine: 17.x                           │          │  - PostgreSQL 17.x + pgvector 0.8.6          │
 └──────────────────────┬───────────────────────┘          └──────────────────────┬───────────────────────┘
                        │                                                         │
                        │ PostgreSQL Protocol (Port 5432)                         │ PostgreSQL Protocol
                        ▼                                                         ▼
 ┌──────────────────────────────────────────────┐          ┌──────────────────────────────────────────────┐
 │ Microservicio (FastAPI)                      │          │ Microservicio (FastAPI)                      │
 │  - SQLAlchemy 2.x                            │          │  - SQLAlchemy 2.x                            │
 └──────────────────────────────────────────────┘          └──────────────────────────────────────────────┘
                        ▲                                                         ▲
                        │ Schema Migrations                                       │ Schema Migrations
 ┌──────────────────────┴───────────────────────┐          ┌──────────────────────┴───────────────────────┐
 │ Liquibase (Ejecución Local)                  │          │ Liquibase Pipeline CI/CD                     │
 └──────────────────────────────────────────────┘          └──────────────────────────────────────────────┘
```

---

## 7. Enlaces Oficiales de Referencia y Soporte

* **PostgreSQL:**
  * [PostgreSQL Versioning Policy](https://www.postgresql.org/support/versioning/) — Calendario oficial de publicaciones y fechas End-of-Life (EOL).
  * [PostgreSQL Official Downloads](https://www.postgresql.org/download/) — Repositorios y distribución oficial de binarios.
  * [PostgreSQL Docker Official Image](https://hub.docker.com/_/postgres) — Repositorio base de imágenes de PostgreSQL en Docker Hub.

* **pgvector:**
  * [pgvector GitHub Repository](https://github.com/pgvector/pgvector) — Código fuente, instrucciones de compilación y documentación.
  * [pgvector Docker Hub](https://hub.docker.com/r/pgvector/pgvector) — Registro oficial de imágenes prefijadas con PostgreSQL.
  * [pgvector Docker Tags](https://hub.docker.com/r/pgvector/pgvector/tags) — Referencia de imágenes compiladas (`0.8.6-pg17-bookworm`).
  * [pgvector Changelog](https://github.com/pgvector/pgvector/blob/master/CHANGELOG.md) — Histórico oficial de versiones y correcciones.