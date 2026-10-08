# Decisiones pendientes

Decisiones técnicas abiertas que afectan el diseño. Cuando una se toma, se registra como ADR en [`docs/adr/`](../docs/adr/) y aquí se marca como cerrada, con el enlace al ADR.

| ID | Decisión | Estado | Valor provisional | Bloquea |
| --- | --- | --- | --- | --- |
| [D-01](#d-01-modelo-de-embeddings-y-dimensión-del-vector) | Modelo de embeddings y dimensión del vector | Abierta | `vector(1024)` | Índices HNSW definitivos y fase de RAG |
| [D-02](#d-02-proveedor-de-llm) | Proveedor de LLM | Abierta | — | Capa `ai/` |
| [D-03](#d-03-autenticación-contraseñas-y-seguridad-de-la-api) | Autenticación, contraseñas y seguridad de la API (Keycloak, bearer tokens) | **Cerrada (ADR 0004)**; quedan pendientes menores | Implementada | Interfaz de estudiante y exposición a internet |
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

**Estado:** **cerrada e implementada** en la cohorte 1 ([ADR 0004](../docs/adr/0004-authentication-keycloak-bearer.md)). Quedan los pendientes de la sección "Lo que queda" más abajo.

### Qué se decidió e implementó

- La tabla `users` **no guarda contraseña**: la identidad se delega a Keycloak (OpenID Connect). Si algún día se guardaran contraseñas, sería con `argon2id` y nunca con cifrado reversible como AES.
- La API valida el `Authorization: Bearer <token>` de Keycloak (firma RS256 por JWKS, `iss`, `aud`, `exp`) y responde 401 si falta o no es válido.
- El usuario se enlaza por `sub`, o por correo verificado la primera vez; si no existe se **crea automáticamente como `student`**. Docentes y administradores los crea un administrador desde la API (`/users` y `/user-roles`).
- La autorización usa `user_roles` de la base de datos, no los roles del token. Matriz de permisos en el ADR 0004 y en `api/app/auth/policies.py`.
- La auditoría registra el id del usuario autenticado. La cabecera temporal `X-User-Id` se eliminó.
- **Keycloak 26.8.0** corre en el compose (puerto 8180) con sus datos en una base `keycloak` del PostgreSQL del proyecto y el realm versionado en `keycloak/realm/` ([ADR 0005](../docs/adr/0005-keycloak-postgres-realm-versioned.md)). Guía de configuración, audiencia y traslado: [`keycloak/README.md`](../keycloak/README.md).
- Usuario inicial: `Administrador` (`admin.smartmentor@yopmail.com`, rol `admin`), sembrado por Liquibase `v1.0.1`.

### Criterio sobre contraseñas

| Opción | Evaluación |
| --- | --- |
| Cifrar con AES | **No recomendada.** El cifrado es reversible: quien obtenga la clave recupera todas las contraseñas. |
| Hash lento con sal (`argon2id`, o `bcrypt`/`scrypt`) | Lo correcto si la aplicación llegara a guardar contraseñas. `argon2id` es la recomendación actual de OWASP. |
| **No guardar contraseñas y delegar en Keycloak** | **Elegida.** Keycloak ofrece recuperación de contraseña, MFA, bloqueo por intentos y inicio de sesión único. |

AES sí es apropiado para datos que la aplicación debe poder leer de nuevo, como claves de APIs de terceros guardadas en la base.

### Integración con el frontend (Streamlit o Next.js)

La API no depende del frontend: solo valida el token. El frontend inicia sesión en Keycloak (OpenID Connect, flujo de código con PKCE) y envía `Authorization: Bearer <access_token>`.

| Frontend | Integración con Keycloak | Observaciones |
| --- | --- | --- |
| Streamlit | Inicio de sesión nativo `st.login()`. Con `expose_tokens` el *access token* queda disponible en el servidor (`st.user.tokens`) para llamar a la API | Las llamadas salen del servidor de Streamlit, así que el token no pasa por el navegador. Antes tenía el límite de no exponer el access token. Hay que verificar en la versión que se instale la renovación del token y el cierre de sesión en Keycloak. |
| Next.js | Auth.js (proveedor Keycloak) o `keycloak-js` | Integración más madura: tokens en el servidor, renovación y protección de rutas. Cuesta más tiempo de desarrollo, que el brief prefiere dedicar a la evaluación. |

Recomendación: Streamlit para el MVP del brief. Si se elige Next.js, nada de lo diseñado cambia. **Decidida: Streamlit** ([ADR 0006](../docs/adr/0006-frontend-streamlit.md)); arquitectura en [`app/README.md`](../app/README.md).

### Lo que queda

- **Configurar Keycloak** (lo hace quien administra el proyecto, pasos en `keycloak/README.md`): mapper de audiencia `smartmentor-api` en el cliente del frontend, URIs de redirección correctas y `Email verified` en el usuario administrador.
- **Endpoints de estudiante con verificación de pertenencia** (inscribirse, responder quizzes, ver su ruta), en la fase de la interfaz. Hoy el rol `student` solo consulta el catálogo y su perfil.
- **Decidir si el registro es abierto.** Hoy cualquiera con correo verificado en Keycloak se vuelve estudiante. Para un piloto cerrado se restringe el registro en Keycloak o se cambia la regla a "rechazar usuarios desconocidos".
- **Endurecimiento:** limitación de peticiones, vida corta de los tokens, CORS restringido al frontend y HTTPS en Keycloak para producción.
- **Cliente `smartmentor-api`:** la API solo valida tokens y **no usa su `client secret`**. Solo haría falta para introspección de tokens.

## D-04: almacenamiento de fragmentos RAG

LlamaIndex (`PGVectorStore`) puede crear sus propias tablas, pero el ADR 0002 exige que todo el esquema lo gestione Liquibase. La propuesta es una tabla `document_chunks`, con su `_audit`, creada por un changeset, y configurar LlamaIndex para usarla sin crear tablas. Depende de D-01.

## D-05: usuario de base de datos con mínimo privilegio

Hoy Liquibase y la API usan el mismo usuario dueño (`POSTGRES_USER`). Para producción se recomienda separar:
- `smartmentor_owner`, que usa Liquibase y puede cambiar el esquema;
- `smartmentor_app`, que usa la API y solo lee y escribe datos.

Se crearían en el bootstrap (`database/bootstrap/`).

## D-06: destino de despliegue

El brief sugiere Supabase, Render, Railway o Hugging Face Spaces. Hay que verificar que el destino ofrezca PostgreSQL 17 con pgvector 0.8.x (ADR 0001), y definir cómo correr Liquibase allí: imagen en CI/CD o un job del proveedor.
