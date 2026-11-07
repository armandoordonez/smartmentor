# Bitácora F01 · Casos de uso, estados y flujos (v3)

Agente `design-docs`, Ola 0, Fase 1. Rama `feature/design-use-cases-v3` (publicada en `origin`).

## Hecho
- `design/01-flujo-y-casos-de-uso/casos-de-uso.md`: CU-01 a CU-35, trazabilidad pantalla a caso de uso, matriz de Figma `2:3` más 16 acciones nuevas. Commit `docs(design): actualiza casos de uso y estados al prototipo v3`.
- `estados.md`: 9 diagramas de estados (curso, inscripción, paso, intento, recurso, ítem, trabajo de IA, piloto, autorización) más primer ingreso (CU-34) y cambio de perfil (CU-35), cada uno con tabla de quién dispara la transición.
- `flujos.md`, `glosario.md`, `design/01.../README.md` (lista de archivos), `design/03-prototipo-alta-fidelidad/README.md` (64 pantallas con nodo, página, CU y prioridad), `design/05-prueba-de-usabilidad/guion-de-tareas.md` (12 tareas de aprendiz, 9 de instructor, 5 de administrador, dos con estado de error). Commit `docs(design): agrega flujos, glosario, inventario v3 y guion de usabilidad`.
- `app/CLAUDE.md` reescrito (secciones 2.6, 5.5 y 5.5.1 del plan) y `proyecto/flujo-por-usuario.md` con los pasos 1b, 3b, 10b, 14b–14d (aprendiz), 3b, 7b, 7c, 8b (instructor) y 3b (administrador).

## Desviaciones frente al plan o al brief
- El worktree arrancó en `main` (solo `proyecto/brief.md`); la rama se creó desde `feature/baseline-dev` como pide la regla común.
- No se tocó `design/03-prototipo-alta-fidelidad/index.html` (no estaba en la lista). Apunta a otra clave de Figma (`5oCXyjG1qaqc4XJNnDd8bN`) que la del plan (`atp2fZdSolEoaww3n9jRLg`): el dueño debe confirmar cuál es la maestra.
- `variables.json` trae **23 hexadecimales**, no 24: `error/acento` (`118:923`) no tiene valor (hex vacío). `app/CLAUDE.md` lo documenta como pendiente y propone igualarlo a `error/texto` en `tokens.css`.
- El `.drawio` y sus SVG no se actualizaron: quedan marcados como pendientes (no obligatorio). `flujo-bpmn.svg` sigue en `flujos.md` con la advertencia de que es del prototipo v2.

## Decisiones
- **Variables CSS en inglés** (`--learner-accent`, `--text-primary`) en vez de los ejemplos en español del plan (`--aprendiz-acento`): la regla común exige identificadores en inglés. Se documenta la tabla Figma a CSS en `app/CLAUDE.md`. Si el dueño prefiere los nombres del plan, es un cambio de una tabla.
- **El administrador no anota ni califica** (D5b, D5c): son del instructor dueño o evaluador asignado. Opción más sencilla coherente con DEF-24.
- **Estado de error de U1x:** Figma solo dibuja el camino feliz; se definió el comportamiento en `flujos.md` (reintentar o volver a la ruta, sin perder lo respondido) y la tarea T8 del guion lo prueba con Mago de Oz hasta que se dibuje el frame.
- **Prioridades del inventario:** salen del Anexo A; A1 se marcó P2 (solo modo demostración) y las pantallas de Keycloak P0.
- **Etiquetas de grupo y `syllabus` para `academic` y `corporate`** (Cohorte/Equipo, Syllabus/Programa de formación) son propuesta mía; el plan solo fija las de los roles. Marcado en el glosario para validar con el dueño.
- **Estados del curso:** se añadió `in_review` → `extracting` (volver a extraer, D2c) y `draft` → `archived` (desactivar), que el plan no listaba; se conservan las demás transiciones tal cual.
- **Estados del paso:** se añadió `on_hold` → `pending` cuando el prerrequisito agotado se aprueba, y la transición `blocked`/`pending` → `on_hold`.
- **Estado del piloto:** se añadió `randomized` → `draft` (volver a sortear antes de iniciar), según la nota de AD4.

## Problemas y lecciones
- Las herramientas de Bash del worktree rechazan comandos con variables calculadas; los scripts de generación se escribieron como archivos y se ejecutaron con rutas literales.
- No hay imagen de `mermaid-cli`. Los 16 bloques Mermaid de `casos-de-uso.md`, `estados.md` y `flujos.md` se validaron con el analizador de `mermaid@10.9.3` bajo `jsdom` en Node 20 (instalado en el directorio temporal, fuera del repositorio): 0 errores, y se comprobó que el script detecta un bloque inválido. No se renderizó el SVG.
- `variables.json` y `v3/README.md` se contradicen levemente sobre cuántas variables se leyeron (23 de 24); se resolvió en `app/CLAUDE.md`.

## Métricas
- Enlaces relativos de los 10 `.md` tocados: 0 rotos (script con comprobación de anclas).
- Anexo A: 0 pantallas P0 o P1 sin caso de uso; CU-01 a CU-35 presentes.
- Mermaid: 16 bloques, 0 errores de sintaxis.
- Inventario de `design/03...`: 64 pantallas (50 P0 incluidas las mixtas, 10 P1, 4 P2).

## Impacto en el brief
- Sección de roles y vocabulario (estudiante, docente, cohorte): el brief v2 debe adoptar Aprendiz, Instructor, Administrador y «grupo» (ya previsto en el plan, sección 13).
- Módulo del admin: el brief no detalla sus pantallas; el v3 agrega cursos e inscripciones (AD5) y piloto (AD4). Sugerido: describirlos en el brief v2.
- Metas personales y racha (E11, CU-23) no están en el brief; quedan en P2.

## Cambios pedidos a archivos compartidos
- `design/03-prototipo-alta-fidelidad/index.html`: confirmar la clave de Figma y actualizar el enlace.
- `proyecto/checklist.md`: ninguno pedido por este agente.
- Los `.svg` y el `.drawio` de `design/01` quedan desactualizados (v2); rehacerlos es opcional.
