# Bitácora F00 · `feature/repo-standards`

Base de calidad común (plan V3, secciones 14.2, 16, 18.2, 18.8 y 19). Sin `CODEOWNERS` (decisión del dueño).

## Hecho

Rama `feature/repo-standards`, creada desde `feature/baseline-dev` (el worktree arrancó en el commit del brief y se movió a la línea base, que es lo que piden las reglas).

- `.github/workflows/ci.yml`: trabajos `api`, `app` y `liquibase`. Se ejecuta en `push` a `feature/**` y `dev`, y en `pull_request` hacia `dev`. Usa `uv` 0.9.30 con `astral-sh/setup-uv` (no `dev.sh`).
- `ruff.toml` común (E, F, I, B, UP, SIM, ASYNC, S, DTZ, C4, PT, RUF, ARG, T20; línea de 100; comillas dobles). `api/pyproject.toml` y `app/pyproject.toml` lo heredan con `extend` y solo declaran excepciones.
- `.pre-commit-config.yaml`, `.editorconfig`, `.dockerignore` (raíz; se ampliaron los de `api/` y `app/`), `.github/pull_request_template.md`, `.github/dependabot.yml`, `CONTRIBUTING.md`, `docs/standards/definition-of-done.md`, `.python-version` (3.12).
- Lint actual de `api` y `app` en verde con las reglas nuevas (ver Decisiones). Sin cambios de lógica de negocio.
- Commits: ver `git log feature/repo-standards` (primer commit `ci: agrega CI mínima y Ruff común…`).

## Desviaciones frente al plan o al brief

- `api/scripts/dev.sh` y `app/scripts/dev.sh` se tocaron (carpetas de otros agentes) con un cambio mínimo: montan la raíz del repositorio en `/repo` y usan `/repo/api` o `/repo/app` como directorio de trabajo. Sin esto, `extend = "../ruff.toml"` no se encuentra dentro del contenedor y `lint` falla. Quien conserve su propio `dev.sh` debe aplicar el mismo cambio.
- mypy y pytest no van en `pre-commit` (el plan 14.2 menciona mypy): se dejan a la CI y a `dev.sh` por duración y por necesitar el entorno de cada servicio. Los ganchos pedidos por el dueño sí están.
- El trabajo `liquibase` hace `validate` contra una base PostgreSQL efímera: Liquibase 5 exige conexión para validar. La imagen se construye con `database/liquibase/Dockerfile` (base oficial `liquibase/liquibase:5.0.4` más el driver), la misma del compose.
- No se agregó `ai/` a Ruff, Dependabot ni CI: no existe aún. Hay que añadirlo cuando se cree (F4).

## Decisiones

- **Excepciones de Ruff (todas justificadas en el `pyproject.toml`):**
  - `api`: `tests/**` ignora `S101`, `ARG001`, `ARG002` (asserts de pytest; fixtures pedidas por su efecto o firmas heredadas). Tres módulos de producción ignoran `S101` (`app/core/exceptions.py`, `app/domains/identity/authentication.py`, `app/domains/student/service.py`) porque usan `assert` para acotar tipos; reemplazarlos cambia lógica y queda para la Fase 3.
  - `app`: `tests/**` ignora `S101` y `PT018`; `RUF001` global (tipografía `›`, `‹`, `−`, `α` intencional en la interfaz); `DTZ011` solo en `src/clients/sample_data.py` (fecha local de datos de ejemplo).
  - Correcciones triviales: `noqa` de más eliminados (RUF100); `noqa: ARG001` con motivo en dos firmas impuestas por SQLAlchemy y Starlette; `noqa: RUF012` en `__mapper_args__` (`ClassVar` rompe mypy con SQLAlchemy); fixture `clean_database` sin `yield` pasa a `return` (PT022).
- **Imágenes y acciones con versión fija:** `actions/checkout@v7.0.1`, `astral-sh/setup-uv@v10.3.3` (versiones verificadas con `git ls-remote`), `pgvector/pgvector:0.8.7-pg17-bookworm` (igual al compose), uv 0.9.30, Ubuntu 24.04. Pendiente de endurecer: fijar las acciones por SHA de commit (Dependabot las actualizará por etiqueta).
- **Credenciales de la CI:** valores desechables escritos en el workflow (`ci_user`, `ci-only-not-a-secret`); ningún secreto del repositorio ni clave de LLM.
- **`pre-commit` + Ruff:** solo sobre `^(api|app)/`; una ejecución sobre todo el repositorio reportó cientos de avisos en `keycloak/`, `design/` y cuadernos que no son código de servicio.
- **Conventional Commits** con `compilerla/conventional-pre-commit` v4.5.0 en la etapa `commit-msg`.

## Problemas y lecciones

- Ruff con las reglas completas: 331 avisos en `api` y 81 en `app`, de los cuales ~380 eran `S101` en pruebas. El resto fueron pocos y triviales.
- Correr `pre-commit run --all-files` modifica archivos existentes (fin de archivo, espacios, Ruff); se revirtió. La primera aplicación a todo el repositorio queda para una rama de limpieza aparte (el gancho solo revisa archivos tocados).
- El `.git` del worktree es un archivo que apunta fuera del montaje, por lo que `pre-commit` no corre dentro de un contenedor uv; se usó `uvx pre-commit` en el equipo.

## Métricas

- Ruff `check` + `format --check` + mypy estricto: `api` 132 archivos sin avisos (90 en mypy); `app` 51 archivos sin avisos (47 en mypy).
- pytest `api`: **148 pasadas** en 10,5 s, contra una PostgreSQL aislada (contenedor y red temporales, imagen del compose, base `smartmentor_test` migrada con la imagen Liquibase). No se usó `smartmentor-postgres` ni el `.env` del dueño; el contenedor se eliminó al terminar.
- pytest `app`: **36 pasadas** en 5,8 s.
- Liquibase en la base aislada: `validate` sin errores; `update` aplicó 21 changesets.
- `actionlint` 1.7.7 en contenedor sobre `ci.yml`: sin avisos. YAML (`ci.yml`, `dependabot.yml`, `.pre-commit-config.yaml`) válidos con PyYAML. `pre-commit run --all-files`: `check-yaml`, `check-json`, Ruff y `gitleaks` pasan; `end-of-file-fixer` y `trailing-whitespace` señalan archivos antiguos (no los nuevos).
- Pendiente de comprobar solo en GitHub: la ejecución real del workflow (servicio de PostgreSQL de Actions, cachés de `setup-uv`).

## Impacto en el brief

Ninguno. El brief no menciona herramientas de calidad. Para el brief v2, la sección de proceso puede citar la CI mínima, la Definition of Done y el flujo `feature/*` → `dev`.

## Cambios pedidos a archivos compartidos

- `.gitignore`: nada. `.env.example`, `docker-compose.yml`: nada.
- `docs/adr/README.md` / índice: enlazar `docs/standards/definition-of-done.md` y `CONTRIBUTING.md` cuando se consolide.
- Cuando exista `ai/`: sumar su pyproject con `extend = "../ruff.toml"`, un trabajo `ai` en `ci.yml`, una entrada en `dependabot.yml` y su ruta en `files:` de Ruff en `.pre-commit-config.yaml`.
- Checklist: marcar «CI mínima y estándares de repositorio» (`proyecto/checklist.md`, a cargo del integrador).
