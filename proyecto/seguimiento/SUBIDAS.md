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
