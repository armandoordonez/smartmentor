"""E8 · Evaluación final."""

import streamlit as st

from clients.base import ApiError
from components.formatting import percent
from components.layout import render_notice, render_page_header
from components.quiz_form import render_options
from components.theme import BLOOM_LABEL
from core.config import get_settings
from core.container import get_services
from core.errors import action_message
from core.navigation import BADGE, MY_PATH, REVIEW
from core.session import get_session
from pages.student.context import require_enrollment

services = get_services()
session = get_session()
enrollment = require_enrollment(services, session)

view = services.learning_path.path_view(enrollment)
if view.progress.final_passed:
    st.switch_page(BADGE)
if not view.progress.final_available:
    render_page_header("Evaluación final", caption=view.path.title)
    st.info(
        "La evaluación final se habilita cuando apruebas (u omites) todos los temas de la ruta y "
        "te quedan intentos."
    )
    st.page_link(MY_PATH, label="Volver a mi ruta", icon=":material/arrow_back:")
    st.stop()

assessment = services.assessment.final_assessment(enrollment.id)
questions = assessment.questions
index = min(session.final_index, len(questions) - 1)
question = questions[index]
is_last = index == len(questions) - 1

render_notice(
    f"Evaluación final · Sin ayuda de IA ni apuntes. Necesitas {percent(assessment.threshold)} "
    f"para el badge. Intento {assessment.attempt_number} de {assessment.max_attempts}."
)
render_page_header(
    "Evaluación final",
    caption=f"{view.path.title} · Pregunta {index + 1} de {len(questions)}",
)


def submit(answers: dict[int, int | None]) -> None:
    try:
        result = services.assessment.submit_final(enrollment.id, answers)
    except ApiError as error:
        st.error(action_message(error))
        return
    session.reset_final()
    st.switch_page(BADGE if result.passed else REVIEW)


with st.container(border=True):
    st.badge(f"Bloom · {BLOOM_LABEL[question.bloom_level]}", color="blue")
    st.subheader(question.prompt, anchor=False)
    choice = render_options(question, selected=session.final_answers.get(question.id), key="final")
    if choice is not None:
        session.final_answers[question.id] = choice
    with st.container(horizontal=True, vertical_alignment="center"):
        st.badge("Tutor IA desactivado durante la evaluación", color="gray")
        st.space("stretch")
        previous = st.button("Anterior", disabled=index == 0)
        following = st.button(
            "Entregar evaluación" if is_last else "Siguiente",
            type="primary",
            disabled=choice is None,
        )

if previous:
    session.final_index = index - 1
    st.rerun()
if following:
    if not is_last:
        session.final_index = index + 1
        st.rerun()
    submit(session.final_answers)

if get_settings().app_data_source == "sample" and st.button(
    ":orange[(Demo del prototipo) Ver resultado menor a 80 %]", type="tertiary"
):
    # Responde la primera opción de cada pregunta: con los datos de ejemplo da 70 %.
    submit({q.id: 0 for q in questions})
