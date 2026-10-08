# 1. Mapa del flujo y casos de uso

Actividad 1 de la Fase 0 del [brief](../../proyecto/brief.md#fase-0-prototipado-de-la-interfaz-y-del-flujo). Resultado esperado: **flujo aprobado por el director**.

| Archivo | Contenido |
| --- | --- |
| [`casos-de-uso.md`](casos-de-uso.md) | Actores, 16 casos de uso con sus pantallas, matriz de permisos y decisiones pendientes |
| [`flujos.md`](flujos.md) | Diagrama de flujo de entrada y sesión, y uno por rol (estudiante, docente, admin) |
| [`estados.md`](estados.md) | Estados de la inscripción, del paso de ruta (tema) y del curso |
| [`flujo-bpmn.drawio`](flujo-bpmn.drawio) | Diagrama BPMN 2.0 con carriles (docente, estudiante, plataforma, IA) y los diagramas de estados del tema y de la inscripción, en tres páginas de draw.io |
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
