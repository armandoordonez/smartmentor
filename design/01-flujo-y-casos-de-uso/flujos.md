# Mapa de flujo por rol

Un diagrama por rol, con el código de la pantalla de Figma v3 en cada nodo. Los nodos con borde punteado son estados o pantallas que el prototipo no dibuja y que la app debe resolver (p. ej., el estado de error de un trabajo de IA). El inventario de pantallas está en [`../03-prototipo-alta-fidelidad/README.md`](../03-prototipo-alta-fidelidad/README.md), los casos de uso en [`casos-de-uso.md`](casos-de-uso.md) y los estados en [`estados.md`](estados.md). GitHub muestra los diagramas directamente; para editarlos se puede pegar el bloque en [mermaid.live](https://mermaid.live).

Los botones «(Demo del prototipo)» y los avances automáticos de 2 segundos de Figma **no son parte del flujo**: en la app real los estados salen de la API.

## Entrada y sesión (todos los roles)

Las pantallas de login, registro y recuperación (A2, A4, A5) son de Keycloak. El consentimiento (A3, A3b) lo pide la app después del primer login (CU-34, DEF-13).

```mermaid
flowchart TD
    A1["A1 · Selector de rol<br/>solo en modo demostración"] --> A2["A2 · Login aprendiz"]
    A1 --> A4["A4 · Login instructor"]
    A2 --> V{"¿Credenciales<br/>válidas?"}
    A4 --> V
    A2 -- olvidó la contraseña --> A5["A5 · Recuperar contraseña<br/>enlace válido 30 minutos"] --> A2
    V -- no --> ERR["Mensaje de error<br/>en la misma pantalla"] --> A2
    V -- sí --> R{"¿Rol?"}
    R -- instructor o admin --> MFA["Verificación<br/>en dos pasos"]
    MFA --> R2{"¿Rol activo?"}
    R2 -- instructor --> D1["D1 · Mis cursos"]
    R2 -- admin --> AD1["AD1 · Usuarios y roles"]
    R -- aprendiz --> PRO["Primer ingreso<br/>la API crea users y el rol learner"]
    PRO --> C{"¿Ya aceptó el<br/>tratamiento de datos?"}
    C -- no --> A3["A3 · Registro<br/>dos casillas"]
    A3 --> A3b["A3b · Consentimiento informado"]
    A3b -- "Más sobre tus derechos" --> A3c["A3c · Tus datos y tus derechos"] --> A3b
    A3b -- "acepta o rechaza el piloto" --> E1
    A3b -- "no acepta los datos" --> A2
    C -- sí --> E1["E1 · Catálogo"]
    X["Cualquier pantalla"] -- "30 minutos sin actividad" --> A7["A7 · Sesión expirada"] --> A2
    X -- "rol sin permiso" --> A6["A6 · 403 Sin permiso"] --> H["Volver a mi inicio"]
    X -- "Cambiar de perfil" --> MENU["Menú del avatar<br/>roles del usuario"]:::nuevo --> R2

    classDef nuevo stroke-dasharray: 5 5
```

## Aprendiz

Incluye la hoja de vida (E2b), los consentimientos, las pantallas de carga (U1a–U1d), el avance no lineal (E7c), los intentos agotados de la final (E9c), la encuesta final (E13a, E13b) y la prueba de retención (E14).

```mermaid
flowchart TD
    E1["E1 · Catálogo<br/>6 rutas en 2 grupos"] --> I{"¿Ya inscrito?"}
    I -- no --> INS["Inscribirse"] --> E2["E2 · Perfil<br/>paso 1 de 4"]
    I -- sí --> E5
    E2 --> HV{"¿Completa la<br/>hoja de vida?"}
    HV -- sí --> E2b["E2b · Hoja de vida<br/>estudios, cargo, herramientas, idioma"]
    HV -- "más tarde" --> E3
    E2b --> E3["E3 · Diagnóstico<br/>15 preguntas, una por pantalla"]
    E3 --> U1a["U1a · Calculando tu nivel"]
    U1a -- "error del trabajo de IA" --> ERRA["Reintentar o volver a la ruta<br/>el avance está guardado"]:::nuevo --> U1a
    U1a --> E4["E4 · Resultado y objetivo<br/>Dominado, Por reforzar, Por aprender, Obligatorio"]
    E4 --> OBJ{"¿Acepta el<br/>objetivo?"}
    OBJ -- edita --> E4b["E4b · Editar objetivo<br/>Bloom + contenido + criterio"] --> E4
    OBJ -- sí --> E5["E5 · Vista de ruta<br/>motivo de cada paso"]
    E5 -. "grupo de ruta fija del piloto" .-> E5b["E5b · Ruta fija<br/>sin omitir temas"]
    E5 --> E6["E6 · Tema<br/>video + texto con citas"]
    E6 -. "califica el video" .-> FB["Calificación del video<br/>¿Te sirvió?, etiquetas, comentario"]
    E6 --> E6b["E6b · Quiz del tema<br/>una pregunta por pantalla"]
    E6b --> E6c["E6c · Respuesta corta<br/>rúbrica de 3 criterios"]
    E6c --> U1c["U1c · Calificando"]
    U1c -- "error de calificación" --> ERRC["Reintentar la calificación"]:::nuevo --> U1c
    U1c --> E7["E7 · Resultado del quiz<br/>detalle por criterio"]
    E7 -. "Pedir revisión del instructor" .-> REV["Solicitud de revisión humana"]
    E7 --> Q{"¿70 % o más?"}
    Q -- sí --> E5
    Q -- no --> INT{"¿Quedan<br/>intentos?"}
    INT -- sí --> E7b["E7b · Quiz no aprobado<br/>explicación alterna"]
    E7b --> U1b["U1b · Preparando reintento"]
    U1b -- "error al generar preguntas" --> ERRB["Reintentar o volver a la ruta"]:::nuevo --> U1b
    U1b --> E6b
    INT -- no --> E7c["E7c · Intentos agotados<br/>tema crítico, alerta al instructor"]
    E7c -- "sigue con temas independientes" --> E5
    E5 -- "todos los temas aprobados u omitidos" --> E8["E8 · Evaluación final<br/>10 preguntas, intento 1 de 3"]
    E8 --> U1d["U1d · Calificando la final"]
    U1d --> F{"¿80 % o más?"}
    F -- no --> E9["E9 · Repaso dirigido<br/>temas débiles"]
    E9 --> E8
    E9 -- "3 intentos usados" --> E9c["E9c · Final con intentos agotados"]
    F -- sí --> E10["E10 · Badge"]
    E10 --> E13a["E13a · Encuesta final<br/>Likert"] --> E13b["E13b · SUS de 10 ítems"]
    E10 --> E12["E12 · Logros"]
    E5 -. "menú" .-> E11["E11 · Mi progreso<br/>KPI, metas y racha"]
    E11 -. "Gestionar mis autorizaciones" .-> E11b["E11b · Salir del piloto<br/>o revocar y borrar datos"]
    E11 -. "3 semanas después" .-> E14["E14 · Prueba de retención"]
    E5 -. "menú" .-> E15["E15 · Mi perfil<br/>la ruta se recalcula"]

    classDef nuevo stroke-dasharray: 5 5
```

Personalización: los temas con dominio de 80 % o más en el diagnóstico aparecen en E5 como «Omitido» y cuentan como completados, salvo los obligatorios. En el grupo de ruta fija (E5b) ningún tema se omite.

### Casos de error de las pantallas de carga U1x

Las pantallas U1a, U1b, U1c y U1d son **estados de carga** con tres pasos («Listo», «En curso», «Pendiente»), un tiempo estimado («menos de 20 segundos») y el mensaje «Si tarda más: tu avance está guardado; puedes volver a tu ruta». Figma solo dibuja el camino feliz; la app resuelve estos casos desde el estado del trabajo (`ai_jobs.status`, sondeado con espera progresiva):

| Pantalla | Qué espera | Caso de error | Qué ve el aprendiz | Qué no se pierde |
| --- | --- | --- | --- | --- |
| U1a · Calculando tu nivel | Calificar el diagnóstico y proponer el objetivo | El trabajo falla o supera el tiempo | «No pudimos calcular tu nivel. Reintentar» y «Volver a mi ruta» | Las respuestas del diagnóstico (intento `submitted`) |
| U1b · Preparando reintento | Generar 5 preguntas nuevas y verificar una sola respuesta correcta | Falla la generación o la verificación | «No pudimos preparar las preguntas nuevas. Reintentar»; no se consume el intento hasta que haya preguntas | El intento anterior y su explicación alterna |
| U1c · Calificando | Opción múltiple y rúbrica de 3 criterios de la respuesta corta | `grading_failed` (JSON inválido o error del LLM) | «No pudimos calificar tu respuesta corta. Reintentar»; la opción múltiple ya calificada se conserva | Las respuestas enviadas |
| U1d · Calificando la final | Igual que U1c para la evaluación final | `grading_failed` | Igual que U1c | Las respuestas de la final |
| Todas | — | Más de 20 segundos | El aviso «Si tarda más» ya existente; la página sigue sondeando | El avance |
| Todas | — | El token vence mientras espera | A7 «Tu sesión expiró»; al volver a entrar retoma el trabajo | El trabajo en curso |

Regla común: el error de un trabajo de IA nunca avanza ni descarta lo respondido; ofrece **reintentar** (`failed` → `queued`) o **volver a la ruta**. La app no inventa un resultado.

## Instructor

Incluye la creación del curso (D1b), la extracción (D1c) y su error (D1d), el grafo de temas (D2d), los intentos extra (D4b, D4c) y las pantallas de evaluación (D5b–D5f). Un instructor asignado como evaluador entra a D5b y D5c de cursos que no son suyos.

```mermaid
flowchart TD
    D1["D1 · Mis cursos<br/>Publicado, En revisión, Borrador"] --> N{"¿Curso nuevo?"}
    D1 -- "sin cursos" --> VAC["Estado vacío<br/>Crea tu primer curso"]:::nuevo --> D1b
    N -- sí --> D1b["D1b · Nuevo curso<br/>grupo o periodo, PDF o texto de hasta 10 MB"]
    D1b --> D1c["D1c · Extrayendo temas"]
    D1c -- "formato inválido" --> RET["Reintento 2 de 3"]
    RET --> D1c
    D1c -- "PDF sin texto o reintentos agotados" --> D1d["D1d · Error al leer el syllabus<br/>0 caracteres"]
    D1d -- "Pegar el texto" --> D1c
    D1d -- "Subir otro archivo" --> D1b
    D1c --> D2["D2 · Curso y syllabus<br/>columna Revisión"]
    N -- no --> D2
    D2 --> D2b["D2b · Editar tema<br/>subtemas, resultados con Bloom"]
    D2b -- "ciclo de prerrequisitos" --> CIC["Error de ciclo"] --> D2b
    D2b --> D2
    D2 --> D2d["D2d · Grafo de temas<br/>Sin ciclos · validado"]
    D2 -- "Volver a extraer" --> D2c["D2c · Confirmar<br/>se pierden las correcciones"]
    D2c --> D1c
    D2 --> AP{"¿Temas<br/>aprobados?"}
    AP -- corrige --> D2
    AP -- sí --> D5["D5 · Revisión de contenido<br/>fidelidad por recurso"]
    D5 --> D5d["D5d · Editar recurso<br/>versión 1.4, fidelidad recalculada"] --> D5
    D5 --> D5e["D5e · Video del tema<br/>Pertinente o No pertinente, respaldos"]
    D5 --> D5b["D5b · Anotación ciega<br/>evaluador 1 de 2, rúbrica de 4 criterios"]
    D5 --> D5c["D5c · Calificación humana<br/>muestra aleatoria, nota del LLM al guardar"]
    D5e -. "índice de calidad" .-> D5f["D5f · Calidad de los videos<br/>6 señales, Midiendo con menos de 10 notas"]
    D5 --> D3b["D3b · Configurar la ruta<br/>objetivo, umbrales, aviso del piloto"]
    D3b --> D3["D3 · Ruta y avance<br/>matriz de dominio, temas críticos"]
    D3 --> D4["D4 · Detalle de aprendiz<br/>hoja de vida resumida"]
    D4 -- "intentos agotados" --> D4b["D4b · Intentos agotados"]
    D4b --> D4c["D4c · Habilitar intentos<br/>registro en attempt_grants"]
    D4c --> D4
    D4 --> D3

    classDef nuevo stroke-dasharray: 5 5
```

Notas del flujo del instructor:

- **D1b a D1d.** Si el PDF no tiene texto (D1d), el curso vuelve a `draft` con sus datos intactos («No se perdió nada»). «Pegar el texto» reinicia la extracción con el texto pegado; «Subir otro archivo» vuelve a D1b.
- **D5b y D5c (CU-27, CU-28).** El evaluador no ve la anotación del otro ni la nota del LLM hasta guardar. Las solicitudes «Pedir revisión» de los aprendices están en una pestaña aparte y no entran a la muestra aleatoria.
- **D5e.** Si ningún candidato sirve o el video deja de estar disponible, los aprendices ven el primer video de respaldo.
- **D3b.** Cambiar los umbrales durante el piloto rompe la comparación entre grupos; la pantalla lo avisa antes de guardar.

## Administrador

Incluye la gestión de cursos e inscripciones (AD5) y la configuración del piloto (AD4, AD4b).

```mermaid
flowchart TD
    AD1["AD1 · Usuarios y roles<br/>Importar CSV"] <--> AD5["AD5 · Cursos, rutas e inscripciones"]
    AD5 <--> AD4["AD4 · Piloto"]
    AD4 <--> AD2["AD2 · Log LLM y costos"]
    AD2 <--> AD3["AD3 · Métricas globales"]
    AD3 <--> AD1
    AD1 --> NU["Crear usuario, asignar o quitar roles, desactivar"]
    NU --> ULT{"¿Queda al menos<br/>un administrador?"}
    ULT -- no --> BLOQ["Se rechaza el cambio"]:::nuevo
    ULT -- sí --> OK["Cambio auditado y reflejado en Keycloak"]
    AD5 --> CC["Crear curso y asignar instructor"]
    AD5 --> INS["Inscribir aprendiz, elegir grupo del piloto,<br/>cambiar de ruta o retirar"]
    AD5 --> EV["Asignar evaluadores a un curso<br/>course_evaluators"]
    AD4 --> CFG["Ruta, fechas, post-test diferido, semilla"]
    CFG --> SOR["Sortear: ruta personalizada y ruta fija"]
    SOR --> EQ{"¿Ítems equivalentes<br/>verificados?"}
    EQ -- no --> REV["No se puede iniciar"]:::nuevo
    EQ -- sí --> CON{"¿Hay consentimientos<br/>pendientes?"}
    CON -- sí --> AVI["Solo entran al análisis los que aceptaron"]
    CON -- no --> INI
    AVI --> INI["Iniciar piloto"]
    SOR -. "antes de iniciar" .-> SOR
    AD4 --> AD4b["AD4b · Vista previa de la ruta fija<br/>solo lectura"]
    AD2 --> C4["C4 · Catálogo de prompts<br/>10 prompts con versión"]

    classDef nuevo stroke-dasharray: 5 5
```

Notas del flujo del administrador:

- **AD5.** Los cursos y las inscripciones se desactivan o se retiran, no se eliminan, para no perder el historial de intentos. El administrador asigna instructor a un curso «Sin asignar» y, si hace falta, evaluadores externos (que son `instructor`, no un rol aparte).
- **AD4.** Con el piloto sin grupo de ruta fija la pantalla avisa que no se puede calcular la d de Cohen y que la ganancia de Hake se reportaría solo para la ruta personalizada. El sorteo solo se repite antes de iniciar.
- **AD1.** Nunca se deja la plataforma sin administrador y cada cambio de rol queda en la auditoría.

## Diagrama BPMN con carriles

La versión formal en BPMN 2.0 sigue siendo [`flujo-bpmn.drawio`](flujo-bpmn.drawio) (exportada en [`flujo-bpmn.svg`](flujo-bpmn.svg)), pero **corresponde al prototipo v2**: no incluye hoja de vida, consentimiento, piloto ni pantallas de carga y sus carriles dicen «docente» y «estudiante». Actualizarlo y reexportar el SVG queda pendiente (no es obligatorio para la Fase 1; los diagramas Mermaid de este archivo mandan).

![Diagrama BPMN del flujo de una ruta (prototipo v2)](flujo-bpmn.svg)
