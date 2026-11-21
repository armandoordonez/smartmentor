# E2 · Estructuración del syllabus: procedimiento

Pregunta del experimento: ¿qué tanto de los temas y de los prerrequisitos de un syllabus extrae bien cada modelo? La métrica es la de [`metrics.md`](metrics.md) (sección «Estructuración del syllabus»): precisión, recall y F1 con `set_f1`, meta de F1 ≥ 0,85.

## Por qué no se usa la API

`POST /courses/{id}/extractions` no deja elegir el modelo, las repeticiones con el mismo texto salen de la caché (`ai_generation_cache`) y re-extraer reemplaza los temas del curso. Por eso se usa `ai/eval/syllabus_experiment.py`, que llama a `EvalWorld.structure_syllabus` en **un proceso nuevo por repetición** (caché en memoria vacía) y no toca la base, la API ni los contenedores.

## Diseño

| Aspecto | Valor |
| --- | --- |
| Modelos | `gemini-3.8-flash` y `gemini-3.5-flash-lite` (ambos con precio en `ai/config/prices.yaml`) |
| Repeticiones | 3 por modelo y por syllabus |
| Costo | Unos US$ 0,10 por 12 extracciones (2 syllabus × 2 modelos × 3 repeticiones) |
| Proveedor | Solo `AI_LLM_PROVIDER=gemini`, como el arnés actual |

`AI_LLM_MODEL_DEFAULT` se fija solo en el entorno de cada subproceso. La clave llega por el entorno y nunca se imprime ni se guarda. Cada repetición se rechaza si `meta.from_cache` no es `false`.

## 1. Extraer

El syllabus debe ser texto o Markdown (si es PDF, pasarlo antes a texto, por ejemplo con `pdftotext -layout`). **El nombre del archivo sin extensión es la clave del curso** (`course_key` del oro). Desde `ai/`, con el entorno del servicio cargado (`AI_EVAL_LIVE=1`, `AI_LLM_PROVIDER=gemini`, la clave y los topes de presupuesto):

```bash
for m in gemini-3.8-flash gemini-3.5-flash-lite; do
  python -m eval.syllabus_experiment run --syllabus ~/e2/curso_a.md --model "$m" --repetitions 3 --out ~/e2/runs
done
```

Deja `~/e2/runs/<curso>/<modelo>/rep<N>.json` con la salida completa (`syllabus`, con `meta.model` y `meta.from_cache`), el costo (`cost_usd`) y la latencia (`latency_ms`).

## 2. Oro a ciegas

Un agente-instructor, **sin ver ninguna extracción**, lee el syllabus y escribe el oro como **nombres**, no ids (los ids `snake_case` los inventa el LLM y un oro a ciegas casi nunca los repite):

```bash
python -m eval.syllabus_experiment export-gold-sheet --course-key curso_a --course-key curso_b --out ~/e2/oro.csv
```

Formato del CSV, sin datos personales:

| Columna | Contenido |
| --- | --- |
| `course_key` | Clave del curso (nombre del archivo del syllabus sin extensión) |
| `kind` | `topic` o `prerequisite` |
| `name` | Nombre del tema, o del prerrequisito cuando `kind` es `prerequisite` |
| `prerequisite_of` | Solo para `prerequisite`: nombre del tema que lo requiere |

Un tema por fila `topic`, y un prerrequisito por fila `prerequisite`; ambos nombres deben existir como filas `topic`. Las filas sin `name` se ignoran.

## 3. Emparejar (juez)

```bash
python -m eval.syllabus_experiment export-matching-sheet --gold ~/e2/oro.csv --run-dir ~/e2/runs --out ~/e2/emparejar.json
```

La hoja trae, por extracción, los temas extraídos (`id` y nombre), los nombres del oro y un `mapping` con cada `id` en `null`. El juez completa `mapping[<id>]` con el nombre **exacto** del tema de oro equivalente, o lo deja en `null`. Juzga por el sentido del nombre. Dos extraídos pueden apuntar al mismo tema de oro (cuentan una vez). Un tema en `null` cuenta como predicho sin pareja y baja la precisión.

## 4. Calcular

```bash
python -m eval.syllabus_experiment match --gold ~/e2/oro.csv --run-dir ~/e2/runs --mapping ~/e2/emparejar.json --out ~/e2/resultado.md
```

Cada tema extraído se lleva a su nombre de oro y se comparan los conjuntos de temas y de pares `(prerrequisito, tema)`. El informe da precisión, recall y F1 por repetición, la media y el rango por curso y modelo, el total por modelo, los temas sin emparejar, el costo y la latencia. Publicar el resultado en `docs/cohorte_1/evaluation/results/e2-<fecha>.md`.

## Lo que el experimento no dice

- El oro lo escribe un agente a ciegas, no un instructor de la materia: es una referencia razonable, no la verdad.
- El emparejamiento lo hace un juez por nombre; su criterio puede ser más o menos estricto y mueve el F1.
- Con 2 syllabus y 3 repeticiones por modelo las cifras son **indicativas**, no una comparación estadística.
