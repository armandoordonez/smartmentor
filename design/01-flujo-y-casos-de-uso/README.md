# 1. Mapa del flujo y casos de uso

Actividad 1 de la Fase 0 del [brief](../../proyecto/brief.md#fase-0-prototipado-de-la-interfaz-y-del-flujo). Resultado esperado: **flujo aprobado por el director**.

| Archivo | Contenido |
| --- | --- |
| [`casos-de-uso.md`](casos-de-uso.md) | Actores (`learner`, `instructor`, `admin`), 35 casos de uso con sus pantallas y prioridades, trazabilidad, matriz de permisos y decisiones |
| [`flujos.md`](flujos.md) | Diagrama de flujo de entrada y sesión, y uno por rol (aprendiz, instructor, administrador), con los casos de error de las pantallas de carga |
| [`estados.md`](estados.md) | Estados del curso, la inscripción, el paso, el intento, el recurso, el ítem, el trabajo de IA, el piloto y la autorización, más el primer ingreso y el cambio de perfil |
| [`glosario.md`](glosario.md) | Vocabulario de roles, etiquetas por perfil de contexto y qué no cambia con el perfil |
| [`flujo-bpmn.drawio`](flujo-bpmn.drawio) | Diagrama BPMN 2.0 del prototipo v2 con carriles (docente, estudiante, plataforma, IA); su actualización a la v3 está pendiente y los diagramas de estados del tema y de la inscripción, en tres páginas de draw.io |
| [`flujo-bpmn.svg`](flujo-bpmn.svg), [`estados-tema.svg`](estados-tema.svg), [`estados-inscripcion.svg`](estados-inscripcion.svg) | Exportación de cada página del `.drawio` para verla en GitHub |

Herramientas: Mermaid para los diagramas dentro de los `.md` (el mismo formato del brief) y draw.io para el BPMN formal. El `.drawio` se abre en [app.diagrams.net](https://app.diagrams.net) o en draw.io desktop; después de editarlo, se vuelven a exportar los SVG:

```bash
drawio -x -f svg -p 1 -o flujo-bpmn.svg flujo-bpmn.drawio
drawio -x -f svg -p 2 -o estados-tema.svg flujo-bpmn.drawio
drawio -x -f svg -p 3 -o estados-inscripcion.svg flujo-bpmn.drawio
```

## Qué cubre frente al análisis

| Hallazgo del [análisis](../README.md#análisis-detallado-del-prototipo-de-figma) | Cómo se atiende aquí |
| --- | --- |
| ❌ No hay diagrama BPMN ni de estados | BPMN con carriles en draw.io, flujos por rol y diagramas de estados |
| ⚠️ Admin sin login y sin acceso a D1 a D5 | Nodo A8 propuesto y decisión 1 en casos de uso |
| ⚠️ No hay pantalla de creación de curso ni carga del syllabus | Nodo D0 propuesto en el flujo del docente |
| ⚠️ Datos inconsistentes (temas, intentos, cortes del diagnóstico) | Reglas fijadas en `estados.md` y decisiones 2 a 4 |
| ➖ Sin evidencia de aprobación | Registro de aprobación abajo |

## Registro de aprobación

| Fecha | Versión (commit) | Revisó | Decisión | Observaciones |
| --- | --- | --- | --- | --- |
| _pendiente_ | | Director | | |
