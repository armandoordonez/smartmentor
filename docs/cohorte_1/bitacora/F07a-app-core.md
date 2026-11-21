# Bitácora F07a · `feature/app-v3-core`

Fase 7, parte 1 (Ola 1): base de la interfaz v3. Rama creada desde `origin/dev`.

## Hecho

- Commit `da7ae9b` y siguientes en `feature/app-v3-core`.
- Prototipo de la Fase 0 reemplazado (`pages/student|teacher|admin`, `sample_data`, `sample_seed`, servicios y pruebas viejas). Se conservan Dockerfile, `pyproject.toml`, `dev.sh`, Ruff y mypy estrictos, fuente Inter.
- Estilos: `static/styles/` (`README.md`, `tokens.css` único con hexadecimales, `base`, `layout`, `roles`, `components/`) y `core/styles.py`. `config.toml` con los tokens v3.
- `core`: `auth` (st.login, `exp`, URL de cierre), `bootstrap_secrets` (secrets.toml desde el entorno, 0600), `labels` (glosario `generic`; `academic` y `corporate` incluidos como P2), `navigation` (páginas registradas por existencia de archivo, menú por rol, `next_action` a página), `identity`, `session`, `errors`, `container`.
- `clients`: `api.py` (httpx, token por llamada, RFC 9457, `Idempotency-Key`, `X-Request-ID`), `fixtures.py` + 24 JSON en `tests/fixtures/`, `jobs.py` (sondeo progresivo), `models.py` (contrato `api-v2.md`).
- 17 componentes de la sección 5.5 más `role_card` y `video_player`.
- Páginas: A1 (solo fixtures), A3/A3b (`consent`), A3c, A6/A7 (en `main.py`), E1, E2, E2b, E15, `coming_soon`. Cambio de perfil (CU-35) en el menú del avatar.
- `app/README.md` reescrito; `static/styles/README.md`.

## Desviaciones frente al plan o al brief

- Modelos escritos a mano desde el contrato (no hay OpenAPI aún); no existe `dev.sh gen-models`.
- `inject_styles()` se llama desde `main.py` y no desde `render_header`, para estilizar también las pantallas previas al login.
- El contrato no fija `LearningPathCard`, `Consent` ni `BadgeSummary`: son propuestas (ver models.py).
- Ni `borde/default` (1,25:1) ni `borde/fuerte` (1,59:1) llegan a 3:1. Se propone `--border-field: #838b9b` (3,42:1 sobre blanco, 3,17:1 sobre la página), usado como `borderColor` de Streamlit. No está en Figma.
- A3c y A3b: «universidad» sale de `ORGANIZATION_NAME`; la ventana del piloto, de `PILOT_WINDOW_TEXT` (C-03).
- Hoja de vida: solo se editan los idiomas que ya tiene el perfil (una fila mínima); «+ Agregar idioma» queda fuera.
- El fixtures client repite un eco mínimo de estado (consentimiento, perfil, inscripción) para poder navegar.

## Decisiones

- Catálogo sin caché compartida (la etiqueta «Recomendada para ti» es personal).
- `APP_DATA_SOURCE` por omisión `api`; `fixtures` se rechaza con `APP_ENV=production`.
- Un 401 o un 403 de rol/cuenta lo atiende `main.py`; el resto se muestra en la pantalla (`show_action_error`).
- Tras aceptar el consentimiento se hace `st.rerun()` y luego `switch_page`, porque durante esa ejecución la navegación solo tenía las pantallas de consentimiento.
- Color del botón principal por rol (P1): contenedor `role-<rol>` y `data-testid` del botón; no verificado en un navegador.

## Problemas y lecciones

- Los comandos Bash complejos (heredocs, variables) los rechaza el aislamiento del worktree: se usaron scripts en el scratchpad.
- `AppTest` ve `st.badge` como Markdown `:color-badge[...]`; el popover y los `button_group` (pills) requieren tratamiento especial en el lector de textos.
- Un bug real hallado por las pruebas: el mínimo de criterios (2/3 = 0,6667) daba 3 por ruido de coma flotante.

## Métricas

- `ruff check` y `ruff format --check`: limpios. `mypy` estricto: 0 errores en 49 archivos.
- `pytest`: 274 pasan (unit, componentes, páginas, modo api con `respx`) en unos 16 s.
- Contraste: 29 pares de texto de 4,99:1 a 17,78:1 (AA).
- Comparación con `estructura-pantallas.json`: E1 (31 textos), E2 (6), E2b (37), E15 (37) y A3b: sin diferencias. A3c: 2 diferencias, ambas por «universidad». A1: solo falta el botón «Demo» (no se construye). A6: una línea con otro nombre de página.
- Contenedor: imagen construida con el Dockerfile; arranca en fixtures y responde `/_stcore/health`; en `api` sin secretos falla nombrando las variables; con secretos genera `secrets.toml` 0600. También se verificó con la imagen uv montando el repositorio.

## Impacto en el brief

- Sección de roles y vocabulario: la interfaz usa Aprendiz/Instructor/Administrador desde el glosario.
- Sección de accesibilidad: los bordes de Figma no cumplen 3:1; proponer `--border-field`.

## Cambios pedidos a archivos compartidos

- `.github/workflows/ci.yml`: `APP_DATA_SOURCE: sample` ya no es válido; cambiar a `fixtures` (las pruebas lo fuerzan, pero conviene corregirlo).
- `docker-compose.yml` (servicio `app`): `APP_DATA_SOURCE` por omisión `api` o `fixtures`; variables `APP_ENV`, `APP_PUBLIC_URL`, `APP_CONTEXT_PROFILE`, `ORGANIZATION_NAME`, `API_BASE_URL=http://api:8020`, `OIDC_SERVER_METADATA_URL`, `OIDC_UI_CLIENT_ID`, `OIDC_UI_CLIENT_SECRET`, `APP_COOKIE_SECRET`; puerto 8501.
- `.env.example`: agregar `OIDC_SERVER_METADATA_URL` y `PILOT_WINDOW_TEXT`; `APP_DATA_SOURCE=api|fixtures`.
- `app/CLAUDE.md` (mío): pendiente actualizar «Estado» y la tabla de tokens con `--border-field`.

## Qué falta

- Páginas E3 a E14, instructor y administrador (siguientes agentes).
- Prueba técnica del login con un Keycloak real (7.0, Fase 8).
- Revisión visual en navegador (la captura headless no renderizó) y del color de botón por rol.
- Actualizar `app/CLAUDE.md` (estado y `--border-field`).
