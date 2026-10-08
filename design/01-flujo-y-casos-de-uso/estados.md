# Diagramas de estados

Estos diagramas fijan las reglas que hoy el prototipo muestra de forma inconsistente (número de temas, cuándo un intento cuenta como aprobado, fecha del badge). Los umbrales son los del brief y los define el docente por ruta: tema ≥ 70 %, final ≥ 80 %, máximo 3 intentos y omitir tema con diagnóstico ≥ 80 %.

## Inscripción del estudiante a una ruta

```mermaid
stateDiagram-v2
    [*] --> Inscrito
    Inscrito --> PerfilCompleto: guarda la descripción (E2)
    PerfilCompleto --> Diagnosticado: termina el diagnóstico (E3)
    Diagnosticado --> EnRuta: confirma el objetivo (E4)
    EnRuta --> EvaluacionFinal: todos los temas aprobados u omitidos
    EvaluacionFinal --> Repaso: final < 80 %
    Repaso --> EvaluacionFinal: nuevo intento
    EvaluacionFinal --> Certificado: final ≥ 80 %
    Certificado --> [*]
    Inscrito --> Abandonado: abandona
    EnRuta --> Abandonado: abandona
    Abandonado --> [*]

    EnRuta: En ruta
    EvaluacionFinal: Evaluación final
    PerfilCompleto: Perfil completo
    Certificado: Certificado (badge emitido)
```

## Paso de ruta (un tema para un estudiante)

```mermaid
stateDiagram-v2
    [*] --> Omitido: diagnóstico ≥ 80 %
    [*] --> Bloqueado: tiene prerrequisitos sin completar
    [*] --> Pendiente: sin prerrequisitos pendientes
    Bloqueado --> Pendiente: prerrequisitos completados
    Pendiente --> EnCurso: abre el tema (E6)
    EnCurso --> Aprobado: quiz ≥ 70 %
    EnCurso --> Refuerzo: quiz < 70 % y quedan intentos
    Refuerzo --> EnCurso: explicación alterna y preguntas nuevas
    EnCurso --> Agotado: quiz < 70 % en el intento 3
    Agotado --> EnCurso: el docente concede un intento más
    Aprobado --> [*]
    Omitido --> [*]

    EnCurso: En curso (intento n de 3)
    Agotado: Intentos agotados
```

Reglas derivadas:

- **Completado** = Aprobado u Omitido. La barra de avance de E5 cuenta ambos.
- Un tema omitido se puede repasar, pero su quiz no cambia el estado.
- El intento cuenta en cuanto se envía el quiz; abrir el tema no consume intentos.
- El puntaje que se muestra es el del último intento; el docente ve todos en D4.

Versión en draw.io: [`flujo-bpmn.drawio`](flujo-bpmn.drawio), páginas 2 (tema) y 3 (inscripción), exportadas en [`estados-tema.svg`](estados-tema.svg) y [`estados-inscripcion.svg`](estados-inscripcion.svg).

## Curso y syllabus

```mermaid
stateDiagram-v2
    [*] --> Borrador: crea el curso (D0)
    Borrador --> Extrayendo: carga el syllabus
    Extrayendo --> EnRevision: la IA devuelve temas válidos
    Extrayendo --> Borrador: JSON inválido o PDF ilegible
    EnRevision --> Aprobado: el docente aprueba los temas (D2)
    Aprobado --> Publicado: recursos y preguntas revisados (D5)
    Publicado --> Archivado: cierre del curso
    Archivado --> [*]

    EnRevision: En revisión
```

Un curso solo aparece en el catálogo del estudiante (E1) cuando está **Publicado**.
