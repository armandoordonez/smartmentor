# Standard Architecture for FastAPI Microservices

**Status:** Proposed standard  
**Scope:** Backend microservices developed with Python/FastAPI  
**Architecture:** Layered / Clean Architecture with ports and adapters where justified  
**Database:** PostgreSQL, externally managed  
**Database versioning:** Liquibase, externally managed  
**Quality:** Ruff + mypy + pytest  
**Python:** 3.12+

---

## 1. Purpose

This document defines a standard, maintainable, and repeatable architecture for developing FastAPI microservices.

The objective is that a new microservice can be created following the same structural, architectural, quality, testing, and operational conventions without each development team having to redefine the project structure.

The standard is intentionally pragmatic: it establishes clear boundaries and dependency rules without requiring unnecessary architectural complexity.

---

## 2. Architectural principles

The microservice must follow these principles:

1. **Separation of concerns**
   - HTTP/API concerns must not contain business rules.
   - Business rules must not depend on FastAPI.
   - Domain/application code must not depend directly on SQLAlchemy.
   - Infrastructure implementations must be replaceable without changing business rules.

2. **Dependency direction**

   Dependencies should point toward business concepts:

   ```text
   API
    |
    v
   Application
    |
    v
   Domain
   ```

   Infrastructure implements interfaces/ports required by the application or domain:

   ```text
                     +----------------------+
                     |    Infrastructure    |
                     | SQLAlchemy/PostgreSQL|
                     +----------+-----------+
                                |
                                | implements
                                v
   +----------+       +----------------------+
   |   API    | ----> |    Application      |
   +----------+       +----------+-----------+
                                |
                                v
                       +----------------+
                       |     Domain     |
                       +----------------+
   ```

3. **Explicit boundaries**
   - Each layer has a defined responsibility.
   - Cross-layer access must be intentional.
   - Database models are not automatically API schemas.
   - External integrations are isolated in infrastructure.

4. **Testability**
   - Domain and application logic must be testable without starting FastAPI or requiring a real PostgreSQL instance whenever possible.

5. **Configuration outside the code**
   - Environment-specific configuration and secrets must not be committed to the repository.
   - The microservice consumes configuration through a typed configuration layer.

6. **Database lifecycle outside the application**
   - PostgreSQL is an external infrastructure dependency.
   - Database schema creation and migration are not responsibilities of the FastAPI application.
   - Liquibase manages schema changes externally.

---

## 3. Proposed project structure

The recommended structure is:

```text
microservice-name/
│
├── app/
│   ├── __init__.py
│   ├── main.py
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── exceptions.py
│   │   ├── logging.py
│   │   └── security.py
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── dependencies.py
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── router.py
│   │       └── endpoints/
│   │           ├── __init__.py
│   │           └── <resource>.py
│   │
│   ├── domain/
│   │   └── <bounded_context>/
│   │       ├── __init__.py
│   │       ├── entities.py
│   │       ├── value_objects.py
│   │       ├── repositories.py
│   │       └── exceptions.py
│   │
│   ├── application/
│   │   └── <bounded_context>/
│   │       ├── __init__.py
│   │       ├── commands.py
│   │       ├── queries.py
│   │       └── services.py
│   │
│   └── infrastructure/
│       ├── __init__.py
│       ├── database/
│       │   ├── __init__.py
│       │   ├── session.py
│       │   ├── models/
│       │   │   └── <resource>.py
│       │   └── repositories/
│       │       └── <resource>.py
│       │
│       └── external/
│           └── <integration>/
│
├── tests/
│   ├── unit/
│   │   ├── domain/
│   │   └── application/
│   │
│   └── integration/
│       ├── api/
│       └── infrastructure/
│
├── pyproject.toml
├── Dockerfile
├── .dockerignore
├── .gitignore
└── README.md
```

### Important

The `migrations/` directory is intentionally **not part of this microservice**.

Liquibase belongs to the database-management/deployment process and should have its own repository/project or external infrastructure structure according to the organization's database management strategy.

PostgreSQL itself is also external to this repository.

---

# 4. Layer responsibilities

## 4.1 API layer

Location:

```text
app/api/
```

Responsible for:

- HTTP endpoints.
- URL/path definitions.
- HTTP status codes.
- Request/response schemas.
- Authentication/authorization integration.
- FastAPI dependency injection.
- Translating application errors into HTTP responses.

The API layer must **not** contain business rules or direct SQL queries.

### Example

```python
@router.post("/users")
async def create_user(
    request: UserCreate,
    service: UserService = Depends(get_user_service),
) -> UserResponse:
    user = await service.create_user(request)
    return UserResponse.from_domain(user)
```

The endpoint coordinates the request; it does not implement the business process.

---

## 4.2 Application layer

Location:

```text
app/application/
```

Responsible for application use cases.

Examples:

```text
CreateUser
UpdateUser
GetUser
SearchUsers
DeleteUser
GenerateReport
ProcessOrder
```

This layer coordinates:

- Domain rules.
- Repository interfaces.
- External service ports.
- Transactions/use-case orchestration.

It should not depend on FastAPI or concrete SQLAlchemy repositories.

Example:

```text
HTTP Request
     |
     v
API
     |
     v
CreateUserService
     |
     +----> User domain rules
     |
     +----> UserRepository
     |
     v
HTTP Response
```

---

## 4.3 Domain layer

Location:

```text
app/domain/
```

The domain represents business concepts and business rules.

It should preferably contain normal Python code and should not require FastAPI or SQLAlchemy.

Possible elements:

```text
Entity
Value Object
Domain Exception
Repository Interface
Domain Service
Business Rule
```

Example:

```python
class User:
    def activate(self) -> None:
        if self.status == UserStatus.BLOCKED:
            raise UserCannotBeActivated()

        self.status = UserStatus.ACTIVE
```

The important point is that the rule exists independently of HTTP and PostgreSQL.

---

## 4.4 Infrastructure layer

Location:

```text
app/infrastructure/
```

Responsible for technical implementations:

- SQLAlchemy.
- PostgreSQL connectivity.
- Repository implementations.
- External HTTP clients.
- Redis clients.
- Message brokers.
- Other technical integrations.

For example:

```text
domain.repositories.UserRepository
              ^
              |
              | implements
              |
infrastructure.database.repositories.UserRepositorySQLAlchemy
```

The domain/application layer should depend on the abstraction, not on the concrete SQLAlchemy implementation.

---

# 5. Database architecture

## 5.1 PostgreSQL is external

PostgreSQL is not part of the application source tree.

The microservice only defines the contract necessary to connect to the database.

Example configuration:

```text
DATABASE_HOST
DATABASE_PORT
DATABASE_NAME
DATABASE_USER
DATABASE_PASSWORD
```

or an equivalent externally managed connection configuration.

The actual PostgreSQL server, database lifecycle, credentials, backups, replication, and operational administration belong to the infrastructure/platform layer.

---

## 5.2 PostgreSQL version

The PostgreSQL version used by each environment must be explicitly documented.

Example:

```text
PostgreSQL: 16.x
```

The exact version must be controlled as an infrastructure/platform decision and should not be silently changed by the microservice.

The microservice must be tested against the PostgreSQL version officially supported by the target environment.

---

## 5.3 SQLAlchemy

SQLAlchemy 2.x is the persistence technology used by the microservice.

Recommended responsibilities:

```text
SQLAlchemy models
    -> infrastructure/database/models/

SQLAlchemy repositories
    -> infrastructure/database/repositories/

Database session/engine
    -> infrastructure/database/session.py
```

The application must not expose SQLAlchemy models as its domain model by default.

---

## 5.4 Async database access

For asynchronous FastAPI endpoints, SQLAlchemy's asyncio support may be used through:

```text
AsyncEngine
AsyncSession
async_sessionmaker
```

A database session must be scoped correctly to the request/use case.

A single `AsyncSession` must not be shared concurrently across unrelated asyncio tasks.

Reference:

https://docs.sqlalchemy.org/en/21/orm/extensions/asyncio.html

---

# 6. Database schema versioning with Liquibase

Database schema versioning is explicitly **outside the FastAPI microservice**.

The responsibility split is:

```text
+-----------------------------+
| FastAPI Microservice        |
|                             |
| SQLAlchemy models           |
| Repository implementations  |
| DB connection configuration |
+--------------+--------------+
               |
               | connects to
               v
+-----------------------------+
| PostgreSQL                  |
| External infrastructure    |
+--------------^--------------+
               |
               | schema changes
               |
+-----------------------------+
| Liquibase                   |
| External DB project/process |
|                             |
| changelogs / changesets     |
| database deployment         |
+-----------------------------+
```

### Rules

- The FastAPI project must not contain Alembic.
- The FastAPI project must not execute schema migrations automatically at startup.
- The FastAPI project must not create production tables automatically.
- Schema changes must be performed through Liquibase.
- Liquibase changelogs must be version controlled externally.
- Deployment pipelines must coordinate application and database versions.

Liquibase uses changelogs and changesets to describe database changes and can deploy changes that have not yet been applied. Its documentation also recommends source-controlled changelog structures.

References:

- https://docs.liquibase.com/community/implementation-guide-5-0-4/intro-to-liquibase
- https://docs.liquibase.com/community/user-guide-5-0-4/what-is-a-changelog
- https://docs.liquibase.com/secure/set-up-secure-automation-6-0/structure-your-changelog/how-should-i-structure-my-changelog

---

# 7. Domain-Driven Design (DDD): what this standard means

DDD must **not** be interpreted as a requirement to implement a large academic DDD architecture in every microservice.

The standard uses DDD selectively.

## 7.1 What is mandatory

The microservice must identify and isolate its relevant business concepts and rules.

For example:

```text
Customer
Order
Contract
Property
Payment
Invoice
Project
```

If a business rule belongs to `Order`, it should not be hidden inside an HTTP controller or a SQL query.

---

## 7.2 What is optional

The following are introduced only when the domain complexity justifies them:

- Value Objects.
- Domain Services.
- Aggregates.
- Domain Events.
- Multiple bounded contexts.
- Complex repository abstractions.
- Rich domain entities.

A CRUD service with simple rules does not need all of these concepts.

### Simple example

For a basic catalog:

```text
API
  |
  v
Application Service
  |
  v
Repository
  |
  v
PostgreSQL
```

There is no need to create dozens of domain classes simply because the project uses the term DDD.

For a complex process:

```text
API
  |
  v
Application Use Case
  |
  +--> Aggregate
  |      |
  |      +--> Value Objects
  |      +--> Business Rules
  |
  +--> Repository
  |
  +--> External Service
```

DDD becomes valuable because the business rules are complex enough to justify explicit modeling.

### Practical rule

> **Complexity determines the amount of domain modeling.**

This standard therefore adopts **DDD principles where they improve business modeling**, rather than requiring "full DDD" for every microservice.

---

# 8. Dependency Injection

FastAPI dependencies are used at the API/composition boundary.

Example:

```text
FastAPI Dependency
       |
       v
Application Service
       |
       v
Repository Interface
       |
       v
SQLAlchemy Repository
```

Dependency construction should be centralized instead of instantiating repositories and database sessions inside every endpoint.

Reference:

https://fastapi.tiangolo.com/tutorial/dependencies/

---

# 9. FastAPI application composition

`app/main.py` should remain small.

Its main responsibilities are:

- Create the FastAPI application.
- Configure lifespan.
- Register routers.
- Register global exception handlers.
- Configure middleware.
- Configure API metadata.

FastAPI officially recommends separating larger applications into multiple modules using `APIRouter`.

Reference:

https://fastapi.tiangolo.com/tutorial/bigger-applications/

---

# 10. Application lifespan

Resources shared by the application can be initialized and released using FastAPI `lifespan`.

Typical resources:

```text
Database connection pool
HTTP clients
Redis clients
Message broker clients
Shared models/resources
```

Example:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize resources
    yield
    # Release resources
```

FastAPI currently recommends the `lifespan` mechanism for startup/shutdown logic.

Reference:

https://fastapi.tiangolo.com/advanced/events/

---

# 11. Configuration

Configuration must be centralized and typed.

Recommended location:

```text
app/core/config.py
```

The configuration layer should be the single point through which the application obtains:

- Database configuration.
- External service URLs.
- Environment information.
- Feature flags.
- Timeouts.
- Security configuration.
- Other runtime configuration.

Secrets must never be hardcoded or committed.

Pydantic Settings should be used when appropriate for typed settings loaded from external configuration sources.

Reference:

https://docs.pydantic.dev/latest/concepts/pydantic_settings/

---

# 12. API versioning

APIs should be versioned explicitly.

Recommended structure:

```text
app/api/v1/
```

Example:

```text
/api/<service>/v1/users
```

A new incompatible API contract should normally be introduced as a new API version rather than silently breaking an existing version.

---

# 13. Request and response schemas

API schemas must be separated from persistence models.

Example:

```text
api/
    schemas/
        user_create.py
        user_response.py

infrastructure/
    database/
        models/
            user.py
```

This prevents the HTTP contract from becoming directly coupled to the PostgreSQL schema.

---

# 14. Error handling

Business/application errors must be represented explicitly.

Example:

```text
Domain exception
       |
       v
Application service
       |
       v
API exception handler
       |
       v
HTTP status + standardized error response
```

Avoid leaking:

- SQLAlchemy exceptions.
- PostgreSQL errors.
- Internal stack traces.
- Secrets.
- Infrastructure details.

to API consumers.

---

# 15. Logging

Logging must be centralized and structured where possible.

Logs should provide enough context to diagnose requests and operations without exposing secrets or sensitive information.

Recommended fields include:

```text
timestamp
level
service
environment
request_id
trace_id
operation
message
```

Do not log passwords, tokens, connection strings, or other secrets.

---

# 16. Ruff

Ruff is the standard linter and formatter.

Recommended configuration is centralized in:

```text
pyproject.toml
```

Example:

```toml
[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = [
    "E",
    "F",
    "I",
    "B",
    "UP",
    "SIM",
    "ASYNC",
]

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
```

Minimum CI commands:

```bash
ruff check .
ruff format --check .
```

Reference:

https://docs.astral.sh/ruff/configuration/

---

# 17. mypy

The project must use static type checking.

Recommended baseline:

```toml
[tool.mypy]
python_version = "3.12"
strict = true
```

The final configuration may disable specific checks only when there is a documented technical reason.

Minimum CI command:

```bash
mypy app
```

The objective is zero type-checking errors.

Reference:

https://mypy.readthedocs.io/en/stable/getting_started.html

---

# 18. pyproject.toml

Project and tool configuration should be centralized in `pyproject.toml` where practical.

It can contain:

```text
Project metadata
Dependencies
Ruff configuration
mypy configuration
pytest configuration
Build configuration
```

The Python Packaging User Guide defines `pyproject.toml` as the modern configuration file for packaging and related tools.

Reference:

https://packaging.python.org/en/latest/guides/writing-pyproject-toml/

---

# 19. Testing strategy

Testing should be divided into at least:

```text
tests/
├── unit/
│   ├── domain/
│   └── application/
│
└── integration/
    ├── api/
    └── infrastructure/
```

## Unit tests

Test business and application behavior without requiring the complete infrastructure whenever possible.

Examples:

```text
Domain rules
Application services
Validation
Error conditions
Use cases
```

## Integration tests

Test integration with:

```text
FastAPI
HTTP layer
PostgreSQL
SQLAlchemy
External integrations
```

The exact infrastructure used by integration tests should be defined by the project's CI strategy.

Pytest is the standard testing framework.

Reference:

https://docs.pytest.org/en/stable/

---

# 20. Quality gates

Every pull request should execute at least:

```bash
ruff check .
ruff format --check .
mypy app
pytest
```

Where coverage is required:

```bash
pytest --cov=app --cov-report=term-missing
```

Recommended pipeline:

```text
Pull Request
     |
     v
Ruff check
     |
     v
Ruff format check
     |
     v
mypy
     |
     v
Unit tests
     |
     v
Integration tests
     |
     v
Coverage
     |
     v
Build
     |
     v
Deploy
```

---

# 21. Dependency rules

The following dependency rules are mandatory.

### Domain

Allowed:

```text
Python standard library
Domain dependencies
```

Not allowed:

```text
FastAPI
SQLAlchemy
HTTP framework
Database driver
Infrastructure implementation
```

### Application

Allowed:

```text
Domain
Application abstractions
```

Avoid:

```text
FastAPI-specific behavior
SQLAlchemy-specific behavior
HTTP implementation details
```

### API

Allowed:

```text
FastAPI
Pydantic
Application
Domain DTO/concepts where appropriate
```

Should not:

```text
Execute SQL directly
Implement business rules
Instantiate database infrastructure ad hoc
```

### Infrastructure

Allowed:

```text
SQLAlchemy
PostgreSQL driver
HTTP clients
Redis
Message brokers
External SDKs
```

---

# 22. What should NOT be included in the microservice repository

The following are explicitly external unless a project-specific decision states otherwise:

```text
PostgreSQL server
PostgreSQL operational configuration
Liquibase runtime
Liquibase changelog repository
Database deployment process
Database backups
Database credentials
Infrastructure secrets
Production infrastructure definitions
```

The microservice repository contains the application code and its required runtime/build configuration, not the entire infrastructure platform.

---

# 23. Recommended runtime dependency flow

The complete request flow should normally look like:

```text
Client
  |
  v
FastAPI Router
  |
  v
Request Schema
  |
  v
Application Use Case
  |
  +----------------------+
  |                      |
  v                      v
Domain Rules       Repository Port
                         |
                         v
                  SQLAlchemy Repository
                         |
                         v
                     PostgreSQL
```

The response follows the inverse direction:

```text
PostgreSQL
    |
    v
SQLAlchemy Model
    |
    v
Repository
    |
    v
Domain/Application
    |
    v
Response Schema
    |
    v
HTTP Response
```

---

# 24. Definition of Done

A microservice implementation is considered complete when:

- [ ] Project follows the standard directory structure.
- [ ] API routes are separated using `APIRouter`.
- [ ] API schemas are separated from database models.
- [ ] Business logic is not implemented inside endpoints.
- [ ] Application use cases are clearly identified.
- [ ] Domain rules are isolated when business complexity requires them.
- [ ] SQLAlchemy is isolated in infrastructure.
- [ ] PostgreSQL version is documented.
- [ ] Database schema changes are managed externally through Liquibase.
- [ ] No Alembic/migration framework is embedded in the microservice.
- [ ] Configuration is centralized and typed.
- [ ] Secrets are externalized.
- [ ] Ruff passes.
- [ ] Ruff formatting passes.
- [ ] mypy passes.
- [ ] Unit tests pass.
- [ ] Integration tests pass where applicable.
- [ ] API documentation/OpenAPI is available.
- [ ] Health/readiness endpoints are implemented where required.
- [ ] Docker image can be built reproducibly.
- [ ] CI quality gates pass.
- [ ] README documents how to run and test the service.

---

# 25. Reference architecture summary

The standard can be summarized as:

```text
                        MICROservice
┌─────────────────────────────────────────────────────────┐
│                                                         │
│  API                                                    │
│  ├── FastAPI                                             │
│  ├── Routers                                             │
│  ├── Request/Response schemas                            │
│  └── Dependencies                                        │
│                         │                               │
│                         ▼                               │
│  APPLICATION                                             │
│  ├── Use cases                                           │
│  ├── Services                                            │
│  └── Ports/interfaces                                    │
│                         │                               │
│                         ▼                               │
│  DOMAIN                                                  │
│  ├── Entities                                            │
│  ├── Value Objects (when justified)                      │
│  ├── Business Rules                                      │
│  └── Domain exceptions                                   │
│                                                         │
│  INFRASTRUCTURE                                          │
│  ├── SQLAlchemy                                          │
│  ├── PostgreSQL adapter                                  │
│  ├── External API clients                                │
│  └── Other technical integrations                        │
│                                                         │
└───────────────────────────┬─────────────────────────────┘
                            │
                            ▼
                 EXTERNAL INFRASTRUCTURE
                 ┌──────────────────────┐
                 │ PostgreSQL           │
                 │ Managed externally   │
                 └──────────┬───────────┘
                            │
                 schema changes
                            │
                            ▼
                 ┌──────────────────────┐
                 │ Liquibase            │
                 │ External DB project  │
                 └──────────────────────┘
```

---

# 26. Official references

## FastAPI

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Bigger Applications – Multiple Files](https://fastapi.tiangolo.com/tutorial/bigger-applications/)
- [Dependencies](https://fastapi.tiangolo.com/tutorial/dependencies/)
- [Lifespan Events](https://fastapi.tiangolo.com/advanced/events/)
- [Testing](https://fastapi.tiangolo.com/tutorial/testing/)

## SQLAlchemy

- [SQLAlchemy 2.x Documentation](https://docs.sqlalchemy.org/en/21/)
- [SQLAlchemy ORM](https://docs.sqlalchemy.org/en/21/orm/)
- [SQLAlchemy AsyncIO](https://docs.sqlalchemy.org/en/21/orm/extensions/asyncio.html)

## Pydantic

- [Pydantic Documentation](https://docs.pydantic.dev/)
- [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)

## Code Quality

- [Ruff Documentation](https://docs.astral.sh/ruff/)
- [Ruff Configuration](https://docs.astral.sh/ruff/configuration/)
- [mypy Documentation](https://mypy.readthedocs.io/)
- [mypy – Strict Mode](https://mypy.readthedocs.io/en/stable/getting_started.html)

## Testing

- [pytest Documentation](https://docs.pytest.org/en/stable/)

## Python Project Standards

- [Python Packaging User Guide](https://packaging.python.org/)
- [pyproject.toml Specification](https://packaging.python.org/en/latest/specifications/pyproject-toml/)

## Database Management

- [Liquibase Documentation](https://docs.liquibase.com/)
- [Liquibase – Introduction](https://docs.liquibase.com/community/implementation-guide-5-0-4/intro-to-liquibase)
- [Liquibase – What is a Changelog?](https://docs.liquibase.com/community/user-guide-5-0-4/what-is-a-changelog)
- [Liquibase – Changelog Structure](https://docs.liquibase.com/secure/set-up-secure-automation-6-0/structure-your-changelog/how-should-i-structure-my-changelog)

---

# 27. Final architectural position

This standard adopts:

```text
FastAPI
    +
Clean/Layered Architecture
    +
Pragmatic DDD
    +
SQLAlchemy 2.x
    +
PostgreSQL externally managed
    +
Liquibase externally managed
    +
Pydantic
    +
Ruff
    +
mypy
    +
pytest
```

The objective is not to maximize the number of architectural patterns.

The objective is to create microservices that are:

- consistent,
- understandable,
- testable,
- statically checked,
- independently maintainable,
- reproducible,
- and ready to evolve without coupling the API, business logic, and database implementation.
