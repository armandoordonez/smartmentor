# Bitácora

Registro cronológico de todo lo que se hace. **Solo se agregan entradas al final**; si algo estaba mal, se agrega una entrada nueva que lo corrige. Hora de Bogotá (-05).

Tipos: `INICIO`, `CAMBIO`, `COMMIT`, `PRUEBA`, `BUG`, `CORRECCIÓN`, `FIGMA`, `SUBIDA`, `DECISIÓN`, `NOTA`.

## Plantilla

```markdown
### AAAA-MM-DD HH:MM · TIPO · ID

Qué se hizo o qué se encontró, en una o dos líneas.
- Rama: `<rama>` · Commit: `<hash>` (si aplica)
- Archivos: `<ruta>`, `<ruta>`
- Resultado / evidencia: <comando y resultado, enlace>
```

## Entradas

### 2026-11-12 13:30 · NOTA · —

Descarga del repositorio en este equipo (`/home/vboxuser1/Documents/Pro/Smart`), rama `dev` en `d8de841` (fusión del PR 3).

### 2026-11-12 13:40 · BUG · B-001

El arreglo del PR 4 (`448e154`, bloqueo API ↔ `ai/`) no está en `dev`: se fusionó en `fix/conteos-y-tablero` cuando esa rama ya había entrado a `dev`.
- Evidencia: `git merge-base --is-ancestor origin/fix/bloqueo-trabajos-ia origin/dev` responde que no.

### 2026-11-12 13:50 · BUG · B-002

`proyecto/checklist.md`, `HANDOFF.md`, `app/README.md` y `CHANGELOG.md` describen un estado anterior al real.

### 2026-11-12 13:55 · FIGMA · F-001 a F-011

Revisión del archivo de Figma en vivo frente a `design/03-prototipo-alta-fidelidad/v3/estructura-pantallas.json`: las 96 pantallas coinciden por nombre. Se registran los 4 estados que Figma no dibuja y las 6 contradicciones ya conocidas.

### 2026-11-12 13:57 · INICIO · T-001

Rama `feature/seguimiento-trazabilidad` desde `dev` (`d8de841`) para crear `proyecto/seguimiento/`.

### 2026-11-12 14:05 · CAMBIO · T-001

Se crean `README.md`, `HOJA_DE_RUTA.md`, `BITACORA.md`, `BUGS.md`, `FIGMA.md`, `SUBIDAS.md` y `MEJORAS.md` en `proyecto/seguimiento/`. Falta el commit y la subida (los aprueba el dueño).
- Rama: `feature/seguimiento-trazabilidad` · Sin commit todavía
- Pruebas: no aplican (solo documentación)
