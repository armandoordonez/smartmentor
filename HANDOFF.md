# HANDOFF

Estado técnico del proyecto, deuda y próximos pasos para la siguiente cohorte. **Última actualización: 2026-11-21 (release `v1.0-cohorte1` publicado).**

Dónde está cada cosa:

- Tareas con fecha y hora, bugs, huecos de Figma y subidas: [`docs/cohorte_1/trazabilidad/`](docs/cohorte_1/trazabilidad/TRAZABILIDAD.md#cómo-se-lleva-este-registro), empezando por la [hoja de ruta](docs/cohorte_1/trazabilidad/HOJA_DE_RUTA.md).
- Avance frente al brief y responsables: [brief de la cohorte 1](proyecto/cohorte_1/brief.md#12-gestión-del-proyecto) y la [trazabilidad](docs/cohorte_1/trazabilidad/TRAZABILIDAD.md).
- Fases y decisiones: el [plan v3](PLAN_IMPLEMENTACION_V3.md).
- Lo planteado frente a lo logrado: el [brief de la cohorte 1](proyecto/cohorte_1/brief.md). Resultados de los experimentos: [`docs/cohorte_1/evaluation/results/`](docs/cohorte_1/evaluation/results/resumen-r005-2026-11-16.md). Notas de la versión: [`CHANGELOG.md`](CHANGELOG.md) y [`docs/cohorte_1/release.md`](docs/cohorte_1/release.md).

## Qué funciona

- **Entorno:** `scripts/local-up.sh` levanta todo con Docker Compose: PostgreSQL 17 + pgvector (o una base externa como Neon), Liquibase, la API, el servicio `ai/` y su trabajador, Keycloak, la interfaz y Mailpit. Ver [`README.md`](README.md).
- **Base de datos v2.0.x:** 40 tablas de negocio y de IA más 35 de auditoría, con rollback, roles `learner`, `instructor` y `admin`, y usuarios de mínimo privilegio por servicio: `smartmentor_api`, `smartmentor_ai` y `smartmentor_metrics` ([ADR 0019](docs/adr/0019-least-privilege-db-users.md)). Ver [`database/README.md`](database/README.md).
- **API v2** ([contrato](docs/contracts/api-v2.md) y [OpenAPI](docs/contracts/openapi-api.json)): aprendiz, instructor, administrador, piloto, métricas y log del LLM. Las reglas de negocio están en la API, no en la interfaz ([ADR 0017](docs/adr/0017-frontend-rebuilt-from-figma-v3.md)). Hay unas 660 pruebas y la CI está en verde (`audit` incluido).
- **Servicio `ai/`:** trabajos asíncronos con lease y reintentos ([ADR 0010](docs/adr/0010-async-jobs-postgres-pull-ingestion.md)), prompts versionados ([`prompts/catalog.yaml`](prompts/catalog.yaml)), presupuestos en USD y registro de cada llamada. Hace todo esto:
  - estructurar el syllabus;
  - generar el diagnóstico y estimar el nivel;
  - proponer el objetivo;
  - secuenciar la ruta;
  - explicar con RAG;
  - buscar videos;
  - generar bancos de preguntas, y revisarlos y calificarlos con el LLM como juez.

  **Probado con Gemini real el 2026-11-12:** 354 llamadas, US$ 1,83 ([evidencia de F6](docs/cohorte_1/trazabilidad/HOJA_DE_RUTA.md#evidencia-de-f6-2026-11-12)).
- **Interfaz (Streamlit):**
  - las 96 pantallas de Figma v3 tienen página, con pruebas `AppTest`;
  - todas leen la API real; el flujo completo se recorrió en el navegador con el syllabus real, del syllabus al badge (T-032, 2026-11-15 y 16);
  - el login es con Keycloak, la sesión dura 3 h y el token de 5 min se renueva solo.
- **Keycloak v3:** realm versionado sin secretos (`sanitize-realm.py`), OTP obligatorio para el instructor y el administrador, y una prueba de importación en la CI.
- **CI** ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)): Ruff, mypy y pytest en los tres servicios, más Liquibase, el realm, los prompts, la documentación, gitleaks y Trivy.
- **Simulación:** [`scripts/simulate-learners.py`](scripts/simulate-learners.py) recorre por la API cada ruta publicada con 4 aprendices de prueba. Es solo para desarrollo.

## Qué no funciona o no existe todavía

| Pendiente | Detalle |
| --- | --- |
| Piloto con personas | Pasa a la siguiente fase con lo que depende de él: syllabus del curso piloto (T-031), textos legales (T-040), fechas (F-007), despliegue y operación (T-043), usabilidad (T-042), endurecimiento (T-050) y los experimentos E4, E9 y E10. Detalle en «Migrados a la siguiente fase» de [`TRAZABILIDAD.md`](docs/cohorte_1/trazabilidad/TRAZABILIDAD.md) |
| Calibración humana | E3, E6 y E7 se midieron con jueces-agente: los resultados son indicativos. Falta que una persona califique 15 a 20 elementos por experimento y se compare con los jueces |
| Calidad de las preguntas | 26 a 60 % de preguntas válidas según la medición (E3, E3b y E3c), lejos de la meta de 80 % (B-062) |
| Explicación alterna de E7b | El prompt y la tarea de IA existen; falta que la API la pida al reprobar un quiz y la guarde (B-049, siguiente fase) |
| Minutos estimados | La casilla de D2b existe desde el 2026-11-17 (T-057), pero los temas de los cursos ya publicados no tienen minutos, así que la métrica de minutos ahorrados no tiene datos |
| Revisión del equipo en el navegador | 74 de 96 pantallas validadas por agente; falta que el equipo las cruce (G-001) |
| Documento final | En el formato de la maestría; sin responsable en el [checklist](proyecto/cohorte_1/brief.md) |

## Deuda técnica

- **Secretos en el historial de git:** el realm de Keycloak tuvo secretos y llaves versionados antes de `sanitize-realm.py`. Antes de usar datos reales o hacer público el repositorio, hay que rotarlos y limpiar el historial (T-050).
- **Cliente `smartmentor-dev-tools` (flujo password):** existe solo para desarrollo, porque lo usan Swagger, `api/scripts/token.sh`, Postman y el simulador. Hay que quitarlo antes de producción.
- **Keycloak en `start-dev` (HTTP):** para producción hace falta `start` con HTTPS y un nombre de host fijo.
- **Renovación del token por redirección:** Streamlit no expone el refresh token, así que la app repite `st.login`. Al renovar, la app vuelve a su página de inicio.
- **`ai/` corta las llamadas al LLM a los 240 s:** antes eran 120 s y se cortaban los bancos de preguntas (B-013). El lease de los trabajos no se renueva mientras corren: es de 1800 s.
- **`GET /jobs/{id}` siempre devuelve `next_action` en `null`** (B-012): la app vuelve a leer la inscripción.
- **Streamlit 1.67 y los widgets con `key`:** conserva su estado aunque no se dibujen. Se corrigió A3b; otras páginas con pasos y `st.stop()` (nuevo curso, encuesta final, quiz, evaluación final) no tienen prueba que lo cubra (B-009).
- **La cobertura se informa en la CI sin umbral** (T-061).
- **Base compartida en Neon con el plan gratis:** el 2026-11-17 se superó una de sus cuotas mensuales (lo más probable, las 100 CU-horas de cómputo) y la base dejó de aceptar conexiones hasta el siguiente mes de facturación. El `ai-worker` consulta la base todo el tiempo y no deja que Neon se suspenda: hay que apagar el stack cuando no se usa (`scripts/local-up.sh --down`) o pasar a un plan de pago.

## Próximos pasos sugeridos

1. Escribir el documento final con los resultados de `docs/cohorte_1/evaluation/results/` y el brief de la cohorte 1.
2. Calibrar los jueces-agente con una persona en E3, E6 y E7.
3. Para la siguiente fase: endurecimiento (T-050), textos legales, despliegue y el piloto con 15 a 30 aprendices (E4, E9 y E10).
4. Mejorar la calidad de las preguntas (B-062) y construir la explicación alterna de E7b (B-049).

## Traspaso entre cohortes

Checklist del brief:

- [x] **Versión etiquetada en Git (`v1.0-cohorte1`, T-052).** Publicada el 2026-11-21: etiqueta anotada sobre `main` (`8a73b3e`) y [GitHub Release](https://github.com/armandoordonez/smartmentor/releases/tag/v1.0-cohorte1) «Cohorte 1 - Versión 1.0», tras promover `dev` → `stage` ([PR 107](https://github.com/armandoordonez/smartmentor/pull/107)) → `main` ([PR 108](https://github.com/armandoordonez/smartmentor/pull/108)). Las notas están en [`release.md`](docs/cohorte_1/release.md) y [`CHANGELOG.md`](CHANGELOG.md). Las otras etiquetas son internas: `schema-v1-final` (último estado de la base v1).
- [x] **Aplicación funcionando en local.** Todo el trabajo y las pruebas fueron locales, con Docker Compose en Linux y Windows con WSL2: ocho servicios y base local o compartida en Neon. Se levanta con `scripts/local-up.sh` y el [runbook](docs/cohorte_1/runbook-despliegue.md).
- [ ] **Despliegue en un entorno web (QA o producción).** No existe: no hay servidor, hosting ni CD, y la base compartida de Neon es un plan gratuito de desarrollo. Pasa a la siguiente fase junto con el piloto: destino y operador ([ADR 0020](docs/adr/0020-deployment-target.md), T-043) y endurecimiento (T-050).
- [x] Este `HANDOFF.md` actualizado (2026-11-17).
- [x] **Notebook de métricas reproducible.** [`notebooks/metrics_cohort1.ipynb`](notebooks/README.md) se ejecuta de arriba abajo, con datos sintéticos (`synthetic_data.py`) o contra la base real en solo lectura. La evidencia que lo respalda: la prueba «Mago de Oz» ([`design/04-prueba-mago-de-oz/`](design/04-prueba-mago-de-oz/README.md)), los [experimentos E2 a E8](docs/cohorte_1/anexos/D-experimentos.md) con sus [resultados](docs/cohorte_1/evaluation/results/resumen-r005-2026-11-16.md) y el [cuaderno sobre la cohorte de desarrollo](docs/cohorte_1/evaluation/results/metrics-cohort1-2026-11-15.md). **Con datos del piloto no se pudo:** el piloto con usuarios reales pasa a la siguiente fase.
- [ ] Datos anonimizados y anotaciones en `data/`.
- [x] **Accesos transferidos.** Qué se entrega y dónde está cada cosa:
  - **GitHub:** el repositorio `armandoordonez/smartmentor`; el dueño administra los permisos y las promociones a `stage` y `main`.
  - **Despliegue:** local con Docker Compose; no hay cuentas de hosting. La base compartida de Neon es un proyecto del plan gratuito, a nombre del dueño (sus contraseñas se piden por un canal privado).
  - **Configuración (`.env`):** [`.env.example`](.env.example) trae los valores de desarrollo y de prueba (usuarios, modelos, topes de gasto, correos de prueba). Quedan vacíos, a propósito, las contraseñas, los secretos de Keycloak y de la base y las claves de API: `scripts/gen-secrets.sh` genera los secretos.
  - **Claves de API:** `GEMINI_API_KEY` y `YOUTUBE_API_KEY` no se versionan. Quien continúe pone las suyas en el `.env`.
  - **Figma:** archivo maestro v3 (`atp2fZdSolEoaww3n9jRLg`), con acceso desde la cuenta del dueño.
  - **Keycloak:** el realm versionado no trae secretos ni usuarios; `scripts/local-up.sh` crea los usuarios de prueba y el administrador se crea con `--with-admin`.
- [x] Brief actualizado con métricas y lecciones aprendidas ([brief de la cohorte 1](proyecto/cohorte_1/brief.md)).

Para pasar los datos de un PC a otro: `database/scripts/backup.sh` en el origen, copiar los `.dump` y `restore.sh` en el destino (aplicación y Keycloak). El `.env` no viaja con git y tiene credenciales: cópialo por un canal seguro o regenéralo con `scripts/gen-secrets.sh`.
