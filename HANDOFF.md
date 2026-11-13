# HANDOFF

Estado técnico del proyecto, deuda y próximos pasos para la siguiente cohorte. **Última actualización: 2026-11-13 (cohorte 1).**

Dónde está cada cosa:

- Tareas con fecha y hora, bugs, huecos de Figma y subidas: [`proyecto/seguimiento/`](proyecto/seguimiento/README.md), empezando por la [hoja de ruta](proyecto/seguimiento/HOJA_DE_RUTA.md).
- Avance frente al brief y responsables: [`proyecto/checklist.md`](proyecto/checklist.md).
- Fases y decisiones: el [plan v3](PLAN_IMPLEMENTACION_V3.md).

## Qué funciona

- **Entorno:** `scripts/local-up.sh` levanta todo con Docker Compose: PostgreSQL 17 + pgvector (o una base externa como Neon), Liquibase, la API, el servicio `ai/` y su trabajador, Keycloak, la interfaz y Mailpit. Ver [`README.md`](README.md).
- **Base de datos v2.0.0:** 39 tablas con auditoría y rollback, roles `learner`, `instructor` y `admin`, y usuarios de mínimo privilegio por servicio: `smartmentor_api`, `smartmentor_ai` y `smartmentor_metrics` ([ADR 0019](docs/adr/0019-least-privilege-db-users.md)). Ver [`database/README.md`](database/README.md).
- **API v2** ([contrato](docs/contracts/api-v2.md) y [OpenAPI](docs/contracts/openapi-api.json)): aprendiz, instructor, administrador, piloto, métricas y log del LLM. Las reglas de negocio están en la API, no en la interfaz ([ADR 0017](docs/adr/0017-frontend-rebuilt-from-figma-v3.md)). Hay unas 660 pruebas y la CI está en verde.
- **Servicio `ai/`:** trabajos asíncronos con lease y reintentos ([ADR 0010](docs/adr/0010-async-jobs-postgres-pull-ingestion.md)), prompts versionados ([`prompts/catalog.yaml`](prompts/catalog.yaml)), presupuestos en USD y registro de cada llamada. Hace todo esto:
  - estructurar el syllabus;
  - generar el diagnóstico y estimar el nivel;
  - proponer el objetivo;
  - secuenciar la ruta;
  - explicar con RAG;
  - buscar videos;
  - generar bancos de preguntas, y revisarlos y calificarlos con el LLM como juez.

  **Probado con Gemini real el 2026-11-12:** 354 llamadas, US$ 1,83 ([evidencia de F6](proyecto/seguimiento/HOJA_DE_RUTA.md#evidencia-de-f6-2026-11-12)).
- **Interfaz (Streamlit):**
  - las 96 pantallas de Figma v3 tienen página, con pruebas `AppTest`;
  - las del instructor y las del administrador ya leen la API real;
  - el login es con Keycloak, la sesión dura 3 h y el token de 5 min se renueva solo.
- **Keycloak v3:** realm versionado sin secretos (`sanitize-realm.py`), OTP obligatorio para el instructor y el administrador, y una prueba de importación en la CI.
- **CI** ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)): Ruff, mypy y pytest en los tres servicios, más Liquibase, el realm, los prompts, la documentación, gitleaks y Trivy.
- **Simulación:** [`scripts/simulate-learners.py`](scripts/simulate-learners.py) recorre por la API cada ruta publicada con 4 aprendices de prueba. Es solo para desarrollo.

## Qué no funciona o no existe todavía

| Pendiente | Detalle |
| --- | --- |
| Aprendiz por la interfaz | El catálogo, el perfil, el quiz y la ruta con la API real están en el PR 5 (`fix/flujo-aprendiz`), en borrador. Se fusiona limpio con `dev` y pasan 730 pruebas. Falta verlo en el navegador (T-010 y T-011) |
| Syllabus real | El del curso piloto (T-031) |
| Piloto con personas | Textos legales del consentimiento (T-040), dónde se despliega y quién lo opera (T-043), anotación de expertos y prueba de usabilidad (T-041 y T-042) |
| Revisión visual | Nunca se comparó cada pantalla con su captura de Figma (T-034) |
| Estados que Figma no dibuja | Catálogo vacío, instructor sin cursos y menú de perfil (F-002 a F-004); el estado «sin piloto» de AD4 (F-013) |

## Deuda técnica

- **Secretos en el historial de git:** el realm de Keycloak tuvo secretos y llaves versionados antes de `sanitize-realm.py`. Antes de usar datos reales o hacer público el repositorio, hay que rotarlos y limpiar el historial (T-050).
- **Cliente `smartmentor-dev-tools` (flujo password):** existe solo para desarrollo, porque lo usan Swagger, `api/scripts/token.sh`, Postman y el simulador. Hay que quitarlo antes de producción.
- **Keycloak en `start-dev` (HTTP):** para producción hace falta `start` con HTTPS y un nombre de host fijo.
- **Renovación del token por redirección:** Streamlit no expone el refresh token, así que la app repite `st.login`. Al renovar, la app vuelve a su página de inicio.
- **`ai/` corta las llamadas al LLM a los 240 s:** antes eran 120 s y se cortaban los bancos de preguntas (B-013). El lease de los trabajos no se renueva mientras corren: es de 1800 s.
- **`GET /jobs/{id}` siempre devuelve `next_action` en `null`** (B-012): la app vuelve a leer la inscripción.
- **Dependencias con vulnerabilidades conocidas** en `api/` y `app/`: `certifi` y `pillow` (B-009, trabajo `audit` de la CI).
- **Las pruebas no miden la cobertura.**

## Próximos pasos sugeridos

1. Terminar y fusionar el PR 5 (aprendiz por la interfaz) y recorrer una ruta completa en el navegador.
2. Correr el flujo de punta a punta con el syllabus real del curso piloto (cierra F6).
3. Revisión visual frente a Figma y decidir los estados que Figma no dibuja.
4. Textos legales, despliegue y piloto con 15 a 30 aprendices (F9).
5. Endurecimiento (T-050), brief v2 y etiqueta `v1.0-cohorte1` (F10 y F11).

## Traspaso entre cohortes

Checklist del brief:

- [ ] Versión etiquetada en Git y aplicación desplegada funcionando.
- [x] Este `HANDOFF.md` actualizado (2026-11-13).
- [ ] Notebook de métricas reproducible con los datos del piloto.
- [ ] Datos anonimizados y anotaciones en `data/`.
- [ ] Accesos transferidos (GitHub, despliegue, claves de API, Figma, Keycloak).
- [ ] Brief actualizado con métricas y lecciones aprendidas.

Para pasar los datos de un PC a otro: `database/scripts/backup.sh` en el origen, copiar los `.dump` y `restore.sh` en el destino (aplicación y Keycloak). El `.env` no viaja con git y tiene credenciales: cópialo por un canal seguro o regenéralo con `scripts/gen-secrets.sh`.
