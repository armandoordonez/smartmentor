# Bugs

Estados y formato en el [README](README.md#estados). Severidad: **Alta** (rompe un flujo), **Media** (funciona mal o confunde), **Baja** (documentación o detalle). El historial de cada bug está en la [bitácora](BITACORA.md).

| ID | Encontrado | Severidad | Descripción | Estado | Corregido | Commit / PR |
| --- | --- | --- | --- | --- | --- | --- |
| B-001 | 2026-11-12 13:40 | Alta | El arreglo del bloqueo entre la API y `ai/` (PR 4, `448e154`, `FOR NO KEY UPDATE`) **no está en `dev`**. El PR 4 tenía como base `fix/conteos-y-tablero`, que se fusionó en `dev` (PR 3, 2026-11-11 19:10 UTC) antes que él (2026-11-12 01:45 UTC). En `dev`, el diagnóstico y el quiz pueden fallar con `503 AI_SERVICE_UNAVAILABLE` | ⏳ Sin subir, pruebas sin correr | 2026-11-12 14:01 | `0699da7` en `fix/bloqueo-trabajos-ia-a-dev` |
| B-002 | 2026-11-12 13:50 | Baja | Documentos de estado desactualizados frente al código: `proyecto/checklist.md` (avance del 28 %, del 2026-11-07, «la interfaz no ha empezado»), `HANDOFF.md` (del 2026-10-07), `app/README.md` («Fase 7, parte 1») y `CHANGELOG.md` (todavía describe v2). Quien los lea cree que el proyecto está mucho más atrás | ☐ | | |

## Detalle

### B-001 · El arreglo del PR 4 no llegó a `dev`

- **Evidencia:** `git merge-base --is-ancestor origin/fix/bloqueo-trabajos-ia origin/dev` responde que no. `fix/conteos-y-tablero` tiene 2 commits por delante de `dev`: el `448e154` y la fusión del PR 4.
- **Archivos:** 7, con 140 líneas agregadas, entre ellos `api/tests/integration/learning/test_ai_job_row_locks.py` y `api/tests/integration/row_writing_ai.py`.
- **Corrección propuesta:** una rama `fix/bloqueo-trabajos-ia-a-dev` desde `origin/dev` con `git cherry-pick 448e154`, y un PR hacia `dev`. También se puede abrir un PR de `fix/bloqueo-trabajos-ia` directo hacia `dev`.
- **Corrección aplicada (2026-11-12 14:01):** rama `fix/bloqueo-trabajos-ia-a-dev` desde `origin/dev` (`d8de841`) con `git cherry-pick -x 448e154` → `0699da7`. Entró sin conflictos y el `patch-id` coincide con el original (`21f67f3…`), así que es el mismo cambio que el PR 4 ya había probado. Ninguno de los 7 archivos cambió en `dev` desde entonces. Las llaves foráneas de `ai_jobs` apuntan a `courses`, `topics` y `enrollments`, y las tres quedan cubiertas.
- **Falta:** correr `api/scripts/dev.sh all` (no autorizado todavía), subir la rama y abrir el PR hacia `dev`.
- **A revisar aparte:** quedan `with_for_update()` simples en `pilot`, `assessments` e `identity`. Ninguna de esas tablas es destino de una llave foránea de `ai_jobs`, así que no deberían tener este problema. Si `ai/` llegara a escribir filas que apunten a ellas, habría que revisarlas.
- **Cómo evitarlo:** ver la [lección de los PR apilados](README.md#lección-aprendida-pr-apilados).
