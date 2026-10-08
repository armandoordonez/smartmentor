"""E6 · Tema (video + texto + quiz) y E7 · Resultado del quiz."""

import streamlit as st

from clients.base import ApiError
from clients.models import QuizResult
from components.formatting import percent
from components.layout import eyebrow, render_page_header
from components.quiz_form import render_answer_review, render_options
from components.video_player import render_explanation, render_video
from core.container import get_services
from core.errors import action_message
from core.navigation import MY_PATH
from core.session import get_session
from pages.student.context import require_enrollment
from services.learning_path import TopicPage

services = get_services()
session = get_session()
enrollment = require_enrollment(services, session)

topic_id = session.selected_topic_id
if topic_id is None:
    current = services.learning_path.path_view(enrollment).current
    if current is None:
        st.switch_page(MY_PATH)
    topic_id = current.topic.id
    session.open_topic(topic_id)
elif session.quiz_topic_id != topic_id:
    session.reset_quiz(topic_id)
page = services.learning_path.topic_page(enrollment, topic_id)


def render_result(result: QuizResult) -> None:
    attempts_left = result.max_attempts - result.attempt_number
    if result.passed:
        title = "¡Tema aprobado!"
        closing = "Tu avance quedó registrado."
    else:
        title = "Aún no apruebas este tema"
        closing = (
            f"Te quedan {attempts_left} de {result.max_attempts} intentos."
            if attempts_left > 0
            else "Ya usaste todos los intentos; tu docente verá tu avance."
        )
    render_page_header(
        title,
        caption=(
            f"Obtuviste {percent(result.score)} ({result.correct_count} de {result.total}). "
            f"El umbral es {percent(result.threshold)}. {closing}"
        ),
    )
    render_answer_review(result.reviews)
    with st.container(horizontal=True):
        if not result.passed and attempts_left > 0 and st.button("Reintentar con otra explicación"):
            session.reset_quiz(result.topic_id)
            st.rerun()
        if st.button("Volver a mi ruta", type="primary"):
            session.reset_quiz(None)
            st.switch_page(MY_PATH)


def render_quiz(page: TopicPage) -> None:
    step = next(s.step for s in page.path.steps if s.topic.id == page.topic.id)
    quiz = page.quiz
    with st.container(border=True):
        if step.status == "skipped":
            eyebrow("QUIZ DEL TEMA")
            st.markdown("Omitiste este tema porque ya lo dominas. Puedes repasarlo cuando quieras.")
            return
        if step.status == "approved":
            eyebrow("QUIZ DEL TEMA")
            st.markdown(f"Ya aprobaste este tema con {percent(step.last_score or 0)}.")
            return
        if not quiz.questions:
            eyebrow("QUIZ DEL TEMA")
            st.caption(
                "Este tema todavía no tiene quiz. En el piloto lo genera la capa de IA y lo "
                "revisa el docente."
            )
            return
        if step.attempts_used >= quiz.max_attempts:
            eyebrow("QUIZ DEL TEMA")
            st.markdown("Ya usaste todos los intentos de este tema. Habla con tu docente.")
            return

        index = min(session.quiz_index, len(quiz.questions) - 1)
        question = quiz.questions[index]
        is_last = index == len(quiz.questions) - 1
        eyebrow(f"QUIZ DEL TEMA · Pregunta {index + 1} de {len(quiz.questions)}")
        st.markdown(f"**{question.prompt}**")
        choice = render_options(
            question, selected=session.quiz_answers.get(question.id), key="quiz"
        )
        if choice is not None:
            session.quiz_answers[question.id] = choice
        st.caption(
            f"Responde sin ayuda de IA. Intento {quiz.attempt_number} de {quiz.max_attempts}."
        )
        if not st.button(
            "Enviar respuesta" if is_last else "Siguiente",
            type="primary",
            disabled=choice is None,
        ):
            return
        if not is_last:
            session.quiz_index = index + 1
            st.rerun()
        try:
            session.quiz_result = services.assessment.submit_quiz(
                enrollment.id, page.topic.id, session.quiz_answers
            )
        except ApiError as error:
            st.error(action_message(error))
            return
        st.rerun()


if session.quiz_result is not None and session.quiz_result.topic_id == page.topic.id:
    render_result(session.quiz_result)
    st.stop()

render_page_header(
    page.topic.title,
    breadcrumb=(
        f"{page.path.path.short_title} › Tema {page.position} de {len(page.path.steps) + 1}"
    ),
)
content, quiz = st.columns([2, 1], gap="medium")
with content:
    render_video(page.content.video)
    render_explanation(page.content)
with quiz:
    render_quiz(page)
st.page_link(MY_PATH, label="Volver a mi ruta", icon=":material/arrow_back:")
