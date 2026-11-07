"""Vistas de evaluación: convierte el `grading.v1` de la API en lo que muestran los componentes.

Solo presenta datos: el puntaje, `is_correct` y los criterios los calcula la API. El mínimo de
criterios («mínimo 2») se deriva de `min_criteria_ratio` únicamente para el texto.
"""

import math
from typing import Any

from components.rubric_result import CriterionView, RubricView


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
            evidence=str(item.get("evidence", "")),
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
