"""Vistas de evaluación: convierte el `grading.v1` de la API en lo que muestran los componentes.

Solo presenta datos: el puntaje, `is_correct` y los criterios los calcula la API. El mínimo de
criterios («mínimo 2») se deriva de `min_criteria_ratio` únicamente para el texto.
"""

import math
import re
from collections.abc import Sequence
from typing import Any

from clients.models import AssessmentItem
from components.rubric_result import CriterionView, RubricView

RUBRIC_COUNT = re.compile(r"rúbrica de (\d+) criterios?", re.IGNORECASE)
GRADING_RUBRIC_STEP = "Aplicar la rúbrica a tu respuesta corta"


def rubric_view(grading: dict[str, Any]) -> RubricView | None:
    """Vista de la rúbrica de una respuesta corta; None si el ítem no es de respuesta corta."""
    if grading.get("item_type") != "short_answer":
        return None
    total = int(grading.get("criteria_total", 0))
    ratio = grading.get("min_criteria_ratio")
    min_met = math.ceil(round(float(ratio) * total, 2)) if ratio is not None and total else None
    criteria = tuple(
        CriterionView(
            name=str(item.get("criterion", "")),
            met=bool(item.get("met", False)),
            evidence=str(item.get("evidence") or ""),
            reason=str(item.get("reason") or ""),
        )
        for item in grading.get("rubric_detail", [])
    )
    return RubricView(
        criteria=criteria,
        criteria_met=int(grading.get("criteria_met", 0)),
        criteria_total=total,
        min_met=min_met,
        is_correct=bool(grading.get("is_correct", False)),
        graded_by="un instructor" if grading.get("grader") == "human" else "IA",
    )


def rubric_criteria_count(items: Sequence[AssessmentItem]) -> int | None:
    """Criterios de la rúbrica de la respuesta corta, si el texto de la pregunta los dice.

    La API no manda la rúbrica estructurada; `rubric_summary` es el texto visible que dice
    «rúbrica de N criterios». Sin ese dato (o si las preguntas no coinciden) devuelve None.
    """
    counts = {
        int(match.group(1))
        for item in items
        if item.item_type == "short_answer"
        and item.rubric_summary
        and (match := RUBRIC_COUNT.search(item.rubric_summary))
    }
    return counts.pop() if len(counts) == 1 else None


def grading_rubric_step(items: Sequence[AssessmentItem]) -> str:
    """Segundo paso de la pantalla «Calificando»: con el número real de criterios o sin número."""
    count = rubric_criteria_count(items)
    if count is None:
        return GRADING_RUBRIC_STEP
    return f"Aplicar la rúbrica de {count} criterios a tu respuesta corta"
