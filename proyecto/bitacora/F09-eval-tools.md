# Bitácora F09 · `feature/evaluation-pilot` (herramientas de evaluación)

Fase 9, Ola 2, agente `eval-tools`: funciones de métricas, cuaderno reproducible, documentación de
métricas y estructura del conjunto de oro. No incluye anotaciones, piloto ni usabilidad (eso lo
hacen personas).

## Hecho

Rama `feature/evaluation-pilot`, creada desde `origin/dev` (commit `8bb1828`).

- `ai/app/domain/metrics.py`: 25 funciones y 4 clases de resultado, solo biblioteca estándar. Kappa de
  Cohen, QWK, F1 de conjuntos, P@k, nDCG@k, Hake (por persona y media), SUS, d de Cohen con IC
  bootstrap con semilla, AUC-ROC, dificultad, punto-biserial y discriminación corregida, % de
  preguntas válidas, percentil y p50/p95. Commit `4f52127`.
- `ai/tests/unit/test_metrics.py`: 56 pruebas contra valores calculados a mano (kappa 0,5; QWK 0,5;
  F1 4/7; nDCG con log2; Hake 0,5; SUS 77,5; d = 2; AUC 0,75; punto-biserial 2/√5; p95 = 4,8) y casos
  límite (vacío, largos distintos, división por cero, desacuerdo total, una sola clase, `pre = 100`).
- `notebooks/metrics_cohort1.ipynb` (32 celdas, 14 gráficos, 29 métricas en el tablero final),
  `notebooks/metrics_data.py` (consultas de solo lectura), `notebooks/synthetic_data.py` (semilla
  `20260507`), `notebooks/requirements.txt` (versiones fijas) y `notebooks/README.md`.
- `docs/evaluation/metrics.md`: función, fórmula, tabla, meta e interpretación de cada métrica.
- `data/eval/README.md`, `data/eval/gold/README.md` y plantillas CSV vacías (solo encabezados) para
  syllabus, anotación de ítems, calificación humana y pertinencia de videos.

## Desviaciones frente al plan o al brief

- Primera entrega con nombres del plan 5.2.1 sin probar; **corregida tras la rama `feature/database-v2-rebase`**
  (commit 0745800): `path_steps.first_attempt_passed` no existe (el primer intento sale de
  `assessment_attempts`, `attempt_number = 1`), la columna es `step_order` y el estado aprobado `passed`; los
  estados reales de un paso son `skipped`, `blocked`, `pending`, `in_progress`, `passed`,
  `attempts_exhausted` y `on_hold` (no existe `abandoned`: el abandono se toma de
  `enrollments.status = 'abandoned'`); `llm_call_logs.status` usa `success` (no `succeeded`).
  `diagnostics.level_by_topic` y `survey_responses.likert` son `jsonb` libres: quedan `SUPUESTO`
  con validación defensiva (`UnexpectedShapeError`).
- **Tiempo en tarea** (`interaction_events`) no se calcula: el plan no define los tipos de evento que lo
  permiten. RAGAS completo queda apagado (`SHOW_RAGAS`) porque exige LLM y red.
- Brief: «dificultad y discriminación con correlación punto-biserial»; se usa la versión **corregida**
  (total sin el ítem) para no inflar la correlación. Es una precisión, no un cambio de meta.

## Decisiones

- **Funciones puras sin dependencias** (en lugar de numpy/scipy) porque `ai/pyproject.toml` no se edita
  en esta rama y el servicio no debe cargar bibliotecas pesadas. Costo: AUC y bootstrap son O(n²) y
  O(n·B), irrelevantes con 15 a 30 personas.
- **Valores límite**: kappa con una única etiqueta común = 1,0; F1 con dos vacíos = 1,0; Hake con
  `pre = 100` = `None` (se excluye del promedio, no se inventa); AUC con una clase y entradas vacías =
  `ValueError`; punto-biserial sin variación = 0,0. Documentados en cada docstring y en `metrics.md`.
- **Pregunta válida** = todos los expertos la marcan válida (criterio conservador). **Relevancia de
  video binaria** = mayoría de jueces (empate relevante); nDCG usa la proporción de jueces.
- **QWK**: los puntajes 0 a 100 se discretizan a 5 niveles (`QWK_LEVELS = 4`), parámetro de la primera
  celda. Solo la muestra `random` cuenta para la meta.
- **El cuaderno guardado se ejecuta con datos sintéticos** y queda con salidas (gráficos incluidos) para
  que se vea el resultado sin ejecutar; contra la base real las salidas se limpian y no se versionan.
- La raíz del repositorio se busca hacia arriba desde el directorio actual (`ai/app/domain/metrics.py`),
  así corre desde la raíz o desde `notebooks/`.

## Problemas y lecciones

- `nbconvert` ejecuta el kernel en la carpeta del cuaderno, no en la del comando: la primera corrida falló al
  importar `app`. Se ejecuta `--inplace` desde `notebooks/` y se busca la raíz por contenido.
- Con `matplotlib.use("Agg")` el cuaderno se guardaba **sin gráficos** (0 imágenes); se quitó para usar el
  backend en línea de Jupyter.
- `met is True` falla con `numpy.bool_`: tres filas del tablero salían grises (solo reportar) siendo
  métricas con meta. Se corrigió con `bool(met)`.
- Los datos sintéticos de psicometría salen con mediana de discriminación baja (0,09) y varias metas en
  rojo: es deliberado para que el tablero muestre los tres estados.

## Métricas

| Comprobación | Resultado |
| --- | --- |
| `ruff check` sobre `metrics.py` y su prueba (config de `ai/pyproject.toml`, imagen uv 0.9.30) | Sin avisos |
| `ruff format --check` | Sin cambios |
| `mypy` estricto sobre ambos archivos | Sin errores |
| `pytest ai/tests/unit/test_metrics.py` | 56 pasadas en 0,15 s |
| `ruff check` sobre `notebooks/*.py` | Sin avisos |
| Cuaderno con `nbconvert --execute` (python:3.12-slim, desechable, versiones de `requirements.txt`) | 0 errores; 14 gráficos; 29 métricas |
| Consultas contra el esquema real (PostgreSQL pgvector 0.8.7-pg17 desechable, Liquibase del repo con los 51 changesets de `v2.0.0`, datos mínimos) | Las 11 consultas corren como `smartmentor_metrics` (solo lectura) y devuelven las filas esperadas (primer intento de `path_steps` verificado: paso aprobado con primer intento fallido); con `level_by_topic` como arreglo falla con `UnexpectedShapeError`; `SELECT users` y `UPDATE enrollments` son rechazados |
| Reproducibilidad | Dos ejecuciones seguidas con salidas idénticas (mismo hash de todas las salidas, imágenes incluidas) |
| Secretos en el cuaderno | 0 coincidencias de `postgres://`, `password`, `secret`, `api_key` |
| Líneas | `metrics.py` 484, `test_metrics.py` 288, `synthetic_data.py` 287 |

Resultados del tablero con datos **sintéticos** (no son del piloto): F1 temas 0,833, F1 prerrequisitos
0,909, % válidas 71,3, κ 0,726, P@3 0,80, QWK 0,846, AUC 0,898, p95 12,6 s, JSON inválido 1,0 %, SUS 70,6,
g = 0,373, d = 0,06 con IC 95 % [-0,73, 1,18].

## Impacto en el brief

- Sección «Métricas de los estudiantes», psicometría: aclarar que la discriminación es la punto-biserial
  corregida (sin el ítem) y que se exige un mínimo de 10 respuestas por ítem.
- «Calidad de preguntas»: precisar que una pregunta es válida solo si **todos** los expertos la aprueban.
- «Calificación automática»: indicar que el QWK usa la muestra aleatoria y reporta aparte las solicitudes
  del aprendiz, y que los puntajes 0 a 100 se discretizan a 5 niveles.
- Nota de límites: con 15 a 30 participantes se reporta el n y los intervalos, no «significancia».

## Cambios pedidos a archivos compartidos

- Hecho por `database`: rol `smartmentor_metrics` y changeset `v2.0.0-049`. Falta que `infra` agregue
  `METRICS_DATABASE_USER` y `METRICS_DATABASE_PASSWORD` a `.env.example` y al servicio `postgres`.
- `ai/pyproject.toml`: ninguno (solo biblioteca estándar). Para ejecutar el cuaderno en CI haría falta un
  trabajo aparte con `notebooks/requirements.txt` (modo sintético, sin base).
- Confirmar con el dueño de la API: `path_steps.first_attempt_passed` (o cómo derivarlo), el tipo de
  evento de `interaction_events` para tiempo en tarea y las claves de `survey_responses.likert`.
