"""E6 · Tema: explicación, video con calificación y entrada al quiz.

El video y la explicación se ven antes del quiz y no durante él. «Empezar quiz» crea el intento
(`POST …/steps/{id}/attempts`): la API responde con el intento o, si hay que generar preguntas
nuevas, con un trabajo de IA (U1b). Los intentos restantes salen de la API.
"""

import streamlit as st

from clients.base import ApiError
from clients.models import Attempt, PathDetail, StepContent
from components.layout import eyebrow, render_page_header
from components.video_feedback import render_video_feedback
from components.video_player import render_explanation, render_video
from core.container import get_client
from core.errors import show_action_error
from core.learner_flow import current_enrollment, idempotency_key
from core.session import get_session
from services.content import (
    explanation_text,
    source_note,
    video_duration,
    youtube_url,
)

PATH_PAGE = "pages/learner/path.py"
QUIZ_PAGE = "pages/learner/quiz.py"
RESULT_PAGE = "pages/learner/quiz_result.py"

client = get_client()
state = get_session().learner
enrollment = current_enrollment(client)

step_id = state.step_id or enrollment.next_action.step_id
if step_id is None:
    st.info("Elige un tema en tu ruta para empezar.")
    st.page_link(PATH_PAGE, label="Volver a mi ruta")
    st.stop()

try:
    content: StepContent = client.get_step_content(enrollment.id, step_id)
    path: PathDetail = client.get_path(enrollment.id)
except ApiError as error:
    show_action_error(error)
    st.stop()

step = next((s for s in path.steps if s.step_id == step_id), None)
position = f" › Tema {step.step_order} de {len(path.steps)}" if step else ""
render_page_header(content.topic.name, breadcrumb=f"{enrollment.learning_path.name}{position}")

if content.video is not None:
    render_video(
        title=content.video.title,
        duration_label=video_duration(content.video),
        url=youtube_url(content.video),
    )
    sent_key = f"video-feedback-sent-{content.video.video_candidate_id}"
    if st.session_state.get(sent_key):
        st.success("¡Gracias! Tu calificación llegó a tu instructor sin tu nombre.")
    else:
        feedback = render_video_feedback(key=f"video-{content.video.video_candidate_id}")
        if feedback.submit and feedback.rating is not None:
            try:
                client.send_video_feedback(
                    video_candidate_id=content.video.video_candidate_id,
                    enrollment_id=enrollment.id,
                    rating=feedback.rating,
                    comment=feedback.comment,
                    watched_fully=False,
                )
            except ApiError as error:
                show_action_error(error)
            else:
                st.session_state[sent_key] = True
                st.rerun()

if content.explanation is not None:
    render_explanation(
        explanation_text(content.explanation.content),
        source_note=source_note(content.explanation),
    )
if content.personal_example:
    st.markdown(f"**{content.personal_example.get('title', 'Ejemplo para ti')}**")
    st.markdown(str(content.personal_example.get("body", "")))

rules, attempts = content.quiz_rules, content.attempts
with st.container(key="card-quiz-entry"):
    eyebrow("QUIZ DEL TEMA")
    st.markdown("**Cuando termines, presenta el quiz**")
    st.caption(f"{rules.items_per_attempt} preguntas, de opción múltiple y de respuesta corta.")
    total = attempts.max + attempts.extra_granted
    st.caption(
        f"Apruebas con {round(rules.pass_threshold)} %. Este es tu intento "
        f"{min(attempts.used + 1, total)} de {total}."
    )
    st.caption("Durante el quiz no verás el video ni la explicación. Respóndelo sin ayuda de IA.")
    action = enrollment.next_action
    open_attempt = (
        action.attempt_id
        if action.type == "continue_attempt" and action.step_id == step_id
        else None
    )
    if open_attempt is not None:
        # Ya hay un intento abierto: la API no deja crear otro (`ATTEMPT_IN_PROGRESS`).
        if st.button("Continuar quiz", type="primary", key="topic-continue-quiz"):
            state.step_id, state.attempt_id, state.quiz_job_id = step_id, open_attempt, None
            st.switch_page(QUIZ_PAGE)
    elif attempts.remaining <= 0:
        st.warning("Usaste todos los intentos de este tema.")
        if st.button("Ver el estado de este tema", key="topic-exhausted"):
            state.attempt_id = None
            st.switch_page(RESULT_PAGE)
    elif st.button("Empezar quiz", type="primary", key="topic-start-quiz"):
        try:
            created = client.create_attempt(
                enrollment.id,
                step_id,
                "topic",
                idempotency_key=idempotency_key(
                    f"attempt-{enrollment.id}-{step_id}-{attempts.used}"
                ),
            )
        except ApiError as error:
            show_action_error(error)
        else:
            state.step_id = step_id
            if isinstance(created, Attempt):
                state.attempt_id = created.id
                state.quiz_job_id = None
            else:
                state.quiz_job_id = created.job_id
                state.quiz_job_kind = "prepare"
            st.switch_page(QUIZ_PAGE)
