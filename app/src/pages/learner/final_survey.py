"""E13a y E13b · Encuesta final (Likert y SUS), en dos pasos.

Es voluntaria y no afecta el badge. Las respuestas del paso 1 se conservan al ir y volver. Al enviar
(`POST …/surveys/final`) vuelve al badge. El puntaje SUS lo calcula la API.
"""

import streamlit as st

from clients.base import ApiError
from components.layout import render_page_header
from components.likert_scale import EXPERIENCE_ITEMS, SCALE_HINT, SUS_ITEMS, render_likert
from core.container import get_client
from core.errors import show_action_error
from core.learner_flow import current_enrollment
from core.session import get_session

BADGE_PAGE = "pages/learner/badge.py"

client = get_client()
state = get_session().learner
enrollment = current_enrollment(client)
step = state.survey_step if state.survey_step in (1, 2) else 1


def _scale(index: int) -> None:
    """Pregunta SUS número `index` (1 a 10); conserva la respuesta en la sesión."""
    value = render_likert(
        f"{index}. {SUS_ITEMS[index - 1]}", key=f"sus-{index}", value=state.survey_sus.get(index)
    )
    if value is not None:
        state.survey_sus[index] = value


def _submit() -> None:
    try:
        client.submit_final_survey(
            enrollment.id,
            likert=state.survey_likert,
            sus_items=[state.survey_sus[i] for i in range(1, 11)],
            comment=(st.session_state.get("survey-comment") or "").strip() or None,
        )
    except ApiError as error:
        show_action_error(error)
        return
    state.survey_step = 1
    st.switch_page(BADGE_PAGE)


course = enrollment.learning_path.name
if step == 1:
    st.caption(f"{course} · Encuesta final")
    render_page_header(
        "Cuéntanos cómo te fue",
        caption=(
            "Es voluntaria y no afecta tu badge. Tus respuestas se analizan sin tu nombre y solo "
            "para evaluar la plataforma, según el consentimiento informado."
        ),
    )
    st.markdown("**Paso 1 de 2**")
    st.caption("unos 3 minutos")
    st.subheader("Tu experiencia", anchor=False)
    st.caption(SCALE_HINT)
    for code, statement in EXPERIENCE_ITEMS:
        value = render_likert(statement, key=code, value=state.survey_likert.get(code))
        if value is not None:
            state.survey_likert[code] = value
    st.subheader("Usabilidad (SUS · ítems 1 a 5)", anchor=False)
    for index in range(1, 6):
        _scale(index)
    complete = len(state.survey_likert) == len(EXPERIENCE_ITEMS) and all(
        i in state.survey_sus for i in range(1, 6)
    )
    with st.container(horizontal=True):
        if st.button("Ahora no", key="survey-skip"):
            st.switch_page(BADGE_PAGE)
        if st.button("Siguiente", type="primary", key="survey-next", disabled=not complete):
            state.survey_step = 2
            st.rerun()
else:
    st.caption(f"{course} · Encuesta final")
    render_page_header("Casi terminas")
    st.markdown("**Paso 2 de 2**")
    st.caption("unos 2 minutos")
    st.subheader("Usabilidad (SUS · ítems 6 a 10)", anchor=False)
    st.caption(SCALE_HINT)
    for index in range(6, 11):
        _scale(index)
    st.markdown("**Comentario (opcional)**")
    st.text_area(
        "¿Qué mejorarías?",
        max_chars=500,
        placeholder="¿Qué mejorarías?",
        key="survey-comment",
    )
    st.caption(
        "¡Gracias! Tus respuestas nos ayudan a mejorar SmartMentor. Al enviar vuelves a tu badge."
    )
    complete = all(i in state.survey_sus for i in range(6, 11))
    with st.container(horizontal=True):
        if st.button("Anterior", key="survey-back"):
            state.survey_step = 1
            st.rerun()
        if st.button("Enviar encuesta", type="primary", key="survey-send", disabled=not complete):
            _submit()
