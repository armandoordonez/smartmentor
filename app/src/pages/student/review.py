"""E9 · Repaso dirigido (evaluación final por debajo del umbral)."""

import streamlit as st

from components.formatting import percent
from components.layout import render_page_header
from core.container import get_services
from core.navigation import BADGE, FINAL_ASSESSMENT, MY_PATH, TOPIC
from core.session import get_session
from pages.student.context import require_enrollment

services = get_services()
session = get_session()
enrollment = require_enrollment(services, session)

result = services.assessment.last_final_result(enrollment.id)
if result is not None and result.passed:
    st.switch_page(BADGE)
if result is None:
    render_page_header("Repaso dirigido")
    st.info("Todavía no presentas la evaluación final de esta ruta.")
    st.page_link(MY_PATH, label="Volver a mi ruta", icon=":material/arrow_back:")
    st.stop()

progress = services.learning_path.path_view(enrollment).progress

render_page_header(
    "Aún no alcanzas el badge",
    caption=(
        f"Obtuviste {percent(result.score)} en la evaluación final; necesitas "
        f"{percent(result.threshold)}. Repasa los temas débiles y vuelve a intentar con "
        "preguntas nuevas."
    ),
)

with st.container(border=True):
    st.markdown("#### Temas a repasar")
    for topic in result.weak_topics:
        name, score, action = st.columns([8, 1, 1.6], vertical_alignment="center")
        name.markdown(topic.topic_title)
        score.markdown(f":orange[**{percent(topic.score)}**]")
        if action.button("Repasar tema", key=f"review-{topic.topic_id}"):
            session.open_topic(topic.topic_id)
            st.switch_page(TOPIC)

st.caption(f"Intento {result.attempt_number} de {result.max_attempts} usado.")
if st.button(
    "Reintentar evaluación final",
    type="primary",
    disabled=not progress.final_available,
    help=None if progress.final_available else "Ya usaste todos los intentos.",
):
    session.reset_final()
    st.switch_page(FINAL_ASSESSMENT)
