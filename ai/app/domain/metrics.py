"""Métricas de evaluación del brief como funciones puras.

Solo usa la biblioteca estándar de Python: lo importan tanto el servicio ``ai/`` como el cuaderno
``notebooks/metrics_cohort1.ipynb``. Ninguna función lee la base de datos ni cambia sus entradas.

Convenciones comunes:

* Una entrada vacía o de largos distintos lanza ``ValueError`` cuando la métrica no tiene sentido.
* Una división por cero que tiene un valor límite natural devuelve ese valor y se documenta en la
  función; las que no lo tienen devuelven ``None`` o lanzan ``ValueError`` (se indica en cada una).
"""

from __future__ import annotations

import math
import random
from collections import Counter
from collections.abc import Collection, Hashable, Sequence
from dataclasses import dataclass

__all__ = [
    "EffectSize",
    "LatencyPercentiles",
    "SetScores",
    "auc_roc",
    "cohen_kappa",
    "cohens_d",
    "cohens_d_with_ci",
    "hake_gain",
    "item_difficulty",
    "item_discrimination",
    "latency_percentiles",
    "mean_hake_gain",
    "ndcg_at_k",
    "percentile",
    "point_biserial",
    "precision_at_k",
    "quadratic_weighted_kappa",
    "set_f1",
    "sus_score",
    "valid_question_rate",
]

SUS_ITEM_COUNT = 10


def _check_paired(first: Sequence[object], second: Sequence[object]) -> None:
    """Valida que dos series pareadas no estén vacías y tengan el mismo largo."""
    if len(first) != len(second):
        raise ValueError(f"series de largo distinto: {len(first)} y {len(second)}")
    if not first:
        raise ValueError("la serie no puede estar vacía")


# ---------------------------------------------------------------------------------------------
# Acuerdo entre evaluadores
# ---------------------------------------------------------------------------------------------


def cohen_kappa(rater_a: Sequence[Hashable], rater_b: Sequence[Hashable]) -> float:
    """Kappa de Cohen entre dos evaluadores con etiquetas nominales.

    ``kappa = (po - pe) / (1 - pe)``, con ``po`` el acuerdo observado y ``pe`` el esperado por
    azar según las frecuencias marginales. Si ``pe == 1`` (ambos evaluadores usaron una única
    etiqueta y es la misma) devuelve ``1.0``: acuerdo total sin variabilidad.

    Raises:
        ValueError: si las series están vacías o tienen largo distinto.
    """
    _check_paired(rater_a, rater_b)
    total = len(rater_a)
    observed = sum(1 for a, b in zip(rater_a, rater_b, strict=True) if a == b) / total
    count_a = Counter(rater_a)
    count_b = Counter(rater_b)
    expected = sum(count_a[label] * count_b.get(label, 0) for label in count_a) / (total * total)
    if math.isclose(expected, 1.0):
        return 1.0
    return (observed - expected) / (1.0 - expected)


def quadratic_weighted_kappa(
    rater_a: Sequence[int],
    rater_b: Sequence[int],
    min_rating: int | None = None,
    max_rating: int | None = None,
) -> float:
    """Kappa ponderado cuadrático (QWK) para puntajes ordinales enteros.

    ``QWK = 1 - sum(w * O) / sum(w * E)`` con ``w_ij = (i - j)^2 / (K - 1)^2``, ``O`` la matriz
    de conteos observados y ``E`` la esperada por azar (producto de marginales). Si
    ``min_rating``/``max_rating`` no se indican, se toman de los datos. Cuando todos los puntajes
    de ambos evaluadores son el mismo valor (denominador cero) devuelve ``1.0``.

    Raises:
        ValueError: series vacías o de largo distinto, o puntajes fuera del rango dado.
    """
    _check_paired(rater_a, rater_b)
    low = min(min(rater_a), min(rater_b)) if min_rating is None else min_rating
    high = max(max(rater_a), max(rater_b)) if max_rating is None else max_rating
    if high < low:
        raise ValueError("max_rating debe ser mayor o igual que min_rating")
    for score in (*rater_a, *rater_b):
        if not low <= score <= high:
            raise ValueError(f"puntaje {score} fuera del rango [{low}, {high}]")
    size = high - low + 1
    total = len(rater_a)
    observed = [[0.0] * size for _ in range(size)]
    for a, b in zip(rater_a, rater_b, strict=True):
        observed[a - low][b - low] += 1.0
    hist_a = [sum(row) for row in observed]
    hist_b = [sum(observed[i][j] for i in range(size)) for j in range(size)]
    denominator_scale = float((size - 1) ** 2) if size > 1 else 1.0
    numerator = 0.0
    denominator = 0.0
    for i in range(size):
        for j in range(size):
            weight = (i - j) ** 2 / denominator_scale
            numerator += weight * observed[i][j]
            denominator += weight * hist_a[i] * hist_b[j] / total
    if denominator == 0.0:
        return 1.0
    return 1.0 - numerator / denominator


# ---------------------------------------------------------------------------------------------
# Extracción del syllabus
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class SetScores:
    """Precisión, recall y F1 de una comparación de conjuntos."""

    precision: float
    recall: float
    f1: float


def set_f1(predicted: Collection[Hashable], gold: Collection[Hashable]) -> SetScores:
    """Precisión, recall y F1 entre un conjunto predicho y uno de referencia.

    Sirve para temas (conjunto de ids) y para prerrequisitos (conjunto de pares
    ``(prerrequisito, tema)``). Los duplicados se ignoran. Si ambos conjuntos están vacíos el
    acuerdo es total (``1.0`` en las tres); si solo uno está vacío todo vale ``0.0``.
    """
    predicted_set = set(predicted)
    gold_set = set(gold)
    if not predicted_set and not gold_set:
        return SetScores(1.0, 1.0, 1.0)
    true_positives = len(predicted_set & gold_set)
    precision = true_positives / len(predicted_set) if predicted_set else 0.0
    recall = true_positives / len(gold_set) if gold_set else 0.0
    f1 = 0.0 if precision + recall == 0.0 else 2 * precision * recall / (precision + recall)
    return SetScores(precision, recall, f1)


# ---------------------------------------------------------------------------------------------
# Recomendación (ranking)
# ---------------------------------------------------------------------------------------------


def precision_at_k(relevances: Sequence[int | bool], k: int) -> float:
    """Precision@k de una lista ordenada por ranking (``relevances[0]`` es el primero).

    Es la cantidad de relevantes en las primeras ``k`` posiciones dividida entre ``k``, aunque la
    lista tenga menos de ``k`` elementos (los que faltan cuentan como no relevantes).

    Raises:
        ValueError: si ``k < 1``.
    """
    if k < 1:
        raise ValueError("k debe ser al menos 1")
    return sum(1 for rel in relevances[:k] if rel) / k


def _dcg(gains: Sequence[float], k: int) -> float:
    return sum(gain / math.log2(position + 2) for position, gain in enumerate(gains[:k]))


def ndcg_at_k(
    relevances: Sequence[float],
    k: int,
    ideal_relevances: Sequence[float] | None = None,
) -> float:
    """nDCG@k con ganancia lineal ``rel / log2(posición + 1)``.

    ``relevances`` va en el orden del ranking. El orden ideal sale de ``ideal_relevances`` (todos
    los candidatos juzgados) o, si no se da, de ordenar ``relevances`` de mayor a menor. Si el DCG
    ideal es cero (ningún candidato relevante) devuelve ``0.0``.

    Raises:
        ValueError: si ``k < 1``.
    """
    if k < 1:
        raise ValueError("k debe ser al menos 1")
    pool = relevances if ideal_relevances is None else ideal_relevances
    ideal = _dcg(sorted(pool, reverse=True), k)
    if ideal == 0.0:
        return 0.0
    return _dcg(relevances, k) / ideal


# ---------------------------------------------------------------------------------------------
# Aprendizaje y efecto
# ---------------------------------------------------------------------------------------------


def hake_gain(pre: float, post: float, max_score: float = 100.0) -> float | None:
    """Ganancia normalizada de Hake de una persona: ``(post - pre) / (max - pre)``.

    Devuelve ``None`` si ``pre >= max_score`` (no hay margen de mejora y la división sería por
    cero), para que quede fuera del promedio en lugar de inventar un valor.

    Raises:
        ValueError: si algún puntaje está fuera de ``[0, max_score]`` o ``max_score <= 0``.
    """
    if max_score <= 0:
        raise ValueError("max_score debe ser positivo")
    if not (0 <= pre <= max_score and 0 <= post <= max_score):
        raise ValueError("pre y post deben estar entre 0 y max_score")
    if pre >= max_score:
        return None
    return (post - pre) / (max_score - pre)


def mean_hake_gain(
    pairs: Sequence[tuple[float, float]], max_score: float = 100.0
) -> tuple[float, int]:
    """Promedio de la ganancia de Hake por persona (primero se calcula, luego se promedia).

    Devuelve ``(media, n)`` con ``n`` las personas con ganancia definida (``pre < max_score``).

    Raises:
        ValueError: si ninguna persona tiene ganancia definida.
    """
    gains = [g for pre, post in pairs if (g := hake_gain(pre, post, max_score)) is not None]
    if not gains:
        raise ValueError("ninguna persona tiene ganancia definida")
    return sum(gains) / len(gains), len(gains)


def sus_score(responses: Sequence[int]) -> float:
    """Puntaje SUS (0 a 100) de un cuestionario de 10 ítems con escala de 1 a 5.

    Los ítems impares (posición 1, 3, ...) aportan ``respuesta - 1``; los pares aportan
    ``5 - respuesta``. La suma se multiplica por 2,5.

    Raises:
        ValueError: si no son exactamente 10 respuestas o alguna está fuera de 1 a 5.
    """
    if len(responses) != SUS_ITEM_COUNT:
        raise ValueError(f"SUS requiere {SUS_ITEM_COUNT} respuestas, llegaron {len(responses)}")
    if any(not 1 <= r <= 5 for r in responses):
        raise ValueError("las respuestas SUS deben estar entre 1 y 5")
    total = sum((r - 1) if index % 2 == 0 else (5 - r) for index, r in enumerate(responses))
    return total * 2.5


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values)


def _sample_variance(values: Sequence[float]) -> float:
    mean = _mean(values)
    return sum((v - mean) ** 2 for v in values) / (len(values) - 1)


def cohens_d(treatment: Sequence[float], control: Sequence[float]) -> float:
    """d de Cohen con desviación estándar combinada: ``(m_t - m_c) / s_p``.

    Si ambos grupos tienen varianza cero: ``0.0`` si las medias son iguales y ``±inf`` si no.

    Raises:
        ValueError: si algún grupo tiene menos de 2 observaciones.
    """
    if len(treatment) < 2 or len(control) < 2:
        raise ValueError("cada grupo necesita al menos 2 observaciones")
    n_t, n_c = len(treatment), len(control)
    weighted = (n_t - 1) * _sample_variance(treatment) + (n_c - 1) * _sample_variance(control)
    pooled_var = weighted / (n_t + n_c - 2)
    difference = _mean(treatment) - _mean(control)
    if pooled_var == 0.0:
        return 0.0 if difference == 0.0 else math.copysign(math.inf, difference)
    return difference / math.sqrt(pooled_var)


@dataclass(frozen=True)
class EffectSize:
    """d de Cohen con su intervalo de confianza bootstrap."""

    d: float
    ci_low: float
    ci_high: float
    confidence: float
    n_bootstrap: int


def cohens_d_with_ci(
    treatment: Sequence[float],
    control: Sequence[float],
    *,
    confidence: float = 0.95,
    n_bootstrap: int = 2000,
    seed: int = 20260,
) -> EffectSize:
    """d de Cohen con intervalo percentil por bootstrap (remuestreo por grupo, con semilla).

    Es determinista para una misma semilla. Se descartan los remuestreos con d no finito (varianza
    cero en ambos grupos).

    Raises:
        ValueError: grupos con menos de 2 datos, ``confidence`` fuera de (0, 1), ``n_bootstrap``
            menor que 100 o ningún remuestreo con d finito.
    """
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence debe estar entre 0 y 1")
    if n_bootstrap < 100:
        raise ValueError("n_bootstrap debe ser al menos 100")
    point = cohens_d(treatment, control)
    rng = random.Random(seed)  # noqa: S311 - remuestreo estadístico, no criptografía
    samples: list[float] = []
    for _ in range(n_bootstrap):
        t_sample = rng.choices(treatment, k=len(treatment))
        c_sample = rng.choices(control, k=len(control))
        value = cohens_d(t_sample, c_sample)
        if math.isfinite(value):
            samples.append(value)
    if not samples:
        raise ValueError("ningún remuestreo produjo un d finito")
    alpha = (1.0 - confidence) / 2.0
    return EffectSize(
        d=point,
        ci_low=percentile(samples, alpha * 100.0),
        ci_high=percentile(samples, (1.0 - alpha) * 100.0),
        confidence=confidence,
        n_bootstrap=len(samples),
    )


# ---------------------------------------------------------------------------------------------
# Diagnóstico y psicometría
# ---------------------------------------------------------------------------------------------


def auc_roc(scores: Sequence[float], labels: Sequence[int | bool]) -> float:
    """AUC-ROC por la estadística de Mann-Whitney, con empates a medio punto.

    ``labels`` es verdadero para la clase positiva (por ejemplo, aprobó el quiz al primer
    intento) y ``scores`` el puntaje del diagnóstico.

    Raises:
        ValueError: series vacías o de largo distinto, o falta alguna de las dos clases.
    """
    _check_paired(scores, labels)
    positives = [s for s, y in zip(scores, labels, strict=True) if y]
    negatives = [s for s, y in zip(scores, labels, strict=True) if not y]
    if not positives or not negatives:
        raise ValueError("el AUC requiere al menos un positivo y un negativo")
    wins = 0.0
    for p in positives:
        for n in negatives:
            if p > n:
                wins += 1.0
            elif p == n:
                wins += 0.5
    return wins / (len(positives) * len(negatives))


def item_difficulty(correct: Sequence[int | bool]) -> float:
    """Índice de dificultad de un ítem: proporción de respuestas correctas (0 a 1).

    Raises:
        ValueError: si no hay respuestas.
    """
    if not correct:
        raise ValueError("el ítem no tiene respuestas")
    return sum(1 for c in correct if c) / len(correct)


def point_biserial(binary: Sequence[int | bool], values: Sequence[float]) -> float:
    """Correlación punto-biserial entre una variable binaria y una continua.

    ``r = (m1 - m0) / s * sqrt(p * (1 - p))`` con ``s`` la desviación estándar poblacional de
    ``values``. Si todos los valores binarios son iguales o ``values`` no varía, devuelve ``0.0``
    (sin capacidad de discriminar).

    Raises:
        ValueError: series vacías o de largo distinto.
    """
    _check_paired(binary, values)
    flags = [bool(b) for b in binary]
    ones = [v for v, f in zip(values, flags, strict=True) if f]
    zeros = [v for v, f in zip(values, flags, strict=True) if not f]
    if not ones or not zeros:
        return 0.0
    mean_all = _mean(values)
    std = math.sqrt(sum((v - mean_all) ** 2 for v in values) / len(values))
    if std == 0.0:
        return 0.0
    p = len(ones) / len(values)
    return (_mean(ones) - _mean(zeros)) / std * math.sqrt(p * (1.0 - p))


def item_discrimination(
    item_correct: Sequence[int | bool],
    total_scores: Sequence[float],
    *,
    corrected: bool = True,
) -> float:
    """Discriminación de un ítem: punto-biserial entre acertar el ítem y el puntaje total.

    Con ``corrected=True`` (por defecto) el puntaje del propio ítem se resta del total para no
    inflar la correlación. Meta del brief: al menos 0,2.

    Raises:
        ValueError: series vacías o de largo distinto.
    """
    _check_paired(item_correct, total_scores)
    if corrected:
        rest = [t - (1.0 if c else 0.0) for c, t in zip(item_correct, total_scores, strict=True)]
        return point_biserial(item_correct, rest)
    return point_biserial(item_correct, total_scores)


def valid_question_rate(verdicts_by_item: Sequence[Sequence[bool]]) -> float:
    """Porcentaje (0 a 100) de preguntas válidas.

    Cada elemento son los veredictos de los evaluadores sobre un ítem (``True`` = válido). Un
    ítem es válido solo si **todos** sus evaluadores lo marcaron válido (criterio conservador).

    Raises:
        ValueError: si no hay ítems o algún ítem no tiene veredictos.
    """
    if not verdicts_by_item:
        raise ValueError("no hay ítems anotados")
    if any(len(verdicts) == 0 for verdicts in verdicts_by_item):
        raise ValueError("hay ítems sin veredictos")
    valid = sum(1 for verdicts in verdicts_by_item if all(verdicts))
    return 100.0 * valid / len(verdicts_by_item)


# ---------------------------------------------------------------------------------------------
# Latencia
# ---------------------------------------------------------------------------------------------


def percentile(values: Sequence[float], q: float) -> float:
    """Percentil ``q`` (0 a 100) por interpolación lineal (igual que ``numpy.percentile``).

    Raises:
        ValueError: si no hay valores o ``q`` está fuera de [0, 100].
    """
    if not values:
        raise ValueError("no hay valores")
    if not 0.0 <= q <= 100.0:
        raise ValueError("q debe estar entre 0 y 100")
    ordered = sorted(values)
    position = (len(ordered) - 1) * q / 100.0
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(ordered[lower])
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


@dataclass(frozen=True)
class LatencyPercentiles:
    """p50 y p95 de una serie de latencias."""

    p50: float
    p95: float
    n: int


def latency_percentiles(latencies: Sequence[float]) -> LatencyPercentiles:
    """p50 y p95 de las latencias (en la unidad de entrada, por ejemplo ``latency_ms``).

    Raises:
        ValueError: si no hay latencias.
    """
    p50 = percentile(latencies, 50.0)
    p95 = percentile(latencies, 95.0)
    return LatencyPercentiles(p50, p95, len(latencies))
