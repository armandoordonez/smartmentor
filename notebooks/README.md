# notebooks/

Análisis y cálculo de métricas, reproducibles por cada cohorte.

| Archivo | Para qué sirve |
| --- | --- |
| `metrics_cohort1.ipynb` | Calcula todas las métricas del brief con sus gráficos. Se ejecuta de arriba abajo |
| `metrics_data.py` | Consultas de solo lectura a la base (nombres de la sección 5.2.1 del plan) |
| `synthetic_data.py` | Datos sintéticos con semilla para el modo de demostración |
| `requirements.txt` | Dependencias con versión fija (Python 3.12) |

Las funciones de cálculo no viven aquí: están en `ai/app/domain/metrics.py` (solo biblioteca
estándar, con pruebas). Cada métrica, su fórmula y su meta: `docs/evaluation/metrics.md`.

## Modo de demostración (sin base)

El cuaderno guardado en el repositorio se ejecutó así. Los números son sintéticos, **no resultados del
piloto**. En un contenedor desechable, desde la raíz del repositorio:

```bash
docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp -v "$PWD:/repo" -w /repo python:3.12-slim sh -c '
  pip install -q --user -r notebooks/requirements.txt &&
  export PATH=$HOME/.local/bin:$PATH && cd notebooks &&
  jupyter nbconvert --to notebook --execute --inplace metrics_cohort1.ipynb'
```

Dos ejecuciones seguidas producen salidas idénticas (semilla fija).

## Cohorte real

1. Pida al administrador de la base un usuario **de solo lectura** (por ejemplo, un rol con `SELECT`
   sobre las tablas de `metrics_data.py`).
2. Exporte la URL en el entorno de su terminal, nunca en el cuaderno ni en un archivo versionado:
   `export METRICS_DATABASE_URL='postgresql+psycopg://<usuario>:<clave>@<host>:<puerto>/<base>'`.
3. Ejecute el cuaderno como arriba, pasando `-e METRICS_DATABASE_URL` al contenedor (o
   `--network` hacia la base).
4. El cuaderno solo imprime agregados. Aun así, **no versione una ejecución contra la base real**:
   limpie las salidas con `jupyter nbconvert --clear-output --inplace metrics_cohort1.ipynb` y
   publique las cifras en el informe, no el cuaderno con salidas.

`FORCE_SYNTHETIC = True` en la celda de parámetros fuerza el modo de demostración aunque exista la
variable.
