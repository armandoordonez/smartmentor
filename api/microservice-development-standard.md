# Arquitectura estándar para microservicios FastAPI

**Estado:** Adoptado. Estándar de referencia para los microservicios FastAPI de SmartMentor (rev. 2, 2026-10-07)  
**Alcance:** Microservicios backend desarrollados con Python/FastAPI  
**Arquitectura:** Por capas / Clean Architecture, con puertos y adaptadores donde se justifique  
**Base de datos:** PostgreSQL 17 + pgvector 0.8.7, gestionada fuera de la aplicación ([ADR 0001](../docs/adr/0001-postgres-pgvector.md))  
**Versionado de la base de datos:** Liquibase 5.0.4, gestionado fuera de la aplicación ([ADR 0002](../docs/adr/0002-liquibase-schema-versioning.md))  
**Calidad:** Ruff + mypy + pytest  
**Python:** 3.12 (fijado)  
**Gestión de dependencias:** uv + `uv.lock`

### Historial de revisiones

| Rev. | Fecha | Cambios |
| --- | --- | --- |
| 1 | 2026-10 | Estándar propuesto inicial. |
| 2 | 2026-10-07 | Adoptado para SmartMentor. Agrega: <br>• excepción monorepo (§3, §6, §22);<br>• organización por dominio (§3.1, [ADR 0003](../docs/adr/0003-api-domain-first-layout.md));<br>• versiones fijadas (§5.2) y pgvector (§5.5);<br>• control de desalineación entre esquema y modelos (§6);<br>• convenciones de API (§12) y errores RFC 9457 (§14);<br>• logs sin datos personales (§15);<br>• secciones §28 a §35: convenciones de datos, borrado lógico y auditoría, zona horaria, health/readiness, unidad de trabajo, imagen Docker, integración con la capa de IA y seguridad base.<br>También corrige errores tipográficos y enlaces de referencia. Documento traducido al español. |

---

## 1. Propósito

Este documento define una arquitectura estándar, mantenible y repetible para desarrollar microservicios FastAPI.

El objetivo es crear un microservicio nuevo con las mismas convenciones de estructura, arquitectura, calidad, pruebas y operación, sin que cada equipo tenga que redefinir la estructura del proyecto.

El estándar es pragmático a propósito: establece límites claros y reglas de dependencia sin exigir complejidad arquitectónica innecesaria.

---

## 2. Principios de arquitectura

El microservicio debe seguir estos principios:

1. **Separación de responsabilidades**
   - La capa HTTP/API no contiene reglas de negocio.
   - Las reglas de negocio no dependen de FastAPI.
   - El código de dominio y de aplicación no depende directamente de SQLAlchemy.
   - Las implementaciones de infraestructura se pueden reemplazar sin cambiar las reglas de negocio.

2. **Dirección de las dependencias**

   Las dependencias apuntan hacia los conceptos de negocio:

   ```text
   API
    |
    v
   Aplicación
    |
    v
   Dominio
   ```

   La infraestructura implementa las interfaces o puertos que requieren la aplicación o el dominio:

   ```text
                     +----------------------+
                     |   Infraestructura    |
                     | SQLAlchemy/PostgreSQL|
                     +----------+-----------+
                                |
                                | implementa
                                v
   +----------+       +----------------------+
   |   API    | ----> |      Aplicación      |
   +----------+       +----------+-----------+
                                |
                                v
                       +----------------+
                       |    Dominio     |
                       +----------------+
   ```

3. **Límites explícitos**
   - Cada capa tiene una responsabilidad definida.
   - El acceso entre capas es intencional.
   - Los modelos de base de datos no son automáticamente los esquemas de la API.
   - Las integraciones externas quedan aisladas en infraestructura.

4. **Testabilidad**
   - La lógica de dominio y de aplicación se puede probar sin arrancar FastAPI y, siempre que sea posible, sin una instancia real de PostgreSQL.

5. **Configuración fuera del código**
   - La configuración propia de cada ambiente y los secretos no se suben al repositorio.
   - El microservicio consume la configuración a través de una capa de configuración tipada.

6. **Ciclo de vida de la base de datos fuera de la aplicación**
   - PostgreSQL es una dependencia de infraestructura externa.
   - Crear y migrar el esquema no es responsabilidad de la aplicación FastAPI.
   - Liquibase gestiona los cambios de esquema de forma externa.

---

## 3. Estructura de proyecto propuesta

La estructura recomendada es:

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

### Importante

El directorio `migrations/` **no forma parte de este microservicio**, a propósito.

Liquibase pertenece al proceso de gestión y despliegue de la base de datos. Debe tener su propio repositorio o proyecto, o una estructura de infraestructura externa, según la estrategia de gestión de bases de datos de la organización.

PostgreSQL también es externo a este repositorio.

### Excepción monorepo (SmartMentor)

El brief del proyecto exige **un solo repositorio por programa**, para que cada cohorte entregue todo en un mismo lugar. En ese caso el proyecto de base de datos vive **al lado** del microservicio, nunca dentro de él:

```text
smartmentor/
├── api/          # este microservicio: solo código de aplicación
└── database/     # proyecto de BD externo: changelogs de Liquibase, bootstrap, respaldos, volumen local
```

Las reglas de §6 y §22 siguen aplicando. El microservicio no importa, ejecuta ni empaqueta nada de `database/`: solo se conecta a la base PostgreSQL resultante.

## 3.1 Organización por dominio (variante aceptada)

Cuando un servicio tiene varios dominios de negocio, el código puede organizarse **por dominio, con las capas dentro de cada uno**, en lugar de por capa. Es la organización que adoptó SmartMentor ([ADR 0003](../docs/adr/0003-api-domain-first-layout.md)):

```text
api/
├── app/
│   ├── main.py
│   ├── core/              # configuración, base de datos (engine/sesión), logging, excepciones
│   ├── common/            # constantes/enums, entidad base, modelo base, paginación, repositorio genérico
│   ├── health/            # /health y /ready
│   └── domains/
│       └── <domain>/
│           ├── controller.py       # capa API: APIRouter, códigos de estado
│           ├── schemas.py          # capa API: contratos de request/response
│           ├── service.py          # capa de aplicación: casos de uso
│           ├── entities.py         # capa de dominio: entidades y reglas (Python puro)
│           ├── exceptions.py       # capa de dominio: errores de negocio
│           ├── repository.py       # capa de dominio: interfaz del repositorio (Protocol)
│           ├── models.py           # infraestructura: modelos SQLAlchemy
│           └── repository_impl.py  # infraestructura: repositorio SQLAlchemy
├── tests/
│   ├── unit/<domain>/
│   └── integration/<domain>/
├── pyproject.toml
├── uv.lock
├── Dockerfile
└── .dockerignore
```

Las **reglas de dependencia de §21 se aplican por archivo**, no por carpeta:

| Archivo | Capa | Puede importar | No puede importar |
| --- | --- | --- | --- |
| `entities.py`, `exceptions.py`, `repository.py` | Dominio | stdlib, `common.entities`, `common.constants` | FastAPI, SQLAlchemy, Pydantic |
| `service.py` | Aplicación | capa de dominio propia, interfaces de otros dominios | FastAPI, SQLAlchemy |
| `controller.py`, `schemas.py` | API | FastAPI, Pydantic, `service.py` | `models.py`, `repository_impl.py`, SQL directo |
| `models.py`, `repository_impl.py` | Infraestructura | SQLAlchemy, pgvector, `repository.py` y `entities.py` propios | FastAPI |

Un dominio nunca importa `models.py` ni `repository_impl.py` de otro dominio.

---

# 4. Responsabilidades de cada capa

## 4.1 Capa API

Ubicación:

```text
app/api/
```

Responsable de:

- Endpoints HTTP.
- Definición de URLs y rutas.
- Códigos de estado HTTP.
- Esquemas de request y response.
- Integración con autenticación y autorización.
- Inyección de dependencias de FastAPI.
- Traducir los errores de aplicación a respuestas HTTP.

La capa API **no** contiene reglas de negocio ni consultas SQL directas.

### Ejemplo

```python
@router.post("/users")
async def create_user(
    request: UserCreate,
    service: UserService = Depends(get_user_service),
) -> UserResponse:
    user = await service.create_user(request)
    return UserResponse.from_domain(user)
```

El endpoint coordina la petición; no implementa el proceso de negocio.

---

## 4.2 Capa de aplicación

Ubicación:

```text
app/application/
```

Responsable de los casos de uso de la aplicación.

Ejemplos:

```text
CreateUser
UpdateUser
GetUser
SearchUsers
DeleteUser
GenerateReport
ProcessOrder
```

Esta capa coordina:

- Reglas de dominio.
- Interfaces de repositorio.
- Puertos de servicios externos.
- Transacciones y orquestación de los casos de uso.

No depende de FastAPI ni de repositorios SQLAlchemy concretos.

Ejemplo:

```text
Petición HTTP
     |
     v
API
     |
     v
CreateUserService
     |
     +----> Reglas de dominio de User
     |
     +----> UserRepository
     |
     v
Respuesta HTTP
```

---

## 4.3 Capa de dominio

Ubicación:

```text
app/domain/
```

El dominio representa los conceptos y las reglas de negocio.

Debe contener preferiblemente código Python normal y no requerir FastAPI ni SQLAlchemy.

Elementos posibles:

```text
Entidad (Entity)
Objeto de valor (Value Object)
Excepción de dominio (Domain Exception)
Interfaz de repositorio (Repository Interface)
Servicio de dominio (Domain Service)
Regla de negocio (Business Rule)
```

Ejemplo:

```python
class User:
    def activate(self) -> None:
        if self.status == UserStatus.BLOCKED:
            raise UserCannotBeActivated()

        self.status = UserStatus.ACTIVE
```

Lo importante es que la regla existe con independencia de HTTP y de PostgreSQL.

---

## 4.4 Capa de infraestructura

Ubicación:

```text
app/infrastructure/
```

Responsable de las implementaciones técnicas:

- SQLAlchemy.
- Conectividad con PostgreSQL.
- Implementaciones de repositorios.
- Clientes HTTP externos.
- Clientes Redis.
- Brokers de mensajes.
- Otras integraciones técnicas.

Por ejemplo:

```text
domain.repositories.UserRepository
              ^
              |
              | implementa
              |
infrastructure.database.repositories.UserRepositorySQLAlchemy
```

La capa de dominio o de aplicación depende de la abstracción, no de la implementación concreta con SQLAlchemy.

---

# 5. Arquitectura de la base de datos

## 5.1 PostgreSQL es externo

PostgreSQL no forma parte del árbol de código fuente de la aplicación.

El microservicio solo define el contrato necesario para conectarse a la base de datos.

Configuración de ejemplo:

```text
DATABASE_HOST
DATABASE_PORT
DATABASE_NAME
DATABASE_USER
DATABASE_PASSWORD
```

o una configuración de conexión equivalente gestionada de forma externa.

El servidor PostgreSQL, el ciclo de vida de la base, las credenciales, los respaldos, la replicación y la administración operativa pertenecen a la capa de infraestructura o plataforma.

---

## 5.2 Versión de PostgreSQL

La versión de PostgreSQL de cada ambiente debe estar documentada explícitamente.

SmartMentor:

```text
PostgreSQL: 17.x
pgvector:   0.8.7
Imagen:     pgvector/pgvector:0.8.7-pg17-bookworm
```

Ver [ADR 0001](../docs/adr/0001-postgres-pgvector.md).

La versión exacta se controla como decisión de infraestructura o plataforma, y el microservicio no debe cambiarla de forma silenciosa.

El microservicio debe probarse contra la versión de PostgreSQL soportada oficialmente por el ambiente de destino.

---

## 5.3 SQLAlchemy

SQLAlchemy 2.x es la tecnología de persistencia del microservicio.

Responsabilidades recomendadas:

```text
Modelos SQLAlchemy
    -> infrastructure/database/models/

Repositorios SQLAlchemy
    -> infrastructure/database/repositories/

Sesión y engine de base de datos
    -> infrastructure/database/session.py
```

En la organización por dominio (§3.1), los modelos y repositorios van en `domains/<domain>/models.py` y `repository_impl.py`, y la sesión en `core/database.py`.

Por defecto, la aplicación no expone los modelos SQLAlchemy como su modelo de dominio.

---

## 5.4 Acceso asíncrono a la base de datos

Para endpoints FastAPI asíncronos se puede usar el soporte asyncio de SQLAlchemy mediante:

```text
AsyncEngine
AsyncSession
async_sessionmaker
```

La sesión de base de datos debe tener el alcance correcto: la petición o el caso de uso.

Una misma `AsyncSession` no debe compartirse de forma concurrente entre tareas asyncio no relacionadas.

Referencia:

https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html

---

## 5.5 pgvector

Las columnas vectoriales se mapean con el paquete de Python `pgvector`:

```python
from pgvector.sqlalchemy import Vector

embedding: Mapped[list[float] | None] = mapped_column(Vector(settings.embedding_dimension))
```

Reglas:

- **La dimensión es un contrato** compartido por el esquema (Liquibase), la configuración (`EMBEDDING_DIMENSION`) y el modelo de embeddings. Los tres deben coincidir, y la aplicación valida la longitud antes de escribir.
- Todos los vectores que se comparan entre sí deben venir **del mismo modelo de embeddings**.
- La búsqueda por similitud usa distancia coseno (`<=>`), respaldada por índices HNSW (`vector_cosine_ops`) que crea Liquibase.
- HNSW sobre `vector` admite hasta 2000 dimensiones (`halfvec`, hasta 4000).
- Las consultas vectoriales viven en `repository_impl.py`, nunca en servicios ni en controladores.

---

# 6. Versionado del esquema con Liquibase

El versionado del esquema de la base de datos está explícitamente **fuera del microservicio FastAPI**.

La división de responsabilidades es:

```text
+--------------------------------+
| Microservicio FastAPI          |
|                                |
| Modelos SQLAlchemy             |
| Implementaciones de repositorio|
| Configuración de conexión a BD |
+---------------+----------------+
                |
                | se conecta a
                v
+--------------------------------+
| PostgreSQL                     |
| Infraestructura externa        |
+---------------^----------------+
                |
                | cambios de esquema
                |
+--------------------------------+
| Liquibase                      |
| Proyecto/proceso de BD externo |
|                                |
| changelogs / changesets        |
| despliegue de la base de datos |
+--------------------------------+
```

### Reglas

- El proyecto FastAPI no contiene Alembic.
- El proyecto FastAPI no ejecuta migraciones de esquema automáticamente al arrancar.
- El proyecto FastAPI no crea tablas de producción automáticamente.
- Los cambios de esquema se hacen con Liquibase.
- Los changelogs de Liquibase se versionan fuera del microservicio (en SmartMentor, `database/liquibase/`; ver la excepción monorepo en §3).
- Los pipelines de despliegue coordinan las versiones de la aplicación y de la base de datos.
- Un changeset ya aplicado nunca se edita: las correcciones van en un changeset nuevo.
- Los cambios incompatibles (renombrar o eliminar) siguen el patrón **expandir y contraer**:
  1. agregar la estructura nueva;
  2. desplegar la aplicación que la usa;
  3. eliminar la estructura vieja en un changeset posterior.

### Control de desalineación entre esquema y modelos

Como la aplicación no es dueña de las migraciones, los modelos SQLAlchemy **reflejan** el esquema que crea Liquibase y no deben apartarse de él:

- Los modelos nunca llaman a `Base.metadata.create_all()`, salvo en pruebas que necesiten explícitamente un esquema desechable.
- Una prueba de integración corre contra una base migrada por Liquibase y comprueba que cada tabla y columna mapeada exista, con tipo y nulabilidad compatibles. Puede hacerse, por ejemplo, reflejando el esquema con `inspect()` de SQLAlchemy.
- Un cambio de Liquibase que afecte columnas mapeadas se acepta junto con el cambio correspondiente del modelo, en el mismo pull request.

Liquibase describe los cambios de la base de datos con changelogs y changesets, y puede desplegar los que aún no se han aplicado. Su documentación también recomienda mantener los changelogs bajo control de versiones.

Referencias:

- https://docs.liquibase.com/community/implementation-guide-5-0-4/intro-to-liquibase
- https://docs.liquibase.com/community/user-guide-5-0-4/what-is-a-changelog
- Guía de operación de SmartMentor: [`database/liquibase/README.md`](../database/liquibase/README.md)

---

# 7. Diseño guiado por el dominio (DDD): qué significa en este estándar

DDD **no** debe interpretarse como la obligación de implementar una gran arquitectura DDD académica en cada microservicio.

El estándar usa DDD de forma selectiva.

## 7.1 Qué es obligatorio

El microservicio debe identificar y aislar sus conceptos y reglas de negocio relevantes.

Por ejemplo:

```text
Customer
Order
Contract
Property
Payment
Invoice
Project
```

Si una regla de negocio pertenece a `Order`, no debe quedar escondida dentro de un controlador HTTP o de una consulta SQL.

---

## 7.2 Qué es opcional

Los siguientes elementos se introducen solo cuando la complejidad del dominio los justifica:

- Objetos de valor (Value Objects).
- Servicios de dominio.
- Agregados.
- Eventos de dominio.
- Varios contextos acotados (bounded contexts).
- Abstracciones de repositorio complejas.
- Entidades de dominio ricas.

Un servicio CRUD con reglas simples no necesita todos estos conceptos.

### Ejemplo simple

Para un catálogo básico:

```text
API
  |
  v
Servicio de aplicación
  |
  v
Repositorio
  |
  v
PostgreSQL
```

No hace falta crear decenas de clases de dominio solo porque el proyecto usa el término DDD.

Para un proceso complejo:

```text
API
  |
  v
Caso de uso de aplicación
  |
  +--> Agregado
  |      |
  |      +--> Objetos de valor
  |      +--> Reglas de negocio
  |
  +--> Repositorio
  |
  +--> Servicio externo
```

DDD aporta valor cuando las reglas de negocio son lo bastante complejas para justificar un modelado explícito.

### Regla práctica

> **La complejidad determina la cantidad de modelado de dominio.**

Por eso este estándar adopta **principios de DDD donde mejoran el modelado del negocio**, en lugar de exigir "DDD completo" en cada microservicio.

---

# 8. Inyección de dependencias

Las dependencias de FastAPI se usan en el límite de la API, donde se compone la aplicación.

Ejemplo:

```text
Dependencia de FastAPI
       |
       v
Servicio de aplicación
       |
       v
Interfaz de repositorio
       |
       v
Repositorio SQLAlchemy
```

La construcción de dependencias se centraliza, en lugar de instanciar repositorios y sesiones de base de datos dentro de cada endpoint.

Referencia:

https://fastapi.tiangolo.com/tutorial/dependencies/

---

# 9. Composición de la aplicación FastAPI

`app/main.py` debe mantenerse pequeño.

Sus responsabilidades principales son:

- Crear la aplicación FastAPI.
- Configurar el `lifespan`.
- Registrar los routers.
- Registrar los manejadores globales de excepciones.
- Configurar los middlewares (intermediarios de peticiones).
- Configurar los metadatos de la API.

FastAPI recomienda oficialmente separar las aplicaciones grandes en varios módulos con `APIRouter`.

Referencia:

https://fastapi.tiangolo.com/tutorial/bigger-applications/

---

# 10. Ciclo de vida de la aplicación (lifespan)

Los recursos compartidos por la aplicación se pueden inicializar y liberar con el `lifespan` de FastAPI.

Recursos típicos:

```text
Pool de conexiones a la base de datos
Clientes HTTP
Clientes Redis
Clientes de brokers de mensajes
Modelos o recursos compartidos
```

Ejemplo:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Inicializar recursos
    yield
    # Liberar recursos
```

FastAPI recomienda actualmente el mecanismo `lifespan` para la lógica de arranque y apagado.

Referencia:

https://fastapi.tiangolo.com/advanced/events/

---

# 11. Configuración

La configuración debe ser centralizada y tipada.

Ubicación recomendada:

```text
app/core/config.py
```

La capa de configuración es el único punto por el que la aplicación obtiene:

- Configuración de la base de datos.
- URLs de servicios externos.
- Información del ambiente.
- Interruptores de funcionalidad (feature flags).
- Timeouts.
- Configuración de seguridad.
- Cualquier otra configuración de ejecución.

Los secretos nunca se escriben en el código ni se suben al repositorio.

Se usa Pydantic Settings cuando sea apropiado, para cargar configuración tipada desde fuentes externas.

Referencia:

https://docs.pydantic.dev/latest/concepts/pydantic_settings/

---

# 12. Versionado de la API

Las APIs se versionan de forma explícita.

Estructura recomendada:

```text
app/api/v1/
```

Ejemplo:

```text
/api/<service>/v1/users
```

Un contrato de API nuevo e incompatible se introduce normalmente como una versión nueva de la API, en lugar de romper en silencio una versión existente.

Cuando el repositorio contiene un solo servicio, como en SmartMentor, el prefijo es simplemente `/api/v1`.

### Convenciones de recursos

| Operación | Método y ruta | Estado de éxito |
| --- | --- | --- |
| Crear | `POST /api/v1/<resources>` | `201 Created` |
| Consultar por id | `GET /api/v1/<resources>/{id}` | `200 OK` |
| Listar | `GET /api/v1/<resources>?limit=&offset=&active=&<filters>` | `200 OK` |
| Actualizar parcialmente | `PATCH /api/v1/<resources>/{id}` | `200 OK` |
| Inactivar | `PATCH /api/v1/<resources>/{id}/deactivate` | `200 OK` |
| Activar | `PATCH /api/v1/<resources>/{id}/activate` | `200 OK` |

- Las rutas usan nombres de recurso en plural y en kebab-case (`/learning-paths`); los campos JSON usan `snake_case`.
- **No hay endpoints `DELETE`**: los registros se eliminan de forma lógica (§29).
- Las listas se paginan con `limit` (por defecto 20, máximo 100) y `offset`, y devuelven `{ "items": [...], "total": n, "limit": l, "offset": o }`.
- `active` filtra por estado. Si se omite, las listas devuelven solo los registros activos.
- `PATCH` actualiza solo los campos presentes en el cuerpo. Los campos que el caso de uso no permite cambiar los ignora el esquema; no se escriben en silencio.

---

# 13. Esquemas de request y response

Los esquemas de la API se separan de los modelos de persistencia.

Ejemplo:

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

Así se evita que el contrato HTTP quede acoplado directamente al esquema de PostgreSQL.

---

# 14. Manejo de errores

Los errores de negocio y de aplicación se representan de forma explícita.

Ejemplo:

```text
Excepción de dominio
       |
       v
Servicio de aplicación
       |
       v
Manejador de excepciones de la API
       |
       v
Estado HTTP + respuesta de error estandarizada
```

Las respuestas de error siguen la **RFC 9457 (Problem Details for HTTP APIs)**, con `Content-Type: application/problem+json`:

```json
{
  "type": "https://smartmentor/errors/email-already-registered",
  "title": "Email already registered",
  "status": 409,
  "detail": "A user with this email already exists.",
  "instance": "/api/v1/users",
  "code": "EMAIL_ALREADY_REGISTERED",
  "request_id": "6f1c..."
}
```

Correspondencia por defecto:

| Situación | Estado |
| --- | --- |
| Error de validación de la petición | `422` |
| Recurso no encontrado | `404` |
| Conflicto de unicidad o de estado | `409` |
| Violación de una regla de negocio | `422` (con un `code` específico) |
| Error inesperado | `500` (mensaje genérico; el detalle solo en los logs) |

La capa de infraestructura traduce los errores de integridad de la base de datos (únicos, llaves foráneas, `CHECK`) a excepciones de dominio. Así la API nunca expone mensajes de PostgreSQL.

No se deben filtrar a los consumidores de la API:

- Excepciones de SQLAlchemy.
- Errores de PostgreSQL.
- Trazas internas de error (stack traces).
- Secretos.
- Detalles de infraestructura.

---

# 15. Logs

Los logs se centralizan y, donde sea posible, son estructurados.

Deben dar contexto suficiente para diagnosticar peticiones y operaciones, sin exponer secretos ni información sensible.

Campos recomendados:

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

No se registran contraseñas, tokens, cadenas de conexión ni otros secretos.

Reglas adicionales:

- Los logs se escriben como **JSON en stdout**, un evento por línea.
- Un middleware (intermediario de peticiones) asigna un `request_id`: usa `X-Request-ID` si viene en la petición; si no, genera uno. El id se devuelve en la cabecera de la respuesta y se incluye en cada línea de log y en cada respuesta de error.
- **Datos personales** (Ley 1581 de 2012):
  - no se registran nombres, perfiles en texto libre ni respuestas de los estudiantes;
  - los emails se enmascaran (`j***@domain.com`);
  - los logs referencian a los usuarios por su `id`.
- Las fechas en los logs usan ISO-8601 con desfase horario (`America/Bogota`, ver §30).

---

# 16. Ruff

Ruff es el linter y formateador estándar.

La configuración recomendada se centraliza en:

```text
pyproject.toml
```

Ejemplo:

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

Comandos mínimos en CI:

```bash
ruff check .
ruff format --check .
```

Referencia:

https://docs.astral.sh/ruff/configuration/

---

# 17. mypy

El proyecto usa verificación estática de tipos.

Configuración base recomendada:

```toml
[tool.mypy]
python_version = "3.12"
strict = true
```

La configuración final solo puede desactivar verificaciones específicas cuando haya una razón técnica documentada.

Comando mínimo en CI:

```bash
mypy app
```

El objetivo es cero errores de tipos.

Referencia:

https://mypy.readthedocs.io/en/stable/getting_started.html

---

# 18. pyproject.toml

La configuración del proyecto y de las herramientas se centraliza en `pyproject.toml` siempre que sea práctico.

Puede contener:

```text
Metadatos del proyecto
Dependencias
Configuración de Ruff
Configuración de mypy
Configuración de pytest
Configuración de build
```

La Python Packaging User Guide define `pyproject.toml` como el archivo de configuración moderno para el empaquetado y las herramientas relacionadas.

Referencia:

https://packaging.python.org/en/latest/guides/writing-pyproject-toml/

---

# 19. Estrategia de pruebas

Las pruebas se dividen como mínimo en:

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

En la organización por dominio (§3.1) se usan `tests/unit/<domain>/` y `tests/integration/<domain>/`.

## Pruebas unitarias

Prueban el comportamiento de negocio y de aplicación, siempre que sea posible sin la infraestructura completa.

Ejemplos:

```text
Reglas de dominio
Servicios de aplicación
Validaciones
Condiciones de error
Casos de uso
```

## Pruebas de integración

Prueban la integración con:

```text
FastAPI
Capa HTTP
PostgreSQL
SQLAlchemy
Integraciones externas
```

La infraestructura exacta de las pruebas de integración la define la estrategia de CI del proyecto.

pytest es el framework de pruebas estándar.

Referencia:

https://docs.pytest.org/en/stable/

---

# 20. Controles de calidad

Cada pull request ejecuta como mínimo:

```bash
ruff check .
ruff format --check .
mypy app
pytest
```

Cuando se exige cobertura:

```bash
pytest --cov=app --cov-report=term-missing
```

Pipeline recomendado:

```text
Pull request
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
Pruebas unitarias
     |
     v
Pruebas de integración
     |
     v
Cobertura
     |
     v
Construcción de la imagen
     |
     v
Despliegue
```

---

# 21. Reglas de dependencia

Las siguientes reglas de dependencia son obligatorias.

### Dominio

Permitido:

```text
Biblioteca estándar de Python
Dependencias del propio dominio
```

No permitido:

```text
FastAPI
SQLAlchemy
Framework HTTP
Driver de base de datos
Implementaciones de infraestructura
```

### Aplicación

Permitido:

```text
Dominio
Abstracciones de aplicación
```

Evitar:

```text
Comportamiento propio de FastAPI
Comportamiento propio de SQLAlchemy
Detalles de implementación HTTP
```

### API

Permitido:

```text
FastAPI
Pydantic
Aplicación
DTOs o conceptos del dominio cuando corresponda
```

No debe:

```text
Ejecutar SQL directamente
Implementar reglas de negocio
Instanciar infraestructura de base de datos sobre la marcha
```

### Infraestructura

Permitido:

```text
SQLAlchemy
Driver de PostgreSQL
Clientes HTTP
Redis
Brokers de mensajes
SDKs externos
```

---

# 22. Qué NO se incluye en el repositorio del microservicio

Lo siguiente es explícitamente externo, salvo que una decisión propia del proyecto indique otra cosa:

```text
Servidor PostgreSQL
Configuración operativa de PostgreSQL
Runtime de Liquibase
Repositorio de changelogs de Liquibase
Proceso de despliegue de la base de datos
Respaldos de la base de datos
Credenciales de la base de datos
Secretos de infraestructura
Definiciones de infraestructura de producción
```

El repositorio del microservicio contiene el código de la aplicación y la configuración necesaria para construirla y ejecutarla, no toda la plataforma de infraestructura.

**Decisión propia de SmartMentor:** como el brief exige un solo repositorio, el contenedor local de PostgreSQL, Liquibase, los scripts de bootstrap y los respaldos van en el proyecto hermano `database/` (§3, excepción monorepo). Quedan fuera de `api/`, y las credenciales de la base viven en `.env`, que nunca se sube al repositorio.

---

# 23. Flujo de dependencias recomendado en ejecución

El flujo completo de una petición suele verse así:

```text
Cliente
  |
  v
Router de FastAPI
  |
  v
Esquema de request
  |
  v
Caso de uso de aplicación
  |
  +----------------------+
  |                      |
  v                      v
Reglas de dominio   Puerto de repositorio
                         |
                         v
                  Repositorio SQLAlchemy
                         |
                         v
                     PostgreSQL
```

La respuesta sigue la dirección inversa:

```text
PostgreSQL
    |
    v
Modelo SQLAlchemy
    |
    v
Repositorio
    |
    v
Dominio/Aplicación
    |
    v
Esquema de response
    |
    v
Respuesta HTTP
```

---

# 24. Definición de terminado

Una implementación de microservicio se considera completa cuando:

- [ ] El proyecto sigue la estructura de directorios del estándar.
- [ ] Las rutas de la API están separadas con `APIRouter`.
- [ ] Los esquemas de la API están separados de los modelos de base de datos.
- [ ] La lógica de negocio no está implementada dentro de los endpoints.
- [ ] Los casos de uso de aplicación están claramente identificados.
- [ ] Las reglas de dominio están aisladas cuando la complejidad del negocio lo requiere.
- [ ] SQLAlchemy está aislado en infraestructura.
- [ ] La versión de PostgreSQL está documentada.
- [ ] Los cambios de esquema se gestionan externamente con Liquibase.
- [ ] No hay Alembic ni otro framework de migraciones dentro del microservicio.
- [ ] La configuración está centralizada y tipada.
- [ ] Los secretos están externalizados.
- [ ] `ruff check` pasa.
- [ ] `ruff format --check` pasa.
- [ ] mypy pasa.
- [ ] Las pruebas unitarias pasan.
- [ ] Las pruebas de integración pasan, donde aplique.
- [ ] La documentación OpenAPI está disponible.
- [ ] Los endpoints de health y readiness están implementados (§31).
- [ ] No hay endpoints `DELETE`, y existen inactivar y activar (§29).
- [ ] Los errores siguen la RFC 9457 (§14).
- [ ] Las fechas tienen zona horaria (`America/Bogota`, §30).
- [ ] El usuario de la aplicación se propaga a la auditoría de la base (§29).
- [ ] La prueba de desalineación entre esquema y modelos pasa (§6).
- [ ] La imagen Docker se construye de forma reproducible.
- [ ] Los controles de calidad de CI pasan.
- [ ] El README documenta cómo ejecutar y probar el servicio.

---

# 25. Resumen de la arquitectura de referencia

El estándar se resume así:

```text
                        MICROSERVICIO
┌─────────────────────────────────────────────────────────┐
│                                                         │
│  API                                                    │
│  ├── FastAPI                                            │
│  ├── Routers                                            │
│  ├── Esquemas de request/response                       │
│  └── Dependencias                                       │
│                         │                               │
│                         ▼                               │
│  APLICACIÓN                                             │
│  ├── Casos de uso                                       │
│  ├── Servicios                                          │
│  └── Puertos/interfaces                                 │
│                         │                               │
│                         ▼                               │
│  DOMINIO                                                │
│  ├── Entidades                                          │
│  ├── Objetos de valor (cuando se justifica)             │
│  ├── Reglas de negocio                                  │
│  └── Excepciones de dominio                             │
│                                                         │
│  INFRAESTRUCTURA                                        │
│  ├── SQLAlchemy                                         │
│  ├── Adaptador de PostgreSQL                            │
│  ├── Clientes de APIs externas                          │
│  └── Otras integraciones técnicas                       │
│                                                         │
└───────────────────────────┬─────────────────────────────┘
                            │
                            ▼
                 INFRAESTRUCTURA EXTERNA
                 ┌──────────────────────┐
                 │ PostgreSQL           │
                 │ Gestión externa      │
                 └──────────┬───────────┘
                            │
                 cambios de esquema
                            │
                            ▼
                 ┌──────────────────────┐
                 │ Liquibase            │
                 │ Proyecto de BD       │
                 │ externo (database/)  │
                 └──────────────────────┘
```

---

# 26. Referencias oficiales

## FastAPI

- [Documentación de FastAPI](https://fastapi.tiangolo.com/)
- [Aplicaciones grandes: varios archivos](https://fastapi.tiangolo.com/tutorial/bigger-applications/)
- [Dependencias](https://fastapi.tiangolo.com/tutorial/dependencies/)
- [Eventos de lifespan](https://fastapi.tiangolo.com/advanced/events/)
- [Pruebas](https://fastapi.tiangolo.com/tutorial/testing/)

## SQLAlchemy

- [Documentación de SQLAlchemy 2.x](https://docs.sqlalchemy.org/en/20/)
- [SQLAlchemy ORM](https://docs.sqlalchemy.org/en/20/orm/)
- [SQLAlchemy AsyncIO](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)

## Pydantic

- [Documentación de Pydantic](https://docs.pydantic.dev/)
- [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)

## Calidad de código

- [Documentación de Ruff](https://docs.astral.sh/ruff/)
- [Configuración de Ruff](https://docs.astral.sh/ruff/configuration/)
- [Documentación de mypy](https://mypy.readthedocs.io/)
- [mypy: modo estricto](https://mypy.readthedocs.io/en/stable/getting_started.html)

## Pruebas

- [Documentación de pytest](https://docs.pytest.org/en/stable/)

## Estándares de proyectos Python

- [Python Packaging User Guide](https://packaging.python.org/)
- [Especificación de pyproject.toml](https://packaging.python.org/en/latest/specifications/pyproject-toml/)

## Gestión de base de datos

- [Documentación de Liquibase](https://docs.liquibase.com/)
- [Liquibase: introducción](https://docs.liquibase.com/community/implementation-guide-5-0-4/intro-to-liquibase)
- [Liquibase: qué es un changelog](https://docs.liquibase.com/community/user-guide-5-0-4/what-is-a-changelog)
- [Liquibase y Docker](https://docs.liquibase.com/workflows/liquibase-community/using-liquibase-and-docker.html)

## PostgreSQL / pgvector

- [Política de versiones de PostgreSQL](https://www.postgresql.org/support/versioning/)
- [pgvector](https://github.com/pgvector/pgvector)

## APIs HTTP

- [RFC 9457: Problem Details for HTTP APIs](https://www.rfc-editor.org/rfc/rfc9457)

---

# 27. Posición arquitectónica final

Este estándar adopta:

```text
FastAPI
    +
Arquitectura limpia / por capas
    +
DDD pragmático
    +
SQLAlchemy 2.x
    +
PostgreSQL gestionado externamente
    +
Liquibase gestionado externamente
    +
Pydantic
    +
Ruff
    +
mypy
    +
pytest
```

El objetivo no es maximizar la cantidad de patrones de arquitectura.

El objetivo es construir microservicios que sean:

- consistentes,
- comprensibles,
- testeables,
- verificados estáticamente,
- mantenibles de forma independiente,
- reproducibles,
- y listos para evolucionar sin acoplar la API, la lógica de negocio y la implementación de la base de datos.

---

# Parte II: estándares adicionales (rev. 2)

Las siguientes secciones se agregaron en la revisión 2 para SmartMentor. Complementan las anteriores; no las reemplazan.

# 28. Convenciones de nombres de datos

| Elemento | Convención | Ejemplo |
| --- | --- | --- |
| Tablas | Inglés, `snake_case`, plural | `learning_paths` |
| Columnas | Inglés, `snake_case` | `created_at`, `owner_user_id` |
| Llave primaria | `id bigint` tomada de una secuencia explícita `<table>_id_seq` | `users_id_seq` |
| Columna de llave foránea | `<tabla_referenciada_en_singular>_id` | `course_id` |
| Índices y restricciones | `<table>_<columns>_<suffix>` (`_uq`, `_idx`, `_fk`, `_ck`) | `users_email_uq` |
| Comentarios de tablas y columnas | Inglés (`remarks` de Liquibase) | — |
| Código Python, rutas de la API, campos JSON | Inglés | `GET /api/v1/learning-paths` |
| Documentación (README, ADR, `.md`) | Español | — |

Columnas comunes de toda tabla de negocio:

```text
id          bigint      PK, default nextval('<table>_id_seq')
active      boolean     NOT NULL DEFAULT true
created_at  timestamptz NOT NULL DEFAULT now()
```

`common/models.py` ofrece un mixin con estas columnas, y `common/entities.py` la entidad base equivalente.

# 29. Borrado lógico y auditoría

**Borrado lógico**

- La aplicación nunca borra registros físicamente. La API expone `deactivate` y `activate` en lugar de `DELETE` (§12).
- `active` es el indicador técnico del ciclo de vida. Es independiente de los estados de negocio, como `courses.status`.
- Los repositorios filtran `active = true` por defecto, y aceptan un filtro explícito para incluir las filas inactivas.

**Auditoría (en la base de datos)**

- Cada tabla de negocio `<table>` tiene su tabla `<table>_audit`. La llena el trigger `<table>_audit_trg` mediante la función común `audit_row_change()`, que crea Liquibase.
- El trigger guarda `old_data` y `new_data` en `jsonb`, además de `operation`, `changed_at`, `db_user` y `app_user_id`.
- La aplicación **debe** propagar el usuario que actúa a la base de datos en cada transacción que escribe:

  ```python
  await session.execute(
      text("SELECT set_config('smartmentor.current_user_id', :user_id, true)"),
      {"user_id": str(current_user_id)},
  )
  ```

  El `true` hace que el valor sea local a la transacción, lo que es seguro con pools de conexiones. Mientras no exista autenticación (decisión pendiente D-03), el usuario se toma de la cabecera `X-User-Id`, con `system` como valor por defecto. Esa cabecera es solo un dato para la auditoría: no autentica ni autoriza, y se elimina cuando el usuario salga del token.

# 30. Política de zona horaria

- La base de datos, los contenedores y la aplicación funcionan con `America/Bogota`.
- Toda columna de fecha y hora es `timestamptz`, y todo `datetime` de Python lleva zona horaria. No se permiten fechas sin zona (naive).
- La aplicación fija la zona horaria de la sesión al conectarse (`server_settings={"timezone": "America/Bogota"}` en asyncpg). Es un respaldo por si en un ambiente gestionado no se puede cambiar el valor por defecto de la base.
- La API serializa las fechas en ISO-8601 con desfase, por ejemplo `2026-10-07T09:30:00-05:00`.
- La zona horaria es configurable (`APP_TIMEZONE`), pero debe coincidir con la de la base.

# 31. Verificación de salud y disponibilidad (health y readiness)

| Endpoint | Propósito | Qué verifica | Estado |
| --- | --- | --- | --- |
| `GET /health` | Liveness: el proceso responde | Nada (sin llamadas externas) | `200 {"status": "ok"}` |
| `GET /ready` | Readiness: el servicio puede atender tráfico | `SELECT 1` y que exista la extensión `vector` | `200`, o `503` indicando la verificación que falló |

Los endpoints de salud no se versionan (`/health`, no `/api/v1/health`) y no se registran en los logs de peticiones a nivel `INFO`.

# 32. Unidad de trabajo y transacciones

- Una `AsyncSession` por petición, creada por una dependencia de FastAPI y cerrada al terminar la petición.
- El **servicio** define el límite de la transacción: hace commit cuando el caso de uso termina bien y rollback ante cualquier excepción.
- Los **repositorios** nunca hacen commit: solo `add`, `flush` y consultas.
- El usuario de auditoría (§29) se fija al inicio de cada transacción que escribe.

# 33. Imagen Docker

- Construcción multi-etapa (multi-stage build) sobre `python:3.12-slim-bookworm`, la misma base Debian que la imagen de la base de datos.
- Dependencias instaladas con `uv sync --frozen --no-dev` a partir de `uv.lock`.
- El proceso corre con un usuario **no root**.
- `TZ=America/Bogota`, con `tzdata` instalado.
- `HEALTHCHECK` contra `/health`.
- Sin secretos en la imagen: la configuración llega solo por variables de entorno.
- `.dockerignore` excluye pruebas, cachés, `.env` y archivos de control de versiones.

# 34. Integración con la capa de IA

El brief aísla la IA en su propia capa (`ai/`: generación, RAG, motor de ruta y calificador).

- La capa de aplicación declara **puertos** (Protocols), por ejemplo un generador de preguntas o un proveedor de embeddings. El paquete `ai/` aporta los adaptadores.
- La API nunca llama directamente a un SDK de LLM desde controladores, servicios o repositorios.
- Cada llamada al LLM se registra en `llm_call_logs` (tarea, modelo, versión del prompt, tokens, costo, latencia y estado), como exigen las métricas del brief.
- El contenido generado se guarda en caché por tema y no se regenera por estudiante (brief: decisiones técnicas).

# 35. Seguridad base

**Estado: fuera del alcance de la primera entrega.** El estándar deja definido el objetivo, y el detalle de la decisión pendiente está en D-03 de `proyecto/decisiones-pendientes.md`.

**Objetivo (pendiente):**

- **Identidad delegada** a un proveedor OpenID Connect (Keycloak). La aplicación **no almacena contraseñas** y la tabla `users` no tiene `password_hash`; guarda solo `identity_provider` e `identity_subject`.
- **Seguridad de la API con bearer tokens:** cada petición protegida envía `Authorization: Bearer <access_token>`. La API valida la firma con las llaves públicas del proveedor (JWKS) y verifica `iss`, `aud` y `exp`. Responde `401` si el token falta o es inválido, y `403` si el rol no basta.
- **Autorización por roles** (`admin`, `teacher`, `student`) con una dependencia `require_role(...)` por endpoint, apoyada en `user_roles`.
- **Si se llegara a guardar contraseñas** (no es el plan): hash `argon2id` con sal. Nunca cifrado reversible como AES.
- **Estructura preparada:** `core/security.py` aloja la validación del token y `get_current_user`. En esta entrega no se usa.
- CORS restringido a los orígenes conocidos del frontend.

**Mientras tanto:** la API no autentica. Es solo para ambientes locales y de piloto, y no debe exponerse a internet. La cabecera `X-User-Id` sirve únicamente para auditoría, nunca para autorización.
