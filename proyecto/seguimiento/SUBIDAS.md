# Subidas a GitHub

Registro de cada `push` y cada pull request. **Solo se agregan entradas al final.** Se sube únicamente con la aprobación del dueño, a ramas `feature/*` o `fix/*`, y nunca a `dev`, `stage` ni `main` ([README](README.md#flujo-de-trabajo)).

Repositorio: <https://github.com/armandoordonez/smartmentor>

## Plantilla

```markdown
### S-NNN · AAAA-MM-DD HH:MM · <rama>

- **Commits:** `abc1234` título, `def5678` título
- **IDs:** T-NNN, B-NNN
- **PR:** <enlace> hacia `dev` (abierto / fusionado el AAAA-MM-DD HH:MM en `hash`)
- **CI:** en verde / falló (qué paso) / sin correr
- **Pruebas locales:** comando y resultado, o «sin correr» y por qué
- **Quién aprobó la subida:** <persona>
```

## Antecedentes (antes de este registro)

| PR | Rama → base | Estado | Nota |
| --- | --- | --- | --- |
| 1 | `fix/syllabus-como-fuente-rag` → `dev` | Fusionado 2026-11-11 | |
| 2 | `feature/archivar-curso` → `fix/syllabus-como-fuente-rag` | Fusionado 2026-11-11 | Llegó a `dev` con el PR 1 |
| 3 | `fix/conteos-y-tablero` → `dev` | Fusionado 2026-11-11 (`d8de841`) | |
| 4 | `fix/bloqueo-trabajos-ia` → `fix/conteos-y-tablero` | Fusionado 2026-11-12 | **No llegó a `dev`** ([B-001](BUGS.md)) |
| 5 | `fix/flujo-aprendiz` → `dev` | Borrador | 3 commits por delante de `dev` |

## Registro

### S-001 · 2026-11-12 15:01 · `feature/seguimiento-trazabilidad`

- **Commits** (base `dev` = `d8de841`):
  - `ee2ee75` docs(proyecto): agrega la carpeta de seguimiento y trazabilidad [T-001]
  - `02c4f5a` docs(proyecto): registra la corrección de B-001 y corrige una hora de la bitácora [T-002]
  - `d47df63` feat: pantallas del instructor y del administrador con la API real [T-012 T-013 T-014 T-015]
  - `54b8b1e` docs(proyecto): seguimiento de T-012 a T-015, bugs B-003 a B-008 y estado por fase
  - `4ea823f` fix(api): bloquear con FOR NO KEY UPDATE para que ai/ pueda guardar sus trabajos (cherry-pick de `448e154`, autora Alexander Amador) [B-001]
- **IDs:** T-001, T-002, T-012, T-013, T-014, T-015a a T-015e, B-001, B-003 a B-008, F-012 a F-014
- **PR:** ninguno todavía. Se puede abrir en <https://github.com/armandoordonez/smartmentor/pull/new/feature/seguimiento-trazabilidad>
- **CI:** la corrida `43296141612` quedó en cola a las 15:01; su resultado se anota cuando termine
- **Pruebas locales:** sin correr (el dueño no autorizó ejecutar el proyecto)
- **Fuera de la subida:** `pr-3-descripcion-actualizada.md` (borrador del dueño, sin versionar)
- **Quién aprobó la subida:** el dueño, en el chat (2026-11-12 15:02)

### S-002 · 2026-11-12 15:05 a 15:25 · `feature/seguimiento-trazabilidad`

Correcciones que pidió la CI. Las pruebas no se pueden correr en este equipo (no hay Docker ni `uv`), así que el dueño pidió las pruebas y se corrieron en la CI:
- `73c9224` style: Ruff lint (I001, SIM108, E501, PT018) y un enlace roto → CI `43304494731`: falló el formato (app) y E501 (API)
- `7181ee3` style: línea larga y formato → CI `43304868193`: app con 620 pruebas en verde y 1 fallida (AD3 frente a Figma: faltaba la cohorte en el encabezado); API con el formato de 2 archivos
- `0c07692` fix(app): la cohorte vuelve al encabezado de AD3, y el formato del piloto → CI `43305251283`: app en verde; API con 659 en verde y 1 fallida (el OpenAPI publicado no coincidía: faltaba la descripción nueva de `GET /metrics/evaluation`)
- `58badeb` docs(contracts): sincroniza esa descripción → **CI `43305654426` en verde**

### Resultado de las pruebas · 2026-11-12 15:31

| Servicio | Ruff | Formato | mypy estricto | pytest |
| --- | --- | --- | --- | --- |
| api | ✔ | ✔ (216 archivos) | ✔ (141) | ✔ **660 en verde** |
| app | ✔ | ✔ (141) | ✔ (104) | ✔ **621 en verde** |
| ai | ✔ | ✔ (150) | ✔ (145) | ✔ 463 en verde, 10 omitidas |

También en verde: liquibase, keycloak-realm, prompts, infra, docs (markdownlint y enlaces), secrets (gitleaks) e images (Trivy). Fallan solo `audit (api)` y `audit (app)`, que son informativos y ya fallaban en `dev` ([B-009](BUGS.md)).
