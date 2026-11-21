"""Reglas puras de calificación: opción múltiple por regla, respuesta corta por criterios y SUS."""

from collections.abc import Iterable, Sequence
from typing import Any

from app.common.exceptions import BusinessRuleError
from app.domains.assessments.entities import AssessmentItem, AttemptAnswer

MULTIPLE_CHOICE = "multiple_choice"
SHORT_ANSWER = "short_answer"
RATIO_TOLERANCE = 1e-3


def grade_multiple_choice(item: AssessmentItem, answer: AttemptAnswer) -> dict[str, Any]:
    """`grading.v1` de una pregunta de opción múltiple: correcta solo con la opción de la clave.

    «No lo sé» o sin respuesta cuentan como no acierto.
    """
    correct = (
        not answer.dont_know
        and answer.selected_index is not None
        and answer.selected_index == item.correct_index
    )
    return {
        "item_id": str(item.id),
        "item_type": MULTIPLE_CHOICE,
        "grader": "rule",
        "approval_rule": "single_correct_option",
        "min_criteria_ratio": None,
        "score": 100.0 if correct else 0.0,
        "is_correct": correct,
        "criteria_met": int(correct),
        "criteria_total": 1,
        "rubric_detail": [],
        "feedback": "",
    }


def short_answer_is_correct(criteria_met: int, criteria_total: int, min_ratio: float) -> bool:
    """Aprobada si cumple la proporción mínima de criterios (DEF-21: 2 de 3 por defecto)."""
    if criteria_total <= 0:
        return False
    # Tolerancia de redondeo: la base guarda la proporción con 3 decimales (2/3 -> 0,667).
    return criteria_met / criteria_total >= min_ratio - RATIO_TOLERANCE


def attempt_score(scores: Iterable[float | None]) -> float:
    """Puntaje del intento: promedio de los puntajes de sus respuestas (0 a 100)."""
    values = [s or 0.0 for s in scores]
    return round(sum(values) / len(values), 2) if values else 0.0


def sus_score(items: Sequence[int]) -> float:
    """SUS: (suma de impares - 5 + 25 - suma de pares) x 2,5, con 10 respuestas de 1 a 5."""
    if len(items) != 10 or any(not 1 <= v <= 5 for v in items):
        raise BusinessRuleError(
            "sus_items must have 10 answers from 1 to 5.", code="VALIDATION_ERROR"
        )
    odd = sum(items[0::2])
    even = sum(items[1::2])
    return (odd - 5 + 25 - even) * 2.5


def pick_quiz_items(
    unseen: Sequence[AssessmentItem], count: int, *, max_short_answers: int = 1
) -> list[AssessmentItem]:
    """Elige `count` ítems no vistos: opción múltiple primero y a lo sumo una respuesta corta."""
    short = [i for i in unseen if i.item_type == SHORT_ANSWER][:max_short_answers]
    choice = [i for i in unseen if i.item_type != SHORT_ANSWER]
    picked = choice[: max(count - len(short), 0)] + short
    if len(picked) < count:
        rest = [i for i in unseen if i not in picked]
        picked += rest[: count - len(picked)]
    return sorted(picked[:count], key=lambda i: i.id or 0)


def round_robin(
    items: Sequence[AssessmentItem], topic_order: Sequence[int], count: int
) -> list[AssessmentItem]:
    """Reparte `count` ítems entre los temas, en el orden de la ruta (evaluación final)."""
    by_topic: dict[int, list[AssessmentItem]] = {t: [] for t in topic_order}
    for item in items:
        by_topic.setdefault(item.topic_id, []).append(item)
    picked: list[AssessmentItem] = []
    while len(picked) < count and any(by_topic.values()):
        for topic in list(by_topic):
            if by_topic[topic] and len(picked) < count:
                picked.append(by_topic[topic].pop(0))
    return picked
