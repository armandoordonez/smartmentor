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

### 2026-11-12 14:00 · COMMIT · T-001

Commit de la carpeta de seguimiento.
- Rama: `feature/seguimiento-trazabilidad` · Commit: `ee2ee75`

### 2026-11-12 14:01 · CORRECCIÓN · —

La entrada «2026-11-12 14:05 · CAMBIO · T-001» tiene una hora estimada a mano que quedó adelantada. Los archivos se crearon entre las 13:57 y las 14:00 (la hora del commit `ee2ee75`). Desde ahora, toda hora sale de `TZ=America/Bogota date` o de la hora del commit.

### 2026-11-12 14:01 · INICIO · T-002 · B-001

Rama `fix/bloqueo-trabajos-ia-a-dev` desde `origin/dev` (`d8de841`).

### 2026-11-12 14:01 · CORRECCIÓN · B-001

`git cherry-pick -x 448e154` → `0699da7`, sin conflictos. Conserva como autora a Alexander Amador y el mensaje original, con la referencia «cherry picked from».
- Rama: `fix/bloqueo-trabajos-ia-a-dev` · Commit: `0699da7`
- Archivos: `api/app/domains/content/{ingestion,repository_impl}.py`, `api/app/domains/courses/repository_impl.py`, `api/app/domains/learning_paths/repository_impl.py` y 3 archivos de pruebas de integración
- Evidencia: el `patch-id --stable` coincide con el del original (`21f67f3`), y ninguno de los 7 archivos cambió en `dev` desde la base del PR 4

### 2026-11-12 14:01 · PRUEBA · B-001

Sin correr: `api/scripts/dev.sh all` necesita Docker y PostgreSQL, y el dueño todavía no autoriza ejecutar el proyecto. Según su descripción, el PR 4 pasó sus pruebas en su rama original.
