"""Preguntas de una en una (diagnóstico E3, quiz E6b y E6c, final E8, retención E14).

Dibuja la pregunta actual, guarda las respuestas en cada paso («guardado parcial») y entrega al
final. Qué se hace al guardar y al entregar lo decide la página con los callbacks; el avance entre
preguntas es solo de presentación.
"""

from collections.abc import Callable, Sequence
from contextlib import suppress
from typing import Literal

import streamlit as st
from streamlit.errors import StreamlitInvalidLayoutContextError

from clients.base import ApiError
from clients.models import AssessmentItem, LearnerAnswer
from components.quiz_form import render_options
from core.errors import show_action_error
from core.learner_state import AnswerSheet

DONT_KNOW_LABEL = "No lo sé"
SHORT_ANSWER_LIMIT = 500


def _rerun(scope: Literal["app", "fragment"]) -> None:
    """Vuelve a dibujar solo el fragmento si se está en uno; si no (la primera carga o `AppTest`,
    que corre la página entera), la página."""
    if scope == "fragment":
        with suppress(StreamlitInvalidLayoutContextError):
            st.rerun(scope="fragment")
    st.rerun()


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
    rerun_scope: Literal["auto", "app", "fragment"] = "auto",
) -> None:
    """Pregunta actual, notas, «No lo sé» y botones Anterior y Siguiente (o el de entregar).

    Elegir una opción o escribir nunca recarga la página entera (B-018, B-022):
    - `"auto"` (por defecto): la hoja va en su propio `st.fragment`. Elegir solo redibuja la hoja;
      «No lo sé», Anterior y Siguiente guardan y recargan la página, para que el «Pregunta X de N»
      que la página muestra arriba se actualice.
    - `"fragment"`: la página ya puso la hoja (con su encabezado) dentro de un fragmento; todo,
      salvo entregar, redibuja solo ese fragmento y no vuelve a pedir datos a la API.
    - `"app"`: sin fragmento; cada interacción recarga la página.

    Entregar siempre recarga la página entera: lo que sigue lo decide el `next_action`.
    """
    if rerun_scope == "auto":
        _sheet_fragment(
            items,
            sheet,
            key=key,
            save=save,
            submit=submit,
            submit_label=submit_label,
            notes=notes,
            context=context,
            allow_dont_know=allow_dont_know,
            hint=hint,
            nav_scope="app",
        )
        return
    _sheet(
        items,
        sheet,
        key=key,
        save=save,
        submit=submit,
        submit_label=submit_label,
        notes=notes,
        context=context,
        allow_dont_know=allow_dont_know,
        hint=hint,
        nav_scope=rerun_scope,
    )


def _sheet(
    items: Sequence[AssessmentItem],
    sheet: AnswerSheet,
    *,
    key: str,
    save: Callable[[list[LearnerAnswer]], object],
    submit: Callable[[list[LearnerAnswer]], object],
    submit_label: str,
    notes: Sequence[str] | Callable[[AssessmentItem], Sequence[str]],
    context: Callable[[AssessmentItem], str | None] | None,
    allow_dont_know: bool,
    hint: str | None,
    nav_scope: Literal["app", "fragment"],
) -> None:
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
    is_last = index == len(items) - 1
    saved = sheet.answers.get(item.item_id)
    if saved is not None and saved.dont_know:
        st.caption(f"Respondiste «{DONT_KNOW_LABEL}». Puedes elegir una opción si la sabes.")
    # «No lo sé» cuenta como respuesta: guarda y pasa a la siguiente pregunta (en la última se
    # queda para que la persona entregue). Antes solo marcaba y no se veía ningún cambio (B-019).
    dont_know = (
        allow_dont_know
        and item.item_type == "multiple_choice"
        and st.button(DONT_KNOW_LABEL, key=f"{key}-dont-know-{item.item_id}")
    )
    if dont_know:
        sheet.answers[item.item_id] = LearnerAnswer(item_id=item.item_id, dont_know=True)
        st.session_state.pop(f"option-{key}-{item.item_id}", None)
        try:
            save(list(sheet.answers.values()))
        except ApiError as error:
            show_action_error(error)
            return
        if not is_last:
            sheet.index = index + 1
        _rerun(nav_scope)
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
    _rerun("app" if forward and is_last else nav_scope)


# La misma hoja como fragmento con identidad fija (`"auto"`): Streamlit la vuelve a llamar con los
# argumentos de la última ejecución completa de la página.
_sheet_fragment = st.fragment(_sheet)
