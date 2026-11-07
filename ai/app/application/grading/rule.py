"""Grading of multiple choice by rule (plan 5.4.10): right option = 100, otherwise 0."""

from __future__ import annotations

from app.domain.contracts.grading import AnswerGrading

CORRECT_FEEDBACK = "Respuesta correcta."
WRONG_FEEDBACK = "La opción elegida no es la correcta; revisa la explicación del tema."
UNANSWERED_FEEDBACK = "No elegiste ninguna opción."


def grade_multiple_choice(
    item_id: str, correct_option: int, selected_option: int | None
) -> AnswerGrading:
    """«No lo sé» and no answer (``selected_option`` is ``None``) count as wrong."""
    right = selected_option is not None and selected_option == correct_option
    if right:
        feedback = CORRECT_FEEDBACK
    else:
        feedback = UNANSWERED_FEEDBACK if selected_option is None else WRONG_FEEDBACK
    return AnswerGrading(
        item_id=item_id,
        item_type="multiple_choice",
        grader="rule",
        approval_rule="single_correct_option",
        score=100.0 if right else 0.0,
        is_correct=right,
        criteria_met=0,
        criteria_total=0,
        rubric_detail=[],
        feedback=feedback,
        meta=None,
    )
