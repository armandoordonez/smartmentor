# Bugs

Estados y formato en el [README](README.md#estados). Severidad: **Alta** (rompe un flujo), **Media** (funciona mal o confunde), **Baja** (documentación o detalle). El historial de cada bug está en la [bitácora](BITACORA.md).

| ID | Encontrado | Severidad | Descripción | Estado | Corregido | Commit / PR |
| --- | --- | --- | --- | --- | --- | --- |
| B-001 | 2026-11-12 13:40 | Alta | El arreglo del bloqueo entre la API y `ai/` (PR 4, `448e154`, `FOR NO KEY UPDATE`) **no está en `dev`**. El PR 4 tenía como base `fix/conteos-y-tablero`, que se fusionó en `dev` (PR 3, 2026-11-11 19:10 UTC) antes que él (2026-11-12 01:45 UTC). En `dev`, el diagnóstico y el quiz pueden fallar con `503 AI_SERVICE_UNAVAILABLE` | ☐ | | |
| B-002 | 2026-11-12 13:50 | Baja | Documentos de estado desactualizados frente al código: `proyecto/checklist.md` (avance del 28 %, del 2026-11-07, «la interfaz no ha empezado»), `HANDOFF.md` (del 2026-10-07), `app/README.md` («Fase 7, parte 1») y `CHANGELOG.md` (todavía describe v2). Quien los lea cree que el proyecto está mucho más atrás | ☐ | | |

## Detalle

### B-001 · El arreglo del PR 4 no llegó a `dev`

- **Evidencia:** `git merge-base --is-ancestor origin/fix/bloqueo-trabajos-ia origin/dev` responde que no. `fix/conteos-y-tablero` tiene 2 commits por delante de `dev`: el `448e154` y la fusión del PR 4.
- **Archivos:** 7, con 140 líneas agregadas, entre ellos `api/tests/integration/learning/test_ai_job_row_locks.py` y `api/tests/integration/row_writing_ai.py`.
- **Corrección propuesta:** una rama `fix/bloqueo-trabajos-ia-a-dev` desde `origin/dev` con `git cherry-pick 448e154`, y un PR hacia `dev`. También se puede abrir un PR de `fix/bloqueo-trabajos-ia` directo hacia `dev`.
- **Cómo evitarlo:** ver la [lección de los PR apilados](README.md#lección-aprendida-pr-apilados).
