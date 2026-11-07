# Guía de contribución

Cómo se trabaja en SmartMentor. La fuente de verdad del plan es [`PLAN_IMPLEMENTACION_V3.md`](PLAN_IMPLEMENTACION_V3.md) (secciones 14, 16 y 18) y la estrategia de ramas está en [`GIT_VERSIONING_STRATEGY.md`](GIT_VERSIONING_STRATEGY.md).

## 1. Idioma

- Documentos, comentarios de base de datos y mensajes de commit: **español**.
- Código, tablas, columnas, campos JSON, rutas de API y nombres de archivos de código: **inglés**.
- Roles: `learner` (Aprendiz), `instructor` (Instructor) y `admin` (Administrador).

## 2. Ramas

| Rama | Uso |
| --- | --- |
| `main` y `stage` | Entrega y preproducción. **No se tocan** desde una rama de trabajo |
| `dev` | Integración; tope de todas las features |
| `feature/<tema>` | Una rama por tema, creada desde `dev`, con pull request hacia `dev` |

Flujo: `feature/*` → pull request hacia `dev` (con la CI en verde) → el dueño promueve `dev` → `stage` → `main`. Nunca `push --force`, nunca borrar ramas remotas, nunca `push` directo a `stage` ni `main`.

## 3. Commits

[Conventional Commits](https://www.conventionalcommits.org/) con la descripción en español:

```text
feat(api): agrega el endpoint de rutas de aprendizaje
fix(app): corrige el filtro de cursos
docs(adr): registra la decisión sobre el proveedor de IA
ci: agrega la validación de Liquibase
```

Tipos: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`. Todo commit termina con el pie de coautoría del equipo:

```text
Co-Authored-By: Eduar Troyano <eatroyano@gmail.com>
Co-Authored-By: Alexander Amador <alexanderamam1@gmail.com>
Co-Authored-By: Nicolas Potes <arquitectosystem@gmail.com>
Co-Authored-By: Carlos Villada <carlos.villada63@gmail.com>
```

## 4. Comprobaciones antes del pull request

La CI (`.github/workflows/ci.yml`) corre en cada `push` a `feature/**` y `dev`, y en cada pull request hacia `dev`: Ruff (lint y formato), mypy estricto y pytest de `api` y `app`, y `liquibase validate`. Corre lo mismo en local antes de subir:

```bash
# Ruff, mypy y pytest de cada servicio (requiere Docker; api necesita PostgreSQL arriba)
api/scripts/dev.sh all
app/scripts/dev.sh all

# Solo lint y tipos, sin base de datos
api/scripts/dev.sh lint && api/scripts/dev.sh typecheck
app/scripts/dev.sh lint && app/scripts/dev.sh typecheck
```

Con `uv` instalado también sirve, desde `api/` o `app/`: `uv sync && uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest`.

La configuración de Ruff es común: [`ruff.toml`](ruff.toml) en la raíz, que `api/pyproject.toml` y `app/pyproject.toml` heredan con `extend`. Una excepción nueva (`per-file-ignores` o `# noqa`) debe llevar su justificación al lado.

### Ganchos locales (`pre-commit`)

```bash
uv tool install pre-commit
pre-commit install          # instala el gancho de commit y el del mensaje de commit
pre-commit run --all-files  # revisión manual de todo el repositorio
```

Los ganchos corren Ruff (lint y formato), `check-yaml`, `check-json`, fin de archivo, espacios finales, `gitleaks` (secretos) y la verificación de Conventional Commits. mypy y pytest quedan para la CI y `dev.sh` por su duración.

## 5. Política de `.env` y secretos

- El `.env` real **nunca** se versiona (está en `.gitignore`) ni entra a una imagen (`.dockerignore`). Solo se versiona `.env.example`, sin valores secretos.
- Toda credencial (usuarios, contraseñas, claves, nombres de modelos) se lee de variables de entorno con `pydantic-settings` o `${VAR}` en el compose. Nada de esto va escrito en el código, los YAML ni los changelogs.
- Las pruebas y la CI usan valores desechables evidentes (por ejemplo `test-only-not-a-secret`) y nunca claves reales de proveedores de IA.
- Si una variable nueva hace falta, se agrega a `.env.example` con un comentario (para qué sirve y quién la define).
- Si se publica un secreto por error: avisar al dueño de inmediato para rotarlo; borrarlo del commit no basta.

## 6. Pull requests

Usa la plantilla de [`.github/pull_request_template.md`](.github/pull_request_template.md). Mantenlos pequeños y de un solo tema, y revisa la lista de [`docs/standards/definition-of-done.md`](docs/standards/definition-of-done.md). Las decisiones de arquitectura van como ADR en `docs/adr/`.
