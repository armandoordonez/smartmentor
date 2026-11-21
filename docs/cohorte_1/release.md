# Cohorte 1

Texto del GitHub Release de `v1.0-cohorte1`, con el formato de la sección 13 de [`GIT_VERSIONING_STRATEGY.md`](../../GIT_VERSIONING_STRATEGY.md). Al final están los pasos para publicarlo (T-052).

## Versión

`v1.0-cohorte1` · Cohorte 1 - Versión 1.0 · 2026-11-17

## Descripción

SmartMentor genera rutas de aprendizaje personalizadas a partir de un syllabus. El instructor carga el syllabus y, si quiere, apuntes o lecturas. La IA extrae los temas y sus prerrequisitos, y el instructor los revisa y publica. Al publicar, la IA genera las explicaciones con RAG, busca videos y crea los bancos de preguntas. El aprendiz hace un diagnóstico, recibe una ruta con los temas que necesita, estudia, presenta quizzes y la evaluación final, y obtiene un badge.

Esta versión cierra la cohorte 1. El flujo completo funciona de punta a punta con el LLM real (Gemini), en un stack de ocho servicios con Docker Compose y una base compartida en Neon. El detalle de lo planteado frente a lo logrado está en el [brief de la cohorte 1](../../proyecto/cohorte_1/brief.md), y la lista de cambios en el [CHANGELOG](../../CHANGELOG.md).

## Funcionalidades

- **Instructor:** carga del syllabus (PDF o texto) con apuntes y lecturas, extracción de temas y prerrequisitos con IA, revisión del grafo de temas (D2 y D2d), publicación, revisión de explicaciones, videos y preguntas (D5), ruta y avance de los aprendices (D3 y D4), intentos extra, anotación de preguntas (D5b) y calificación humana (D5c).
- **Aprendiz:** catálogo, perfil y hoja de vida, diagnóstico con nivel por tema, objetivo propuesto por la IA y editable, ruta personalizada, tema con explicación y videos, quiz con respuesta corta calificada por la IA, evaluación final, badge, progreso, logros y encuesta final.
- **Administrador:** usuarios y roles, log del LLM y costos, métricas globales, cursos, rutas e inscripciones, y catálogo de prompts.
- **IA:** trabajos asíncronos, RAG con citas sobre syllabus, apuntes y lecturas, recomendador de videos de YouTube, bancos de preguntas alineados con Bloom y el LLM como juez de respuestas cortas.
- **Seguridad y operación:** Keycloak con roles y OTP para el staff, usuarios de base de datos de mínimo privilegio, CI con pruebas, Liquibase, realm, prompts, documentación, gitleaks y Trivy.
- **Interfaz:** las 96 pantallas del prototipo de Figma v3 en Streamlit.

## Métricas

Los experimentos se hicieron con **jueces-agente** (Claude Opus y Sonnet), a ciegas y sobre datos de prueba. **Los jueces no son expertos humanos: los resultados son indicativos.** Resumen en [`resumen-r005-2026-11-16.md`](evaluation/results/resumen-r005-2026-11-16.md).

| Experimento | Resultado | Meta | Cumple |
| --- | --- | --- | --- |
| E2 · Estructuración del syllabus | F1 de temas 1,000; F1 de prerrequisitos 0,694 (flash-lite) y 0,578 (flash) | F1 ≥ 0,85 | ✔ temas · ✖ prerrequisitos |
| E3 · Preguntas válidas | 28,8 % válidas con ambos jueces; κ 0,704 | ≥ 80 % y κ ≥ 0,6 | ✖ calidad · ✔ acuerdo |
| E3b y E3c · Tras B-062 | De 32,5 % a 60,0 % válidas (v2); claves erróneas de 4/4 a 0/1 (v3) | ≥ 80 % | ✖ (mejora) |
| E5 · Fidelidad del RAG | Fidelidad media 0,889 (tema ETL/ELT: 0,667); la comparación con lecturas no fue concluyente | ≥ 0,8 | ✔ media |
| E6 · Videos por tema | P@3 0,718; κ 0,766 | P@3 ≥ 0,7 | ✔ |
| E7 · Juez de respuestas cortas | QWK 0,998, con una muestra polarizada | QWK ≥ 0,6 | ✔ con salvedad |
| E8 · Latencia y costo | p95 de 2,1 s al calificar y 9,2 s al cerrar el diagnóstico; las tareas de generación superan 20 s; JSON inválido 0,8 %; costo del log US$ 1,84 | p95 < 20 s y JSON < 2 % | ✔ lo que espera el aprendiz · ✖ generación |

**Pasan a la siguiente fase:** E4 (validez del diagnóstico), E9 (prueba con 5 o 6 empleados) y E10 (revisión con la organización), junto con el piloto con usuarios reales, y la calibración humana de los jueces.

## Validaciones

- **Tests: PASS.** Interfaz 1083; API 526 unitarias más las de integración, que corren con PostgreSQL en la CI; servicio de IA 563 y 13 omitidas.
- **Prompt schemas: PASS.** Revisión `prompts (hashes y esquemas exportados)` de la CI.
- **CI: PASS.** Las 15 revisiones de GitHub Actions en el último PR fusionado.
- Ruff y mypy estricto sin errores en los tres servicios.

## Informe

- Resultados de los experimentos: [`docs/cohorte_1/evaluation/results/`](evaluation/results/resumen-r005-2026-11-16.md).
- Métricas de la cohorte 1 con la base real: [`metrics-cohort1-2026-11-15.md`](evaluation/results/metrics-cohort1-2026-11-15.md) y el cuaderno [`notebooks/metrics_cohort1.ipynb`](../../notebooks/metrics_cohort1.ipynb).
- Brief de la cohorte 1: [`proyecto/cohorte_1/brief.md`](../../proyecto/cohorte_1/brief.md).
- Seguimiento: [`docs/cohorte_1/trazabilidad/TRAZABILIDAD.md`](trazabilidad/TRAZABILIDAD.md).

## Pasos para publicarlo (dueño del repositorio)

Según la [estrategia de versiones](../../GIT_VERSIONING_STRATEGY.md), la etiqueta va sobre `main` y las promociones las hace el dueño del repositorio:

1. Abrir y fusionar un PR de `dev` a `stage`.
2. Abrir y fusionar un PR de `stage` a `main`.
3. Crear la etiqueta sobre `main`:

   ```bash
   git checkout main
   git pull origin main
   git tag -a v1.0-cohorte1 -m "Cierre cohorte 1"
   git push origin v1.0-cohorte1
   ```

4. Crear el GitHub Release con este texto, sin la sección «Pasos para publicarlo»:

   ```bash
   gh release create v1.0-cohorte1 --title "Cohorte 1 - Versión 1.0" --notes-file docs/cohorte_1/release.md
   ```

5. En `docs/cohorte_1/trazabilidad/TRAZABILIDAD.md`, pasar T-052 a «Realizado».
