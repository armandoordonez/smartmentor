# ADR 0003: Organización del microservicio por dominio

* **Estado:** Aceptado
* **Fecha:** 2026-10-07
* **Autor:** eduar.troyano
* **Fuente:** [`proyecto/brief.md`](../../proyecto/brief.md), secciones "Módulos y requerimientos funcionales" y "Arquitectura técnica y stack sugerido"
* **Relacionados:** [estándar del microservicio](../../api/microservice-development-standard.md), sección 3.1

## 1. Contexto

El estándar de microservicios FastAPI propone una estructura **por capas**: `app/api/`, `app/application/`, `app/domain/` y `app/infrastructure/`, cada una con subcarpetas por contexto.

Con seis dominios, esa estructura dispersa cada dominio en cuatro árboles distintos. Eso dificulta:

- que un integrante trabaje un dominio completo sin pisar a otro;
- que la siguiente cohorte entienda o reemplace un dominio de una vez;
- revisar un pull request que toca un solo dominio.

## 2. Decisión

Se organiza el código **por dominio**, con las capas **dentro** de cada uno. Las reglas de dependencia del estándar (sección 21) **no cambian**.

```text
api/app/
├── main.py
├── core/          # config, database, logging, middleware, errores HTTP (RFC 9457), audit, security
├── common/        # constantes, entidad base, modelo base, repositorio y servicio CRUD genéricos,
│                  # fábrica de routers, esquemas comunes, errores de negocio
├── auth/          # get_current_user, require_roles y matriz de permisos (raíz de composición, ADR 0004)
├── health/        # /health y /ready
└── domains/
    └── <domain>/
        ├── controller.py        # capa API: routers (usa la fábrica CRUD de common/controller.py)
        ├── schemas.py           # capa API: contratos request/response (Pydantic)
        ├── dependencies.py      # composición: construye los servicios con sus repositorios SQLAlchemy
        ├── service.py           # capa aplicación: casos de uso y reglas de negocio
        ├── entities.py          # capa dominio: entidades (dataclasses de Python puro)
        ├── exceptions.py        # capa dominio: errores de negocio (solo si el dominio los necesita)
        ├── repository.py        # capa dominio: interfaz del repositorio (Protocol)
        ├── models.py            # capa infraestructura: modelos SQLAlchemy
        └── repository_impl.py   # capa infraestructura: implementación SQLAlchemy
```

## 3. Dominios

Derivados de los módulos del brief:

| Dominio | Tablas | Módulo del brief |
| --- | --- | --- |
| `identity` | roles, users, user_roles | 1. Gestión de usuarios |
| `courses` | courses, topics, topic_prerequisites | 2. Gestión de cursos y syllabus |
| `learning_paths` | learning_paths, enrollments, path_steps | 3. Gestión de rutas y 5. Motor de ruta |
| `content` | resources | 5. Motor de ruta y contenido |
| `assessments` | diagnostics, assessment_attempts, badges | 4. Diagnóstico y 6. Evaluación y certificación |
| `observability` | llm_call_logs | Componente de IA (log LLM) |

## 4. Reglas de dependencia (mapeo al estándar)

| Archivo | Capa del estándar | Puede importar | No puede importar |
| --- | --- | --- | --- |
| `entities.py`, `exceptions.py`, `repository.py` | Dominio | stdlib, `common.entities`, `common.constants` | FastAPI, SQLAlchemy, Pydantic |
| `service.py` | Aplicación | dominio del mismo dominio, interfaces de otros dominios | FastAPI, SQLAlchemy |
| `controller.py`, `schemas.py` | API | FastAPI, Pydantic, `service.py`, `dependencies.py` | `models.py`, `repository_impl.py`, SQL |
| `models.py`, `repository_impl.py` | Infraestructura | SQLAlchemy, pgvector, `repository.py`, `entities.py` | FastAPI |
| `dependencies.py` | Composición | Todo lo anterior, incluidos los `repository_impl.py` de otros dominios | Reglas de negocio |

- La composición vive en `dependencies.py`: las funciones `get_<x>_service` construyen cada servicio con su `repository_impl` y la unidad de trabajo. `controller.py` solo recibe el servicio.
- Un dominio no importa `models.py` ni `repository_impl.py` de otro dominio. La **única excepción** es `dependencies.py`, la raíz de composición: ahí se conectan, por ejemplo, el repositorio de temas de `courses` con el servicio de pasos de `learning_paths`. Los servicios dependen solo de las interfaces (`repository.py`) de los otros dominios.
- Los repositorios, servicios y routers CRUD comparten una base genérica en `common/` (`SqlAlchemyCrudRepository`, `CrudService`, `build_crud_router`). Cada dominio solo declara su modelo, su entidad, sus esquemas y sus reglas de negocio.

## 5. Consecuencias

- **Positivas:** alta cohesión, PRs acotados, traspaso entre cohortes por dominio y la misma testabilidad del estándar.
- **Negativas:** la separación de capas depende de la disciplina por archivo y no de la carpeta. Se mitiga con la tabla de la sección 4, la revisión de PR y, a futuro, con `import-linter` en CI.
