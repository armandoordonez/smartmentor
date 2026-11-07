# Bitácora · Integración de la Ola 0

## Hecho
- Se integraron en `feature/integration-ola0` (partiendo de `feature/repo-standards`, con fusiones `--no-ff`): `v3-only-sources`, `design-use-cases-v3`, `adr-architecture-v3` y `prompts-and-contracts`. Sin conflictos.
- Se agregó el tablero de avance (sección 21 del plan) y se cerraron D-01 y D-02 en `decisiones-pendientes.md`.

## Validación local (2026-11-07)
| Servicio | Resultado |
| --- | --- |
| `api` | Ruff y mypy sin errores; 148 pruebas pasan |
| `app` | Ruff y mypy sin errores; 36 pruebas pasan |
| `ai` | Ruff y mypy sin errores (26 archivos); 197 pruebas pasan |
| `docker compose config` | Válido |

## Problemas y lecciones
- `api/scripts/dev.sh` y `app/scripts/dev.sh` ahora montan la raíz del repositorio en `/repo` y trabajan en `/repo/<servicio>`. Un `.venv` creado antes con el montaje antiguo (`/app`) queda con rutas inválidas y `uv run mypy` falla con «Failed to spawn: mypy». **Solución: mover o borrar `api/.venv`, `app/.venv` y `ai/.venv` una vez**; `uv` los recrea. Está anotado para el README de cada servicio.
- Las pruebas de `ai` leen `prompts/` y exigen montar la raíz del repositorio; falta `ai/scripts/dev.sh` (lo crea la Fase 4).

## Impacto en el brief
Ninguno.
