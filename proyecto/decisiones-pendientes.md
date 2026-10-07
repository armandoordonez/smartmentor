# Decisiones pendientes

Decisiones técnicas abiertas que afectan el diseño. Cuando una se toma, se registra como ADR en [`docs/adr/`](../docs/adr/) y aquí se marca como cerrada, con el enlace al ADR.

| ID | Decisión | Estado | Valor provisional | Bloquea |
| --- | --- | --- | --- | --- |
| [D-01](#d-01-modelo-de-embeddings-y-dimensión-del-vector) | Modelo de embeddings y dimensión del vector | Abierta | `vector(1024)` | Índices HNSW definitivos y fase de RAG |
| [D-02](#d-02-proveedor-de-llm) | Proveedor de LLM | Abierta | — | Capa `ai/` |
| [D-03](#d-03-autenticación-contraseñas-y-seguridad-de-la-api) | Autenticación, contraseñas y seguridad de la API (Keycloak, bearer tokens) | Abierta, fuera de alcance | Sin autenticación; `X-User-Id` solo para auditoría | Login real (módulo 1) y exposición a internet |
| [D-04](#d-04-almacenamiento-de-fragmentos-rag) | Almacenamiento de fragmentos RAG | Abierta | — | Fase de RAG |
| [D-05](#d-05-usuario-de-base-de-datos-con-mínimo-privilegio) | Usuario de BD con mínimo privilegio para la API | Abierta | Un solo usuario dueño | Despliegue productivo |
| [D-06](#d-06-destino-de-despliegue) | Destino de despliegue | Abierta | — | Paridad de versiones (ADR 0001) |

---

## D-01: modelo de embeddings y dimensión del vector

**Estado:** abierta. **Valor provisional:** `vector(1024)` en `topics.embedding` y `enrollments.profile_embedding` (changeset `v1.0.0`).

### Para qué usa embeddings el brief

| # | Uso | Sección del brief | Qué exige al modelo |
| --- | --- | --- | --- |
| 1 | Perfil semántico: comparar la descripción libre del estudiante con cada tema | Componente de IA, punto 3 | Textos cortos en español; buena similitud semántica |
| 2 | RAG: recuperar fragmentos de libros abiertos y apuntes del docente | Componente de IA, punto 6 | Textos largos, mezcla de español e inglés; contexto amplio |
| 3 | Reordenar videos de YouTube por similitud entre transcripción y tema | Componente de IA, punto 6 | Transcripciones largas y ruidosas; multilingüe |
| 4 | Métrica de costo por estudiante-ruta | Métricas del sistema | Bajo costo por token o costo cero |
| 5 | Continuidad entre cohortes | Gestión del proyecto | Que el modelo siga disponible y los resultados se puedan reproducir |
| 6 | Integración técnica | Arquitectura | Compatible con LlamaIndex y con HNSW de pgvector (máximo 2000 dimensiones en `vector`) |

**Regla clave:** perfil, temas, fragmentos y transcripciones **deben usar el mismo modelo**, porque se comparan entre sí. Cambiar de modelo implica recalcular todos los vectores.

### Opciones

| Opción | Dimensión | Tipo | A favor | En contra |
| --- | --- | --- | --- | --- |
| OpenAI `text-embedding-3-small` | 1536 nativa; reducible a 1024 con el parámetro `dimensions` | API | Muy barato, buen desempeño multilingüe, fácil de integrar | Dependencia de un proveedor; los datos salen a un tercero |
| OpenAI `text-embedding-3-large` | 3072 nativa; hay que reducirla para usar HNSW | API | Mayor calidad de la familia OpenAI | Bastante más caro; sin reducir, excede el límite de HNSW |
| Voyage `voyage-3.5` / `voyage-multilingual-2` | 1024 por defecto (3.5 admite 256 a 2048) | API | Es el proveedor de embeddings que recomienda Anthropic si el LLM es Claude; buena calidad en recuperación | Otro proveedor y otra clave de API |
| Cohere `embed-multilingual-v3.0` | 1024 | API | Fuerte en multilingüe y búsqueda | Otro proveedor y otra clave de API |
| BAAI `bge-m3` | 1024 | Open source (MIT) | Costo cero, corre local, más de 100 idiomas, contexto de 8192 tokens, reproducible entre cohortes | Requiere CPU/GPU o un servicio propio; en CPU es más lento |
| `multilingual-e5-large` / `-base` | 1024 / 768 | Open source | Gratis; la versión base es liviana | Contexto de 512 tokens; calidad menor que bge-m3 |

> Los precios de las APIs cambian. Hay que consultar las tarifas vigentes de cada proveedor antes de decidir y registrarlas en el ADR.

### Recomendación

**Dimensión: 1024.**
- Es el denominador común: bge-m3, Voyage, Cohere y e5-large la producen de forma nativa, y OpenAI la alcanza con `dimensions=1024`.
- Si después se cambia de proveedor, solo hay que recalcular los vectores; el esquema no cambia.
- Ocupa un tercio menos que 1536 y queda dentro del límite de HNSW.

**Modelo sugerido: `bge-m3`.**
- Costo cero, lo que favorece la métrica de costo del brief.
- Reproducible por cualquier cohorte, porque no depende de que una API siga existiendo ni de una clave de pago.
- Multilingüe con contexto amplio, lo que sirve para RAG y transcripciones.

**Alternativa:** si se elige Claude como LLM (D-02) y se prefiere no operar un modelo propio, `voyage-3.5` en 1024 dimensiones.

### Cómo cerrar la decisión

1. Construir un conjunto de 20 a 30 pares tema↔fragmento con el syllabus real del piloto, anotados por el docente.
2. Medir recall@5 y nDCG@5 con 2 o 3 candidatos (por ejemplo bge-m3, voyage-3.5 y text-embedding-3-small en 1024), además del costo y la latencia.
3. Registrar el resultado en un ADR. Si la dimensión final no es 1024, crear un changeset que altere las columnas y recree los índices HNSW.

---

## D-02: proveedor de LLM

El brief admite Claude, GPT u open source. Afecta las salidas estructuradas (JSON), el costo por estudiante-ruta y la recomendación de D-01. Debe decidirse antes de construir `ai/`.

## D-03: autenticación, contraseñas y seguridad de la API

**Estado:** abierta, **fuera del alcance de esta entrega**. Aplica a una entrega posterior; hoy solo queda el modelo preparado.

### Qué hay en esta entrega

- La tabla `users` **no guarda contraseña**. No existe `password_hash` ni columna equivalente.
- La tabla `users` tiene dos columnas opcionales para enlazar a un proveedor de identidad: `identity_provider` (por ejemplo `keycloak`) e `identity_subject` (el `sub` del token). Un índice único evita enlazar dos usuarios a la misma identidad.
- La API **no autentica**: no valida tokens ni protege rutas. Solo está pensada para ambientes locales y de piloto.
- Para la auditoría, el usuario que actúa llega por la cabecera `X-User-Id` (valor por defecto `system`). Esta cabecera **no es autenticación ni autorización**, y se elimina cuando se implemente la seguridad.

### Criterio sobre contraseñas

| Opción | Evaluación |
| --- | --- |
| Cifrar con AES | **No recomendada.** El cifrado es reversible: quien obtenga la clave recupera todas las contraseñas. Una contraseña nunca debe poder recuperarse. |
| Hash lento con sal (`argon2id`, o `bcrypt`/`scrypt`) | Es lo correcto si la aplicación llegara a guardar contraseñas. `argon2id` es la recomendación actual de OWASP. Se almacena en `users.password_hash`. |
| **No guardar contraseñas y delegar en un proveedor de identidad (Keycloak)** | **Recomendada.** La aplicación no maneja credenciales, y Keycloak ofrece recuperación de contraseña, MFA, bloqueo por intentos y inicio de sesión único. |

**Decisión de diseño:** no se crea `password_hash`. Si se descartara el proveedor de identidad, se agregaría con un changeset nuevo (`argon2id`, nunca AES).

AES sí es apropiado para datos que la aplicación debe poder leer de nuevo, como tokens de terceros o claves de API guardadas en la base. No es el caso de las contraseñas.

### Plan objetivo con Keycloak (pendiente)

1. **Proveedor:** Keycloak (OpenID Connect) como servicio adicional en `docker-compose.yml`, con su propia base o esquema, separado de `smartmentor`.
2. **Flujo:** el frontend inicia sesión en Keycloak y obtiene un *access token* (JWT). Envía `Authorization: Bearer <token>` a la API.
3. **Validación en la API:**
   - verificar la firma con las llaves públicas del proveedor (JWKS);
   - verificar `iss`, `aud` y `exp`;
   - rechazar con `401` el token ausente o inválido y con `403` el rol insuficiente.
4. **Vinculación de usuarios:** `users.identity_subject` se llena con el `sub` del token en el primer acceso. El correo se toma de la reclamación `email`.
5. **Roles:**
   - los roles `admin`, `teacher` y `student` viven en Keycloak y se mapean a `roles.code`;
   - `user_roles` sigue siendo la fuente de autorización dentro de la aplicación;
   - hay que decidir si se sincronizan al iniciar sesión o si solo manda Keycloak.
6. **Auditoría:** `app_user_id` pasa a salir del usuario autenticado, y se elimina `X-User-Id`.
7. **Rutas públicas:** `/health`, `/ready` y la documentación OpenAPI según el ambiente.
8. **Seguridad adicional:** CORS restringido, limitación de peticiones y registro de accesos denegados.

### Lo que habrá que implementar

- **Código:** `core/security.py` con la validación del token y la dependencia `get_current_user`, más una dependencia `require_role(...)` por endpoint.
- **Configuración:** `OIDC_ISSUER_URL`, `OIDC_AUDIENCE` y `OIDC_JWKS_URL` en `.env.example`.
- **Servicio Keycloak:** contenedor, realm `smartmentor` con los tres roles y un cliente para el frontend y otro para la API.
- **Pruebas:** tokens firmados de prueba, y casos 401 y 403.
- **ADR nuevo** que cierre la decisión.

Hasta que esto se implemente, la API **no debe exponerse a internet**.

## D-04: almacenamiento de fragmentos RAG

LlamaIndex (`PGVectorStore`) puede crear sus propias tablas, pero el ADR 0002 exige que todo el esquema lo gestione Liquibase. La propuesta es una tabla `document_chunks`, con su `_audit`, creada por un changeset, y configurar LlamaIndex para usarla sin crear tablas. Depende de D-01.

## D-05: usuario de base de datos con mínimo privilegio

Hoy Liquibase y la API usan el mismo usuario dueño (`POSTGRES_USER`). Para producción se recomienda separar:
- `smartmentor_owner`, que usa Liquibase y puede cambiar el esquema;
- `smartmentor_app`, que usa la API y solo lee y escribe datos.

Se crearían en el bootstrap (`database/bootstrap/`).

## D-06: destino de despliegue

El brief sugiere Supabase, Render, Railway o Hugging Face Spaces. Hay que verificar que el destino ofrezca PostgreSQL 17 con pgvector 0.8.x (ADR 0001), y definir cómo correr Liquibase allí: imagen en CI/CD o un job del proveedor.
