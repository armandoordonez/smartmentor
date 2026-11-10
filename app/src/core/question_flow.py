"""Preguntas de una en una (diagnóstico E3, quiz E6b y E6c, final E8, retención E14).

Dibuja la pregunta actual, guarda las respuestas en cada paso («guardado parcial») y entrega al
final. Qué se hace al guardar y al entregar lo decide la página con los callbacks; el avance entre
preguntas es solo de presentación.
"""

from collections.abc import Callable, Sequence

import streamlit as st

from clients.base import ApiError
from clients.models import AssessmentItem, LearnerAnswer
from components.quiz_form import render_options
from core.errors import show_action_error
from core.learner_state import AnswerSheet

DONT_KNOW_LABEL = "No lo sé"
SHORT_ANSWER_LIMIT = 500


def _is_answered(item: AssessmentItem, sheet: AnswerSheet) -> bool:
    answer = sheet.answers.get(item.item_id)
    if answer is None:
        return False
    if item.item_type == "short_answer":
        return bool((answer.text_answer or "").strip())
    return answer.dont_know or answer.selected_option is not None


def _question(
    item: AssessmentItem,
    sheet: AnswerSheet,
    key: str,
    *,
    hint: str | None,
    show_rubric: bool,
) -> None:
    saved = sheet.answers.get(item.item_id)
    widget_key = f"{key}-{item.item_id}"
    if item.item_type == "multiple_choice":
        choice = render_options(
            stem=item.stem,
            options=item.options,
            key=widget_key,
            selected=saved.selected_option if saved and not saved.dont_know else None,
        )
        if choice is not None:
            sheet.answers[item.item_id] = LearnerAnswer(
                item_id=item.item_id, selected_option=choice
            )
        return
    st.markdown(f"**{item.stem}**")
    if hint:
        st.caption(hint)
    text = st.text_area(
        "Tu respuesta",
        value=(saved.text_answer or "") if saved else "",
        max_chars=SHORT_ANSWER_LIMIT,
        placeholder="Escribe tu respuesta…",
        label_visibility="collapsed",
        key=f"answer-{widget_key}",
    )
    st.caption(f"{len(text)} / {SHORT_ANSWER_LIMIT} caracteres")
    if text.strip():
        sheet.answers[item.item_id] = LearnerAnswer(item_id=item.item_id, text_answer=text)
    elif item.item_id in sheet.answers:
        del sheet.answers[item.item_id]
    if show_rubric and item.rubric_summary:
        st.caption("**CÓMO SE CALIFICA**")
        st.markdown(item.rubric_summary)


def render_question_sheet(
    items: Sequence[AssessmentItem],
    sheet: AnswerSheet,
    *,
    key: str,
    save: Callable[[list[LearnerAnswer]], object],
    submit: Callable[[list[LearnerAnswer]], object],
    submit_label: str,
    notes: Sequence[str] | Callable[[AssessmentItem], Sequence[str]] = (),
    context: Callable[[AssessmentItem], str | None] | None = None,
    allow_dont_know: bool = False,
    hint: str | None = None,
) -> None:
    """Pregunta actual, notas, «No lo sé» y botones Anterior y Siguiente (o el de entregar)."""
    if not items:
        st.info("Esta prueba todavía no tiene preguntas.")
        return
    index = min(sheet.index, len(items) - 1)
    item = items[index]
    if context is not None and (line := context(item)):
        st.caption(line)
    _question(item, sheet, key, hint=hint, show_rubric=True)
    for note in notes(item) if callable(notes) else notes:
        st.caption(note)
    if (
        allow_dont_know
        and item.item_type == "multiple_choice"
        and st.button(DONT_KNOW_LABEL, key=f"{key}-dont-know-{item.item_id}")
    ):
        sheet.answers[item.item_id] = LearnerAnswer(item_id=item.item_id, dont_know=True)
        st.session_state.pop(f"option-{key}-{item.item_id}", None)
        st.rerun()
    is_last = index == len(items) - 1
    with st.container(horizontal=True):
        back = st.button("Anterior", key=f"{key}-back", disabled=index == 0)
        forward = st.button(
            submit_label if is_last else "Siguiente",
            type="primary",
            key=f"{key}-next",
            disabled=not _is_answered(item, sheet),
        )
    if not (back or forward):
        return
    try:
        save(list(sheet.answers.values()))
        if back:
            sheet.index = index - 1
        elif is_last:
            submit(list(sheet.answers.values()))
        else:
            sheet.index = index + 1
    except ApiError as error:
        show_action_error(error)
        return
    st.rerun()
