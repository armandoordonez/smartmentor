# Diagramas de estados

Actualizados al prototipo v3 (sección 5.1 del [plan](../../PLAN_IMPLEMENTACION_V3.md)). Cada estado lleva el valor de la columna de la base de datos en inglés (el que viaja por la API) y su etiqueta en español entre comillas. Cada diagrama va seguido de una tabla de transiciones con **quién la dispara**: el aprendiz (`learner`), el instructor (`instructor`), el administrador (`admin`), el sistema (la API o un trabajo de IA) o el tiempo.

Los umbrales son los del brief y los define el instructor por ruta: tema ≥ 70 %, final ≥ 80 %, máximo 3 intentos y omitir un tema con diagnóstico ≥ 80 %. Los estados los decide la API (`next_action`); las páginas nunca los deducen.

> **Pendiente (no obligatorio):** exportar estos diagramas a draw.io. [`flujo-bpmn.drawio`](flujo-bpmn.drawio) y sus SVG ([`estados-tema.svg`](estados-tema.svg), [`estados-inscripcion.svg`](estados-inscripcion.svg)) corresponden al prototipo v2 y quedan desactualizados. Cuando se rehagan: `drawio -x -f svg -p <página> -o <archivo>.svg flujo-bpmn.drawio`. Mientras tanto, los diagramas Mermaid de este archivo mandan.

## Curso (`courses.status`)

```mermaid
stateDiagram-v2
    [*] --> draft
    draft --> extracting: carga el syllabus
    extracting --> in_review: la IA devuelve temas válidos
    extracting --> extraction_failed: agota los reintentos o el PDF no tiene texto
    extraction_failed --> draft: sube otro archivo o pega el texto
    in_review --> extracting: vuelve a extraer
    in_review --> generating_content: aprueba los temas
    generating_content --> published: recursos y preguntas revisados
    published --> archived: cierra el curso
    draft --> archived: desactiva el curso
    archived --> [*]

    state "draft - Borrador" as draft
    state "extracting - Extrayendo temas" as extracting
    state "extraction_failed - Error al leer el syllabus" as extraction_failed
    state "in_review - En revisión" as in_review
    state "generating_content - Generando contenido" as generating_content
    state "published - Publicado" as published
    state "archived - Archivado" as archived
```

| Transición | Quién la dispara | Pantalla | Regla |
| --- | --- | --- | --- |
| `[*]` → `draft` | `instructor` o `admin` | D1b | Crea el curso con grupo o periodo |
| `draft` → `extracting` | `instructor` o `admin` | D1b, D1c | PDF o texto, máximo 10 MB; se crea un trabajo de IA |
| `extracting` → `in_review` | sistema | D1c → D2 | El JSON es válido y el grafo no tiene ciclos |
| `extracting` → `extraction_failed` | sistema | D1c, D1d | 3 reintentos por formato inválido, o 0 caracteres de texto |
| `extraction_failed` → `draft` | `instructor` | D1d | «Pegar el texto» o «Subir otro archivo»; los datos del curso se conservan |
| `in_review` → `extracting` | `instructor` | D2c | Se pierden las correcciones; el registro de revisión vuelve a cero |
| `in_review` → `generating_content` | `instructor` | D2, D2d | Aprueba los temas y valida el grafo |
| `generating_content` → `published` | `instructor` | D5 | Recursos y preguntas revisados |
| `published` → `archived`, `draft` → `archived` | `admin` o `instructor` dueño | D1, AD5 | Se desactiva, nunca se elimina |

Un curso aparece en el catálogo del aprendiz (E1) solo cuando está `published`.

## Inscripción (`enrollments.status`)

```mermaid
stateDiagram-v2
    [*] --> enrolled
    enrolled --> profiling: abre el perfil
    profiling --> diagnosing: guarda perfil u hoja de vida
    diagnosing --> objective_pending: termina el diagnóstico
    objective_pending --> in_path: confirma el objetivo
    in_path --> final_ready: todos los temas aprobados u omitidos
    final_ready --> completed: final de 80 % o más
    final_ready --> final_ready: final menor a 80 %, repaso y nuevo intento
    completed --> [*]
    enrolled --> abandoned: abandona
    profiling --> abandoned: abandona
    diagnosing --> abandoned: abandona
    objective_pending --> abandoned: abandona
    in_path --> abandoned: abandona
    final_ready --> abandoned: abandona
    enrolled --> withdrawn: el admin la retira
    profiling --> withdrawn: el admin la retira
    diagnosing --> withdrawn: el admin la retira
    objective_pending --> withdrawn: el admin la retira
    in_path --> withdrawn: el admin la retira
    final_ready --> withdrawn: el admin la retira
    abandoned --> [*]
    withdrawn --> [*]

    state "enrolled - Inscrito" as enrolled
    state "profiling - Perfil" as profiling
    state "diagnosing - Diagnóstico" as diagnosing
    state "objective_pending - Objetivo por confirmar" as objective_pending
    state "in_path - En ruta" as in_path
    state "final_ready - Evaluación final habilitada" as final_ready
    state "completed - Completada, badge emitido" as completed
    state "abandoned - Abandonada" as abandoned
    state "withdrawn - Retirada" as withdrawn
```

| Transición | Quién la dispara | Pantalla | Regla |
| --- | --- | --- | --- |
| `[*]` → `enrolled` | `learner` o `admin` | E1, AD5 | Requiere el consentimiento de datos (CU-17). En el piloto se asigna el brazo (`pilot_arm`) |
| `enrolled` → `profiling` | `learner` | E2 | Perfil, paso 1 de 4; la hoja de vida (E2b) es opcional |
| `profiling` → `diagnosing` | `learner` | E2, E2b | Guarda el perfil o elige «Completar más tarde» |
| `diagnosing` → `objective_pending` | sistema | E3, U1a, E4 | Termina el trabajo de calificación del diagnóstico |
| `objective_pending` → `in_path` | `learner` | E4, E4b | Confirma o edita el objetivo; se calcula la ruta |
| `in_path` → `final_ready` | sistema | E5 | Todos los pasos están en `passed` o `skipped` |
| `final_ready` → `completed` | sistema | E8, U1d, E10 | Final de 80 % o más; emite el badge |
| `final_ready` → `final_ready` | `learner` | E9 | Final menor a 80 %: repaso dirigido y nuevo intento (hasta 3, más los extra) |
| cualquiera → `abandoned` | `learner` | E11 | También lo marca el sistema si el piloto cierra con la ruta sin terminar |
| cualquiera → `withdrawn` | `admin` | AD5 | Se retira, no se elimina, para conservar el historial |

Con la final en intentos agotados (E9c) la inscripción sigue en `final_ready` y el instructor recibe una alerta; puede habilitar un intento extra (CU-26). Salir del piloto no cambia el estado de la inscripción.

## Paso de ruta (`path_steps.status`)

Un paso es un tema para un aprendiz.

```mermaid
stateDiagram-v2
    [*] --> skipped: diagnóstico de 80 % o más y no obligatorio
    [*] --> blocked: tiene prerrequisitos sin completar
    [*] --> pending: sin prerrequisitos pendientes
    blocked --> pending: prerrequisitos completados
    pending --> in_progress: abre el tema
    in_progress --> passed: quiz de 70 % o más
    in_progress --> in_progress: quiz menor a 70 % y quedan intentos
    in_progress --> attempts_exhausted: quiz menor a 70 % en el último intento
    attempts_exhausted --> in_progress: el instructor habilita intentos extra
    blocked --> on_hold: un prerrequisito queda en attempts_exhausted
    pending --> on_hold: un prerrequisito queda en attempts_exhausted
    on_hold --> pending: el prerrequisito se resuelve
    passed --> [*]
    skipped --> [*]

    state "skipped - Omitido" as skipped
    state "blocked - Bloqueado" as blocked
    state "pending - Pendiente" as pending
    state "in_progress - En curso, intento n de 3" as in_progress
    state "passed - Aprobado" as passed
    state "attempts_exhausted - Intentos agotados, tema crítico" as attempts_exhausted
    state "on_hold - En espera, depende de uno agotado" as on_hold
```

| Transición | Quién la dispara | Pantalla | Regla |
| --- | --- | --- | --- |
| `[*]` → `skipped` | sistema | E4, E5 | Dominio ≥ 80 % y `topics.is_mandatory` falso. En la ruta fija del piloto (E5b) nunca se omite |
| `[*]` → `blocked` o `pending` | sistema | E5 | Según el grafo de prerrequisitos |
| `blocked` → `pending` | sistema | E5 | Cuando sus prerrequisitos están `passed` o `skipped` |
| `pending` → `in_progress` | `learner` | E6 | Abrir el tema no consume intentos |
| `in_progress` → `passed` | sistema | E7 | Quiz de 70 % o más (la respuesta corta cuenta con 2 de 3 criterios, configurable) |
| `in_progress` → `in_progress` | `learner` | E7b, U1b | Menos de 70 %: explicación alterna y preguntas nuevas |
| `in_progress` → `attempts_exhausted` | sistema | E7c | Crea una alerta (`alerts`) para el instructor |
| `attempts_exhausted` → `in_progress` | `instructor` | D4c | Intentos extra en `attempt_grants`, reportados aparte de los 3 |
| `blocked` o `pending` → `on_hold` | sistema | E7c | Solo los dependientes del tema agotado; los demás temas siguen disponibles (avance no lineal) |
| `on_hold` → `pending` | sistema | E5 | Cuando el tema agotado se aprueba |

Reglas derivadas:

- **Completado** = `passed` o `skipped`. La barra de avance cuenta ambos.
- La evaluación final queda en espera mientras algún paso esté en `attempts_exhausted` u `on_hold`.
- El intento cuenta en cuanto se envía el quiz. El puntaje que se muestra es el del último intento; el instructor ve todos en D4.

## Intento (`assessment_attempts.status`)

```mermaid
stateDiagram-v2
    [*] --> created
    created --> in_progress: muestra la primera pregunta
    in_progress --> submitted: envía las respuestas
    submitted --> grading: se crea el trabajo de calificación
    grading --> graded: la calificación termina
    grading --> grading_failed: error del LLM o JSON inválido
    grading_failed --> grading: reintento
    graded --> [*]

    state "created - Creado" as created
    state "in_progress - Respondiendo" as in_progress
    state "submitted - Enviado" as submitted
    state "grading - Calificando" as grading
    state "graded - Calificado" as graded
    state "grading_failed - Falló la calificación" as grading_failed
```

| Transición | Quién la dispara | Pantalla | Regla |
| --- | --- | --- | --- |
| `created` → `in_progress` | `learner` | E6b, E3, E8 | Una pregunta por pantalla; las respuestas se guardan con cada paso |
| `in_progress` → `submitted` | `learner` | E6c | Envío idempotente (`Idempotency-Key`) |
| `submitted` → `grading` | sistema | U1c, U1d, U1a | Se crea el `ai_jobs` correspondiente |
| `grading` → `graded` | sistema | E7, E4, E9 | Opción múltiple por clave; respuesta corta por rúbrica |
| `grading` → `grading_failed` | sistema | U1x | La pantalla ofrece reintentar; el avance queda guardado |
| `grading_failed` → `grading` | `learner` o sistema | U1x | Reintento manual o automático |

## Recurso (`resources.review_status`)

```mermaid
stateDiagram-v2
    [*] --> pending_review
    pending_review --> approved: el instructor aprueba
    pending_review --> retired: el instructor retira
    approved --> pending_review: se regenera o se edita
    approved --> retired: el instructor retira
    retired --> pending_review: el instructor restaura
    retired --> [*]

    state "pending_review - Por revisar" as pending_review
    state "approved - Aprobado" as approved
    state "retired - Retirado" as retired
```

| Transición | Quién la dispara | Pantalla | Regla |
| --- | --- | --- | --- |
| `[*]` → `pending_review` | sistema | D5 | La IA genera el recurso con su fidelidad y fuentes |
| `pending_review` → `approved` | `instructor` | D5, D5d | La edición crea una versión nueva «editada por instructor» y recalcula la fidelidad |
| `approved` → `pending_review` | `instructor` o sistema | D5 | «Regenerar» o editar; reemplaza la caché del tema |
| `pending_review` o `approved` → `retired` | `instructor` | D5 | El aprendiz ve el respaldo si el recurso es un video (D5e) |
| `retired` → `pending_review` | `instructor` | D5 | Restaurar |

## Ítem de evaluación (`assessment_items.review_status`)

```mermaid
stateDiagram-v2
    [*] --> auto_rejected: no pasa la validación automática
    [*] --> pending_review: pasa la validación automática
    pending_review --> approved: el instructor aprueba
    pending_review --> retired: el instructor retira
    approved --> retired: el instructor retira
    retired --> pending_review: el instructor restaura
    approved --> pending_review: el instructor edita
    auto_rejected --> [*]

    state "auto_rejected - Rechazado automáticamente" as auto_rejected
    state "pending_review - Por revisar" as pending_review
    state "approved - Aprobado" as approved
    state "retired - Retirado" as retired
```

| Transición | Quién la dispara | Pantalla | Regla |
| --- | --- | --- | --- |
| `[*]` → `auto_rejected` o `pending_review` | sistema | D5 | Validación del esquema: una sola respuesta correcta, Bloom coherente |
| `pending_review` → `approved` | `instructor` | D5 | Solo los ítems `approved` entran a los quizzes |
| `approved` → `retired`, `pending_review` → `retired` | `instructor` | D5 | El ítem sale del banco sin borrarse |
| `retired` → `pending_review` | `instructor` | D5 | Restaurar |
| `approved` → `pending_review` | `instructor` | D5 | Edición del enunciado |

La anotación ciega (D5b, CU-27) no cambia este estado: cada evaluador guarda su rúbrica y veredicto en `item_annotations`, y el acuerdo (κ de Cohen) se calcula cuando ambos terminan.

## Trabajo de IA (`ai_jobs.status`)

```mermaid
stateDiagram-v2
    [*] --> queued
    queued --> running: el trabajador lo toma
    running --> succeeded: respuesta válida
    running --> failed: error o JSON inválido tras los reintentos
    failed --> queued: reintento
    succeeded --> [*]

    state "queued - En cola" as queued
    state "running - En ejecución" as running
    state "succeeded - Terminado" as succeeded
    state "failed - Fallido" as failed
```

| Transición | Quién la dispara | Pantalla | Regla |
| --- | --- | --- | --- |
| `[*]` → `queued` | sistema (API) | U1a–U1d, D1c | Una acción del usuario crea el trabajo y devuelve su `id` |
| `queued` → `running` | sistema | U1x | El cliente sondea `GET /jobs/{id}` con espera progresiva |
| `running` → `succeeded` | sistema | U1x → destino | La pantalla de carga navega al resultado |
| `running` → `failed` | sistema | U1x, D1c, D1d | Los reintentos por formato inválido se muestran («2 de 3») |
| `failed` → `queued` | `learner`, `instructor` o sistema | U1x | Reintento manual; el aprendiz nunca pierde lo respondido |

## Piloto (`pilots.status`)

```mermaid
stateDiagram-v2
    [*] --> draft
    draft --> randomized: sortea los grupos con la semilla
    randomized --> draft: vuelve a sortear antes de iniciar
    randomized --> running: inicia el piloto
    running --> closed: llega la fecha de fin o el admin lo cierra
    closed --> [*]

    state "draft - Borrador" as draft
    state "randomized - Grupos sorteados" as randomized
    state "running - En curso" as running
    state "closed - Cerrado" as closed
```

| Transición | Quién la dispara | Pantalla | Regla |
| --- | --- | --- | --- |
| `[*]` → `draft` | `admin` | AD4 | Ruta, fechas, post-test diferido (opcional) |
| `draft` → `randomized` | `admin` | AD4 | Sorteo con semilla; solo entran los aprendices con consentimiento |
| `randomized` → `draft` | `admin` | AD4 | Solo se puede volver a sortear antes de iniciar |
| `randomized` → `running` | `admin` | AD4, AD4b | Requiere ítems equivalentes verificados; sin ruta fija no se calcula la d de Cohen |
| `running` → `closed` | `admin` o tiempo | AD4 | Fecha de fin; el post-test diferido (E14) ocurre de 2 a 4 semanas después |

Mientras el piloto está `running`, cambiar los umbrales de la ruta (D3b) rompe la comparación y la pantalla lo advierte.

## Autorización (`consents`)

```mermaid
stateDiagram-v2
    [*] --> granted: acepta en el registro o en Mi progreso
    granted --> revoked: sale del piloto o revoca la autorización
    revoked --> granted: vuelve a autorizar
    revoked --> [*]

    state "granted - Concedida" as granted
    state "revoked - Revocada" as revoked
```

Hay dos autorizaciones independientes: `data_processing` (obligatoria) y `pilot` (opcional).

| Transición | Quién la dispara | Pantalla | Regla |
| --- | --- | --- | --- |
| `[*]` → `granted` | `learner` | A3, A3b, E11b | Se registra la fecha y la versión del texto aceptado |
| `granted` → `revoked` (piloto) | `learner` | E11b | Sale del piloto sin perder su ruta ni su badge |
| `granted` → `revoked` (datos) | `learner` | E11b | Además crea una solicitud (`data_subject_requests`) para seudonimizar y purgar `_audit` (C-13) |
| `revoked` → `granted` | `learner` | E11b | Solo la autorización del piloto, y solo mientras el piloto no haya cerrado |

## Primer ingreso (CU-34)

```mermaid
stateDiagram-v2
    [*] --> anonymous
    anonymous --> authenticated: login en Keycloak
    authenticated --> provisioning: primera llamada a la API sin fila en users
    authenticated --> consent_pending: el usuario ya existe sin consentimiento de datos
    authenticated --> active: el usuario ya existe y tiene consentimiento
    provisioning --> consent_pending: la API crea users y el rol learner
    consent_pending --> active: acepta el tratamiento de datos
    consent_pending --> anonymous: cierra sin aceptar
    active --> anonymous: cierra sesión o la sesión expira
    active --> [*]

    state "anonymous - Sin sesión" as anonymous
    state "authenticated - Con token" as authenticated
    state "provisioning - Creando usuario" as provisioning
    state "consent_pending - Falta el consentimiento" as consent_pending
    state "active - Usuario activo" as active
```

| Transición | Quién la dispara | Pantalla | Regla |
| --- | --- | --- | --- |
| `anonymous` → `authenticated` | `learner` | A2 (Keycloak) | El token trae `sub` y el correo verificado |
| `authenticated` → `provisioning` | sistema (API) | — | Primera llamada autenticada; enlaza por `sub` y, si el correo está verificado, por correo |
| `provisioning` → `consent_pending` | sistema (API) | — | Crea `users` y el rol `learner` de forma idempotente y segura ante dos llamadas simultáneas |
| `consent_pending` → `active` | `learner` | A3, A3b | La casilla de tratamiento de datos es obligatoria; la del piloto es opcional |
| `consent_pending` → `anonymous` | `learner` | A3b | Sin aceptar no entra a la plataforma |
| `active` → `anonymous` | `learner` o tiempo | A7 | 30 minutos sin actividad |

## Cambio de perfil (CU-35)

El «rol activo» es solo de presentación; no es un estado de la base de datos. La API autoriza por la unión de los roles y cada ruta pide el suyo.

```mermaid
stateDiagram-v2
    [*] --> learner_view: default_role es learner
    [*] --> instructor_view: default_role es instructor
    [*] --> admin_view: default_role es admin
    learner_view --> instructor_view: elige Instructor en el menú
    learner_view --> admin_view: elige Administrador en el menú
    instructor_view --> learner_view: elige Aprendiz en el menú
    instructor_view --> admin_view: elige Administrador en el menú
    admin_view --> learner_view: elige Aprendiz en el menú
    admin_view --> instructor_view: elige Instructor en el menú

    state "learner_view - Vista de Aprendiz, inicia en E1" as learner_view
    state "instructor_view - Vista de Instructor, inicia en D1" as instructor_view
    state "admin_view - Vista de Administrador, inicia en AD1" as admin_view
```

| Transición | Quién la dispara | Pantalla | Regla |
| --- | --- | --- | --- |
| inicio → vista | sistema | Menú superior | `GET /me` devuelve `roles`, `role_labels` y `default_role` |
| vista → otra vista | cualquier rol | Menú superior | Solo se ofrecen los roles que el usuario tiene; con uno solo no hay opción de cambio |
| abrir una página de otro rol sin tenerlo | cualquier rol | A6 | La API responde 403 |
