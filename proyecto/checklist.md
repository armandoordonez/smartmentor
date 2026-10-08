# Checklist de avance del proyecto

Lista de verificación del [brief](brief.md): qué está hecho, qué falta y quién responde de cada cosa. Se marca a mano (`[x]`) y el resumen de avance se recalcula con un script. Complementa a [`HANDOFF.md`](../HANDOFF.md) (estado técnico y deuda) y a [`decisiones-pendientes.md`](decisiones-pendientes.md).

**Última actualización:** 2026-10-07 · **Cohorte:** 1

## Cómo usar este checklist

- Cada tarea es una línea con casilla: `- [ ] Tarea — **Resp.:** nombre — _nota_`. Al terminarla se cambia a `- [x]`.
- **Resp.** es la persona que responde de la tarea. Mientras no se asigne queda `_por asignar_`, con entre paréntesis el rol del brief que debería tomarla.
- Para agregar tareas, se añade una línea en la sección que corresponda. No hace falta tocar números: el resumen se recalcula.
- Después de marcar tareas, actualiza el resumen y confirma el cambio:

```bash
proyecto/scripts/avance.sh                     # muestra el avance por sección
proyecto/scripts/avance.sh --actualizar        # reescribe la tabla de «Avance de la fase» en este archivo
proyecto/scripts/avance.sh pendientes nombre   # lista las tareas abiertas de una persona (o «por asignar»)
```

## Equipo y responsables

Roles definidos en el brief. Completa el nombre de cada persona y úsalo en **Resp.** de las tareas.

| Rol del brief | Responsabilidad | Persona |
| --- | --- | --- |
| Director o tutor (product owner) | Prioriza el backlog, aprueba hitos, garantiza la continuidad entre cohortes | _por asignar_ |
| Líder del grupo (scrum master) | Planea sprints, mantiene el tablero, actualiza el documento vivo | _por asignar_ |
| Responsable de IA y datos | Prompts, RAG, motor de ruta, notebook de métricas | _por asignar_ |
| Responsable de producto | Prototipo, interfaz, API y despliegue | _por asignar_ |
| Responsable de evaluación | Instrumentos, piloto, anotación de expertos, ética | _por asignar_ |
| Autor del trabajo técnico de la cohorte 1 (base de datos, API, identidad) | Lo hecho hasta hoy en infraestructura y backend | eduar.troyano |

En grupos de 2 personas los roles se combinan.

## Avance de la fase

<!-- AVANCE:INICIO -->

| Sección | Hechas | Total | Avance |
| --- | ---: | ---: | ---: |
| A. Gestión del proyecto y repositorio | 6 | 15 | 40 % |
| B. Infraestructura, datos e identidad | 7 | 15 | 47 % |
| C. Fase 0: prototipado y validación del flujo | 0 | 6 | 0 % |
| D. Módulos del brief (backend) | 12 | 26 | 46 % |
| E. Componente de IA y ciencia de datos | 1 | 9 | 11 % |
| F. Interfaz de usuario (frontend) | 0 | 8 | 0 % |
| G. Evaluación, piloto y entregables | 0 | 11 | 0 % |
| H. Decisiones técnicas pendientes | 1 | 6 | 17 % |
| **Total** | **27** | **96** | **28 %** |

_Calculado el 2026-10-07 con `proyecto/scripts/avance.sh --actualizar`._

<!-- AVANCE:FIN -->

### Dónde estamos frente al cronograma del brief

| Fase del brief | Estado | Detalle |
| --- | --- | --- |
| **Fase 0: prototipado** | No iniciada | Sin wireframes, prototipo navegable, prueba de prompts ni prueba de usabilidad. El brief la pide antes de construir pantallas |
| **Fundamentos** | Parcial | Hecho: modelo de datos, repositorio y documentación. Falta: CI, estado del arte, syllabus real y docente validador |
| **Flujo completo** | En curso, solo el backend | Hecho: usuarios y roles, cursos, rutas, evaluaciones, seguridad y endpoints del estudiante. Falta: IA, recursos, interfaz |
| **Piloto** | No iniciada | Requiere el flujo completo, el consentimiento informado y los instrumentos |
| **Cierre** | No iniciada | Métricas, notebook, documento final y traspaso |

**Lectura honesta del avance:** la infraestructura y el backend van adelantados; la IA y la interfaz, que son el aporte académico y lo que el estudiante ve, no han empezado. El hito clave del brief («el flujo corre de punta a punta, con el alcance congelado») no se alcanza solo con el backend: su principal riesgo es la capa de IA y su principal bloqueo, la decisión del proveedor de LLM (D-02).

## A. Gestión del proyecto y repositorio

### Repositorio y documentación

- [x] Estructura de carpetas del brief, con un README en cada una — **Resp.:** eduar.troyano
- [x] Estrategia de ramas y Conventional Commits documentada — **Resp.:** eduar.troyano — [`GIT_VERSIONING_STRATEGY.md`](../GIT_VERSIONING_STRATEGY.md)
- [x] Decisiones de arquitectura registradas (ADR 0001 a 0005) — **Resp.:** eduar.troyano — [`docs/adr/`](../docs/adr/README.md)
- [x] `HANDOFF.md` y `CHANGELOG.md` iniciales — **Resp.:** eduar.troyano
- [x] Decisiones pendientes con opciones y recomendación (D-01 a D-06) — **Resp.:** eduar.troyano
- [x] Estándar de microservicios FastAPI adoptado y traducido (rev. 2) — **Resp.:** eduar.troyano — [`api/microservice-development-standard.md`](../api/microservice-development-standard.md)

### Proceso del equipo

- [ ] Repositorio en una organización de GitHub de la maestría, no en una cuenta personal — **Resp.:** _por asignar_ (Director o tutor)
- [ ] Rama `main` protegida: sin push directo y con revisión de otro integrante — **Resp.:** _por asignar_ (Líder del grupo)
- [ ] CI en GitHub Actions: Ruff, mypy, pytest y validación de los changelogs en cada pull request — **Resp.:** _por asignar_ (Líder del grupo)
- [ ] Tablero de GitHub Projects con cada tarea como issue enlazado a su pull request — **Resp.:** _por asignar_ (Líder del grupo)
- [ ] Reunión semanal de 30 minutos con el director y demo al cierre de cada fase — **Resp.:** _por asignar_ (Líder del grupo)
- [ ] Documento final iniciado en paralelo, en el formato de la maestría — **Resp.:** _por asignar_ (Líder del grupo)

### Fundamentos académicos

- [ ] Estado del arte ampliado a partir de las referencias del brief — **Resp.:** _por asignar_ (Responsable de IA y datos)
- [ ] Syllabus real (1 o 2) y docente validador identificados — **Resp.:** _por asignar_ (Director o tutor)
- [ ] Consentimiento informado y anonimización definidos (Ley 1581 de 2012) — **Resp.:** _por asignar_ (Responsable de evaluación)

## B. Infraestructura, datos e identidad

### Hecho

- [x] PostgreSQL 17 + pgvector en Docker, con volumen dentro del proyecto y reinicio automático — **Resp.:** eduar.troyano
- [x] Liquibase v1.0.0: 14 tablas con auditoría por trigger, borrado lógico, índices vectoriales provisionales y roles; rollback probado — **Resp.:** eduar.troyano
- [x] Liquibase v1.0.1: usuario Administrador (`admin.smartmentor@yopmail.com`) — **Resp.:** eduar.troyano
- [x] Bootstrap de las bases, `backup.sh` y `restore.sh` (aplicación y Keycloak), probados — **Resp.:** eduar.troyano
- [x] Keycloak 26.8.0 sobre el mismo PostgreSQL, con el realm versionado y arranque automático en un PC nuevo — **Resp.:** eduar.troyano
- [x] Cliente de desarrollo para pedir tokens desde Swagger, la terminal y Postman — **Resp.:** eduar.troyano
- [x] Entorno reproducible con `docker compose up -d --build` — **Resp.:** eduar.troyano

### Pendiente: lo que debe hacer quien administra el proyecto

- [ ] Definir la contraseña del usuario administrador en Keycloak y ejecutar `keycloak/scripts/export-realm.sh` — **Resp.:** eduar.troyano
- [ ] Probar el login de Swagger y la colección de Postman en las herramientas reales — **Resp.:** eduar.troyano
- [ ] Regenerar el client secret de `smartmentor-api` (se compartió en un chat) y exportar el realm — **Resp.:** eduar.troyano
- [ ] Borrar la URI mal escrita `http:localhost:8081` del cliente `smartmentor-frontend` — **Resp.:** eduar.troyano
- [ ] Hacer `push` de la rama con el remoto en privado — **Resp.:** eduar.troyano

### Pendiente: antes de exponer algo fuera de la máquina local

- [ ] HTTPS y nombre de host fijo en Keycloak, CORS restringido al frontend y limitación de peticiones — **Resp.:** _por asignar_ (Responsable de producto)
- [ ] Eliminar el cliente `smartmentor-dev-tools` y dejar `OIDC_DOCS_CLIENT_ID` vacío — **Resp.:** _por asignar_ (Responsable de producto)
- [ ] Dejar de versionar usuarios y secretos del realm y limpiar el historial de git — **Resp.:** _por asignar_ (Responsable de producto)

## C. Fase 0: prototipado y validación del flujo

Criterio de salida del brief: flujo y pantallas aprobados, y esquemas JSON de cada salida de IA definidos y versionados.

- [ ] Mapa del flujo y casos de uso aprobado por el director (el brief ya trae el diagrama del flujo del estudiante) — **Resp.:** _por asignar_ (Director o tutor)
- [ ] Wireframes de baja fidelidad de las 7 pantallas: login, catálogo de rutas, perfil, diagnóstico, vista de ruta, tema (video, texto y quiz) y badge — **Resp.:** _por asignar_ (Responsable de producto)
- [ ] Prototipo navegable de alta fidelidad (Figma, o Streamlit con datos de ejemplo) — **Resp.:** _por asignar_ (Responsable de producto)
- [ ] Prueba de prompts «Mago de Oz»: syllabus estructurado, diagnóstico y un tema generados a mano con el LLM — **Resp.:** _por asignar_ (Responsable de IA y datos)
- [ ] Esquemas JSON de cada salida de IA, definidos y versionados en `prompts/` — **Resp.:** _por asignar_ (Responsable de IA y datos)
- [ ] Prueba de usabilidad con 3 a 5 usuarios (pensar en voz alta) y cuestionario SUS — **Resp.:** _por asignar_ (Responsable de evaluación)

## D. Módulos del brief (backend)

### Módulo 1: gestión de usuarios

- [x] Inicio de sesión con Keycloak, validación de tokens en la API y roles admin, docente y estudiante — **Resp.:** eduar.troyano — [ADR 0004](../docs/adr/0004-authentication-keycloak-bearer.md)
- [x] El estudiante se crea solo en su primer acceso; docentes y administradores los crea un administrador desde la API — **Resp.:** eduar.troyano
- [x] Perfil del usuario autenticado (`GET /api/v1/me`) — **Resp.:** eduar.troyano
- [ ] Pantallas de login y perfil — **Resp.:** _por asignar_ (Responsable de producto)

### Módulo 2: cursos y syllabus

- [x] Crear cursos, temas y prerrequisitos (grafo sin ciclos y dentro del mismo curso) — **Resp.:** eduar.troyano
- [x] Objetivo por defecto y umbrales de la ruta según el brief (70 %, 80 %, 80 % y 3 intentos) — **Resp.:** eduar.troyano
- [ ] Carga del syllabus (PDF o texto) — **Resp.:** _por asignar_ (Responsable de producto)
- [ ] Extracción de temas, prerrequisitos y resultados de aprendizaje con LLM — **Resp.:** _por asignar_ (Responsable de IA y datos)
- [ ] Revisión y aprobación de los temas extraídos por el docente — **Resp.:** _por asignar_ (Responsable de producto)

### Módulo 3: rutas

- [x] Inscripción, estado de avance por tema e historial de intentos — **Resp.:** eduar.troyano
- [x] Endpoints del estudiante sobre lo propio (`/api/v1/me/enrollments...`), con verificación de pertenencia — **Resp.:** eduar.troyano — [`api/README.md`](../api/README.md)
- [ ] Dashboard simple de avance para el docente — **Resp.:** _por asignar_ (Responsable de producto)

### Módulo 4: diagnóstico

- [x] Guardar el diagnóstico y recibir las respuestas del estudiante (una sola vez) — **Resp.:** eduar.troyano
- [ ] Generar la prueba diagnóstica desde el syllabus (2 a 3 preguntas por tema, en tres niveles de Bloom) — **Resp.:** _por asignar_ (Responsable de IA y datos)
- [ ] Calcular el nivel por tema — **Resp.:** _por asignar_ (Responsable de IA y datos)

### Módulo 5: motor de ruta y contenido

- [ ] Definir el objetivo de aprendizaje personalizado — **Resp.:** _por asignar_ (Responsable de IA y datos)
- [ ] Seleccionar y ordenar los temas (orden topológico; omitir los dominados con 80 % o más) — **Resp.:** _por asignar_ (Responsable de IA y datos)
- [ ] Recursos de video y texto por tema — **Resp.:** _por asignar_ (Responsable de IA y datos)

### Módulo 6: evaluación y certificación

- [x] Aprobación automática con el umbral de la ruta y máximo de intentos por evaluación — **Resp.:** eduar.troyano
- [x] El badge solo se emite con la evaluación final aprobada — **Resp.:** eduar.troyano
- [ ] Generar los quizzes de tema y la evaluación final — **Resp.:** _por asignar_ (Responsable de IA y datos)
- [ ] Calificar automáticamente las respuestas cortas — **Resp.:** _por asignar_ (Responsable de IA y datos)
- [ ] Emitir el badge como imagen y JSON tipo Open Badges — **Resp.:** _por asignar_ (Responsable de producto)

### Calidad del backend

- [x] 148 pruebas (unitarias e integración) con Ruff y mypy estricto en verde — **Resp.:** eduar.troyano — `api/scripts/dev.sh all`
- [x] Errores RFC 9457, logs JSON con `request_id`, `/health` y `/ready` — **Resp.:** eduar.troyano
- [ ] Medir la cobertura de las pruebas — **Resp.:** _por asignar_ (Responsable de producto)

## E. Componente de IA y ciencia de datos

El corazón académico del proyecto: cada paso es un problema de IA con entrada, salida estructurada (JSON) y una forma de medirlo.

- [x] Registro de cada llamada al LLM (tarea, modelo, tokens, costo, latencia): tabla y endpoints listos — **Resp.:** eduar.troyano — falta que la capa de IA lo use
- [ ] Estructuración del syllabus como grafo de temas, con salida validada por esquema (Pydantic) — **Resp.:** _por asignar_ (Responsable de IA y datos)
- [ ] Prueba diagnóstica y estimación del nivel por tema — **Resp.:** _por asignar_ (Responsable de IA y datos)
- [ ] Perfil semántico del estudiante con embeddings, combinado con el diagnóstico — **Resp.:** _por asignar_ (Responsable de IA y datos)
- [ ] Definición del objetivo de aprendizaje (el de la ruta o uno propuesto por el LLM) — **Resp.:** _por asignar_ (Responsable de IA y datos)
- [ ] Secuenciación de la ruta: algoritmo determinista y explicable sobre el grafo — **Resp.:** _por asignar_ (Responsable de IA y datos)
- [ ] Texto con RAG citando fuentes y videos reordenados por similitud semántica — **Resp.:** _por asignar_ (Responsable de IA y datos)
- [ ] Evaluaciones generadas desde los resultados de aprendizaje y calificación con rúbrica (LLM-as-judge) — **Resp.:** _por asignar_ (Responsable de IA y datos)
- [ ] Prompts versionados como código, y contenido en caché por tema — **Resp.:** _por asignar_ (Responsable de IA y datos)

## F. Interfaz de usuario (frontend)

El brief propone dos caminos: **Streamlit** (recomendado para el MVP) o **Next.js** («válido si el equipo domina React, pero consume tiempo que conviene dedicar a la evaluación»). Ambos usan la misma API y el mismo inicio de sesión con Keycloak.

### Decisión

- [ ] Decidir el frontend: Streamlit o Next.js — **Resp.:** _por asignar_ (Director o tutor, con el Responsable de producto) — comparación a continuación

### Comparación

| Criterio | Streamlit | Next.js |
| --- | --- | --- |
| Lenguaje y equipo | **Python**: el mismo del backend y de la capa de IA; no exige una herramienta nueva | TypeScript y React: exige que alguien domine el frontend y el entorno de Node |
| Tiempo hasta el MVP | **Muy corto**: pantallas con pocas líneas; el brief dice que «se construye en días» | Más largo: componentes, rutas, manejo de estado y estilos |
| Integración con IA y datos | **Directa**: puede importar el código Python y reutilizar lo de los notebooks | Siempre por HTTP a través de la API |
| Inicio de sesión con Keycloak | `st.login()` nativo; con `expose_tokens` el access token queda en el servidor. Hay que verificar la renovación del token y el cierre de sesión | **Integración más madura** con Auth.js o `keycloak-js`: tokens en el servidor, renovación y protección de rutas |
| Control de la interfaz | Limitado a los componentes disponibles; los diseños complejos cuestan | **Total**: diseño propio, accesibilidad y adaptación a móviles |
| Interactividad | Re-ejecuta el script en cada interacción y guarda el estado en `session_state`: cómodo para formularios y quizzes simples, incómodo para flujos muy dinámicos | **Estado de cliente flexible** y navegación fluida |
| Rendimiento y usuarios simultáneos | Un proceso Python atiende las sesiones; debería bastar para el piloto previsto (15 a 30 estudiantes), conviene medirlo | **Pensado para mucho tráfico** (renderizado en servidor, CDN) |
| Pruebas automáticas | Existe `AppTest` para probar la interfaz, más limitado | **Ecosistema maduro** (Jest, Playwright) |
| Despliegue | Un contenedor Python; el brief lista Hugging Face Spaces como opción | Un contenedor Node o una plataforma de alojamiento de frontend |
| Continuidad entre cohortes | **Cualquier integrante que sepa Python** puede mantenerlo | Exige que la siguiente cohorte tenga perfil de frontend |
| Camino a producción | Probable reescritura si el producto crece | **Evolución natural** a un producto real |
| Riesgo para el brief | **Bajo**: deja tiempo para la evaluación, que es lo que se aprueba | Medio: el tiempo extra se resta a la evaluación |

**Recomendación:** Streamlit para el prototipo de la Fase 0, el MVP y el piloto, porque libera tiempo para lo que el brief evalúa y reutiliza el stack de Python. Elegir Next.js si el equipo ya domina React y hay quien lo mantenga, o si se prevé pasar a producción con más usuarios. Como la API y el login no dependen del frontend, cambiar de uno a otro más adelante no obliga a rehacer el backend.

### Pantallas

- [ ] Login y perfil — **Resp.:** _por asignar_ (Responsable de producto)
- [ ] Catálogo de rutas e inscripción — **Resp.:** _por asignar_ (Responsable de producto)
- [ ] Diagnóstico — **Resp.:** _por asignar_ (Responsable de producto)
- [ ] Vista de la ruta personalizada — **Resp.:** _por asignar_ (Responsable de producto)
- [ ] Tema: video, texto y quiz — **Resp.:** _por asignar_ (Responsable de producto)
- [ ] Badge — **Resp.:** _por asignar_ (Responsable de producto)
- [ ] Panel del docente: revisión del syllabus y avance de los estudiantes — **Resp.:** _por asignar_ (Responsable de producto)

## G. Evaluación, piloto y entregables

- [ ] Notebook reproducible con todas las métricas del brief y sus gráficos — **Resp.:** _por asignar_ (Responsable de IA y datos)
- [ ] Anotación de expertos: 50 a 100 preguntas con dos evaluadores y kappa de Cohen — **Resp.:** _por asignar_ (Responsable de evaluación)
- [ ] Piloto con 15 a 30 estudiantes en una ruta de 4 a 6 temas (pre y post-test) — **Resp.:** _por asignar_ (Responsable de evaluación)
- [ ] Grupo de control con ruta fija, si el tiempo lo permite — **Resp.:** _por asignar_ (Responsable de evaluación)
- [ ] Encuesta SUS y de percepción al final del piloto — **Resp.:** _por asignar_ (Responsable de evaluación)
- [ ] Prototipo navegable (Figma) con el informe de usabilidad de la Fase 0 — **Resp.:** _por asignar_ (Responsable de producto)
- [ ] Prototipo desplegado y accesible por URL, con un curso y una ruta completos — **Resp.:** _por asignar_ (Responsable de producto)
- [ ] Dataset generado: syllabus estructurado, preguntas, recursos y anotaciones — **Resp.:** _por asignar_ (Responsable de IA y datos)
- [ ] Documento final: estado del arte, metodología, arquitectura, resultados, limitaciones y trabajo futuro — **Resp.:** _por asignar_ (Líder del grupo)
- [ ] Video demo de 3 a 5 minutos y presentación de la sustentación — **Resp.:** _por asignar_ (Líder del grupo)
- [ ] Paquete de traspaso: versión etiquetada (`v1.0-cohorte1`), `HANDOFF.md` y este brief actualizados — **Resp.:** _por asignar_ (Líder del grupo)

## H. Decisiones técnicas pendientes

Detalle, opciones y recomendación en [`decisiones-pendientes.md`](decisiones-pendientes.md).

- [x] D-03: autenticación, contraseñas y seguridad de la API (Keycloak y bearer tokens) — **Resp.:** eduar.troyano — cerrada, [ADR 0004](../docs/adr/0004-authentication-keycloak-bearer.md)
- [ ] D-02: proveedor de LLM (Claude, GPT u open source). **Bloquea la capa de IA** — **Resp.:** _por asignar_ (Director o tutor, con el Responsable de IA y datos)
- [ ] D-01: modelo de embeddings y dimensión del vector (hoy `vector(1024)` provisional); benchmark con el syllabus real — **Resp.:** _por asignar_ (Responsable de IA y datos)
- [ ] D-04: almacenamiento de los fragmentos RAG (`document_chunks` gestionado por Liquibase) — **Resp.:** _por asignar_ (Responsable de IA y datos)
- [ ] D-05: usuario de base de datos con mínimos privilegios para la API — **Resp.:** _por asignar_ (Responsable de producto)
- [ ] D-06: destino de despliegue (verificar PostgreSQL 17 + pgvector y cómo correr Liquibase) — **Resp.:** _por asignar_ (Responsable de producto)
