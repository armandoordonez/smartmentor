"""Cálculo puro de las métricas del brief que salen de la base (sin SQL ni FastAPI).

Las consultas traen los pares ya agrupados; aquí solo se calculan κ de Cohen, QWK, P@k y nDCG@k.
"""

import math
from collections.abc import Sequence


def cohen_kappa(pairs: Sequence[tuple[str, str]]) -> float | None:
    """κ de Cohen entre dos evaluadores (etiquetas nominales); `None` sin pares o sin varianza."""
    if not pairs:
        return None
    n = len(pairs)
    labels = sorted({a for a, _ in pairs} | {b for _, b in pairs})
    observed = sum(1 for a, b in pairs if a == b) / n
    expected = sum(
        (sum(1 for a, _ in pairs if a == label) / n) * (sum(1 for _, b in pairs if b == label) / n)
        for label in labels
    )
    if math.isclose(expected, 1.0):
        return None
    return round((observed - expected) / (1 - expected), 4)


def quadratic_weighted_kappa(pairs: Sequence[tuple[int, int]], categories: int) -> float | None:
    """QWK entre dos calificadores con categorías ordinales `0..categories-1`."""
    if not pairs or categories < 2:
        return None
    n = len(pairs)
    observed = [[0.0] * categories for _ in range(categories)]
    for a, b in pairs:
        observed[min(max(a, 0), categories - 1)][min(max(b, 0), categories - 1)] += 1
    rows = [sum(observed[i]) for i in range(categories)]
    cols = [sum(observed[i][j] for i in range(categories)) for j in range(categories)]
    numerator = denominator = 0.0
    for i in range(categories):
        for j in range(categories):
            weight = ((i - j) ** 2) / ((categories - 1) ** 2)
            numerator += weight * observed[i][j]
            denominator += weight * rows[i] * cols[j] / n
    if denominator == 0:
        return None
    return round(1 - numerator / denominator, 4)


def precision_at_k(relevance: Sequence[bool], k: int = 3) -> float | None:
    """Fracción de relevantes entre los `k` primeros (la lista ya viene ordenada por puesto)."""
    top = list(relevance[:k])
    if not top:
        return None
    return sum(1 for r in top if r) / k


def ndcg_at_k(relevance: Sequence[bool], k: int = 3) -> float | None:
    """nDCG@k con relevancia binaria. `None` si ningún candidato es relevante (sin ideal)."""
    top = list(relevance[:k])
    if not top:
        return None
    dcg = sum((1.0 if r else 0.0) / math.log2(i + 2) for i, r in enumerate(top))
    ideal_count = sum(1 for r in relevance if r)
    ideal = sum(1.0 / math.log2(i + 2) for i in range(min(ideal_count, k)))
    if ideal == 0:
        return None
    return dcg / ideal


def mean(values: Sequence[float | None]) -> float | None:
    present = [v for v in values if v is not None]
    return round(sum(present) / len(present), 4) if present else None


def score_bucket(score: float, categories: int = 5) -> int:
    """Convierte una nota de 0 a 100 en una categoría ordinal (por defecto, bandas de 20)."""
    return min(int(score // (100 / categories)), categories - 1)
