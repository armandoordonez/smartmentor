# Mapa de flujo por rol

Un diagrama por rol, con el código de la pantalla de Figma en cada nodo. Los nodos con borde punteado no existen todavía en el prototipo y son los cambios que propone el [análisis](../README.md#análisis-detallado-del-prototipo-de-figma). GitHub muestra los diagramas directamente; para editarlos se puede pegar el bloque en [mermaid.live](https://mermaid.live).

## Entrada y sesión (todos los roles)

```mermaid
flowchart TD
    A1["A1 · Selector de rol<br/>(solo en la demo)"] --> A2["A2 · Login estudiante"]
    A1 --> A4["A4 · Login docente"]
    A1 --> A8["A8 · Login admin"]:::falta
    A2 --> V{"¿Credenciales<br/>válidas?"}
    A4 --> V
    A8 --> V
    V -- no --> ERR["Mensaje de error<br/>en la misma pantalla"] --> A2
    V -- sí --> R{"¿Rol?"}
    R -- docente o admin --> MFA["Verificación<br/>en dos pasos"]:::falta
    MFA --> R2{"¿Rol?"}
    R2 -- docente --> D1["D1 · Mis cursos"]
    R2 -- admin --> AD1["AD1 · Usuarios y roles"]
    R -- estudiante --> E1["E1 · Catálogo"]
    X["Cualquier pantalla"] -- token vencido --> A7["A7 · Sesión expirada"] --> A2
    X -- rol sin permiso --> A6["A6 · 403 Sin permiso"] --> H["Volver al inicio de su rol"]

    classDef falta stroke-dasharray: 5 5
```

## Estudiante

```mermaid
flowchart TD
    E1["E1 · Catálogo de rutas"] --> I{"¿Ya inscrito?"}
    I -- no --> INS["Inscribirse"] --> E2["E2 · Perfil<br/>descripción libre"]
    I -- sí --> E5
    E2 --> E3["E3 · Diagnóstico<br/>2 a 3 preguntas por tema"]
    E3 --> E4["E4 · Resultado del diagnóstico<br/>nivel por tema + objetivo"]
    E4 --> OBJ{"¿Acepta el<br/>objetivo?"}
    OBJ -- edita --> E4
    OBJ -- sí --> E5["E5 · Vista de ruta"]
    E5 --> E6["E6 · Tema<br/>video + texto + quiz"]
    E6 --> E7["E7 · Resultado del quiz"]
    E7 --> Q{"¿≥ 70 %?"}
    Q -- sí --> E5
    Q -- no --> INT{"¿Quedan<br/>intentos?"}
    INT -- sí --> REF["Explicación alterna<br/>y preguntas nuevas"] --> E6
    INT -- no --> AGO["Intentos agotados<br/>aviso al docente"]:::falta --> E5
    E5 -- todos los temas completados --> E8["E8 · Evaluación final"]
    E8 --> F{"¿≥ 80 %?"}
    F -- no --> E9["E9 · Repaso dirigido<br/>temas débiles"] --> E8
    F -- sí --> E10["E10 · Badge"]
    E10 --> E12["E12 · Logros"]
    E5 -.-> E11["E11 · Mi progreso"]

    classDef falta stroke-dasharray: 5 5
```

Personalización: los temas con dominio ≥ 80 % en el diagnóstico aparecen en E5 como «Omitido» y cuentan como completados.

## Docente

```mermaid
flowchart TD
    D1["D1 · Mis cursos"] --> N{"¿Curso nuevo?"}
    N -- sí --> D0["D0 · Crear curso<br/>y cargar syllabus"]:::falta
    D0 --> EXT["IA extrae temas,<br/>resultados y prerrequisitos"]
    EXT --> D2
    N -- no --> D2["D2 · Curso y syllabus<br/>revisar y aprobar temas"]
    D2 --> AP{"¿Temas<br/>aprobados?"}
    AP -- corrige --> D2
    AP -- sí --> D5["D5 · Revisión de recursos<br/>y preguntas"]
    D5 --> D3["D3 · Ruta y avance<br/>objetivo y umbrales"]
    D3 --> D4["D4 · Detalle de estudiante<br/>intentos por tema"]
    D4 --> D3
    D1 -- sin cursos --> VAC["Estado vacío<br/>«Crea tu primer curso»"]:::falta

    classDef falta stroke-dasharray: 5 5
```

## Admin

```mermaid
flowchart TD
    AD1["AD1 · Usuarios y roles"] <--> AD2["AD2 · Log LLM y costos"]
    AD2 <--> AD3["AD3 · Métricas globales"]
    AD3 <--> AD1
    AD1 --> NU["Crear docente o admin<br/>asignar rol, desactivar"]
    AD2 --> FIL["Filtrar por tarea, modelo<br/>y versión de prompt"]
    AD1 -. "decisión pendiente" .-> D1["D1 · Mis cursos"]:::falta

    classDef falta stroke-dasharray: 5 5
```

## Flujo BPMN con carriles

Versión formal en BPMN 2.0, hecha en draw.io: [`flujo-bpmn.drawio`](flujo-bpmn.drawio) (página 1). Un solo proceso recorre los cuatro carriles: el docente prepara el curso, la plataforma lo publica, el estudiante lo recorre y el sistema de IA genera y califica. Las tareas con persona son tareas de usuario y las de engranaje, tareas de servicio.

![Diagrama BPMN del flujo de una ruta](flujo-bpmn.svg)
