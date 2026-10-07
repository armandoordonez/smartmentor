# api/

API de negocio en FastAPI: usuarios, cursos, rutas y evaluaciones.

## Estándar de referencia

Este microservicio sigue el estándar [`microservice-development-standard.md`](microservice-development-standard.md) (rev. 2): arquitectura por capas, reglas de dependencia, calidad (Ruff, mypy, pytest) y convenciones de API, datos, auditoría, zona horaria y errores. Todo microservicio FastAPI nuevo del proyecto debe seguirlo.

Decisiones relacionadas:

- [ADR 0001: PostgreSQL 17 + pgvector](../docs/adr/0001-postgres-pgvector.md)
- [ADR 0002: Liquibase](../docs/adr/0002-liquibase-schema-versioning.md). La API no crea ni migra tablas.
- [ADR 0003: organización por dominio](../docs/adr/0003-api-domain-first-layout.md)

## Dominios

| Dominio | Recursos |
| --- | --- |
| `identity` | roles, users, user_roles |
| `courses` | courses, topics, topic_prerequisites |
| `learning_paths` | learning_paths, enrollments, path_steps |
| `content` | resources |
| `assessments` | diagnostics, assessment_attempts, badges |
| `observability` | llm_call_logs |

Cada recurso expone crear, consultar, listar, actualizar, activar e inactivar bajo `/api/v1`. No hay `DELETE`.

## Ejecución

*Por completar en la fase de implementación del microservicio.*
