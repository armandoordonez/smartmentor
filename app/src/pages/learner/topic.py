"""E6 · Tema: explicación, video con calificación y entrada al quiz.

El video y la explicación se ven antes del quiz y no durante él. «Empezar quiz» crea el intento
(`POST …/steps/{id}/attempts`): la API responde con el intento o, si hay que generar preguntas
nuevas, con un trabajo de IA (U1b). Los intentos restantes salen de la API.

Un tema aprobado u omitido llega en modo repaso (`mode: "review"`, B-025): se ve la explicación y
el video con la etiqueta «Repaso» y sin la tarjeta del quiz. Se abre desde E5 o desde «Repasar
tema» de E9.
"""

from datetime import datetime

import streamlit as st

from clients.base import ApiError
from clients.models import Attempt, PathDetail, StepContent
from clients.models_learner import InteractionEvent
from components.layout import eyebrow, render_page_header
from components.video_feedback import render_video_feedback
from components.video_player import render_explanation, render_video
from core.container import get_client
from core.errors import show_action_error
from core.learner_flow import current_enrollment, go_to_action, idempotency_key
from core.session import get_session
from core.usage_events import build_event, open_view
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

# Un tema aprobado u omitido ya no abre intentos: la API lo entrega en modo repaso. Una API anterior
# al modo repaso respondía `409 STEP_NOT_AVAILABLE`; en ese caso se explica por qué (B-025).
REVIEW_MODE = "review"
REVIEW_LABEL = "Repaso"
DEFAULT_CLOSED_NOTE = "Ya completaste este tema."
CLOSED_NOTES = {
    "passed": "Ya aprobaste este tema.",
    "skipped": "Este tema se omitió porque tu diagnóstico mostró que ya lo dominas.",
}
# B-046: si la API no trae explicación o video no se deja el hueco sin aviso ni se inventa nada.
NO_EXPLANATION_NOTE = ":material/info: Este tema todavía no tiene explicación en texto."
NO_VIDEO_NOTE = ":material/info: Este tema todavía no tiene video."

try:
    path: PathDetail = client.get_path(enrollment.id)
except ApiError as error:
    show_action_error(error)
    st.stop()

step = next((s for s in path.steps if s.step_id == step_id), None)
position = f" › Tema {step.step_order} de {len(path.steps)}" if step else ""
breadcrumb = f"{enrollment.learning_path.name}{position}"
closed_note = CLOSED_NOTES.get(step.status) if step else None

try:
    content: StepContent = client.get_step_content(enrollment.id, step_id)
except ApiError as error:
    if step is None or closed_note is None or error.code != "STEP_NOT_AVAILABLE":
        show_action_error(error)
        st.stop()
    render_page_header(step.name, breadcrumb=breadcrumb)
    st.info(closed_note)
    if st.button("Volver a mi ruta", type="primary", key="topic-back"):
        st.switch_page(PATH_PAGE)
    st.stop()

render_page_header(content.topic.name, breadcrumb=breadcrumb)
reviewing = content.mode == REVIEW_MODE
if reviewing:
    st.badge(REVIEW_LABEL, color="blue", icon=":material/history_edu:")


def _resources_shown(at: datetime) -> list[InteractionEvent]:
    """`resource.view` del texto y del video que muestra esta visita (una vez por visita)."""
    events: list[InteractionEvent] = []
    common = {"screen": "E6", "step_id": content.step_id}
    if content.explanation is not None:
        payload = {
            **common,
            "resource": "explanation",
            "resource_id": content.explanation.resource_id,
        }
        events.append(
            build_event(
                enrollment.id,
                "resource.view",
                topic_id=content.topic.id,
                payload=payload,
                occurred_at=at,
            )
        )
    if content.video is not None:
        payload = {
            **common,
            "resource": "video",
            "video_candidate_id": content.video.video_candidate_id,
            "duration_seconds": content.video.duration_seconds,
        }
        events.append(
            build_event(
                enrollment.id,
                "resource.view",
                topic_id=content.topic.id,
                payload=payload,
                occurred_at=at,
            )
        )
    return events


# Tiempo en tarea (m27): `topic.open` y lo que se ve, una vez por visita; `topic.close` con los
# segundos al salir del tema (al empezar el quiz o al ir a otra página).
open_view(
    client,
    f"topic:{enrollment.id}:{content.step_id}",
    enrollment_id=enrollment.id,
    event_type="topic.open",
    close_type="topic.close",
    topic_id=content.topic.id,
    payload={
        "screen": "E6",
        "step_id": content.step_id,
        "step_status": content.status,
        "mode": content.mode,
    },
    extra=_resources_shown,
)

# Dos columnas como en Figma (V-011): video, valoración y explicación a la izquierda y la tarjeta
# del quiz a la derecha.
left, right = st.columns([2, 1])


@st.fragment
def _video_block() -> None:
    """Video y valoración. Va en un fragmento: cada clic en las etiquetas, el comentario o «Enviar»
    solo redibuja este bloque y no vuelve a pedir inscripción, ruta y contenido a la API (B-046).
    El contenido del tema no cambia mientras se está en la pantalla: no queda desactualizado."""
    video = content.video
    if video is None:
        st.caption(NO_VIDEO_NOTE)
        return
    render_video(
        title=video.title,
        duration_label=video_duration(video),
        url=youtube_url(video),
    )
    sent_key = f"video-feedback-sent-{video.video_candidate_id}"
    if st.session_state.get(sent_key):
        st.success("¡Gracias! Tu calificación llegó a tu instructor sin tu nombre.")
        return
    # La tarjeta va en un hueco: al enviar se reemplaza por el agradecimiento sin otra ejecución.
    slot = st.empty()
    with slot.container():
        feedback = render_video_feedback(key=f"video-{video.video_candidate_id}")
    if feedback.submit and feedback.rating is not None:
        try:
            client.send_video_feedback(
                video_candidate_id=video.video_candidate_id,
                enrollment_id=enrollment.id,
                rating=feedback.rating,
                comment=feedback.comment,
                watched_fully=False,
            )
        except ApiError as error:
            show_action_error(error)
        else:
            st.session_state[sent_key] = True
            slot.success("¡Gracias! Tu calificación llegó a tu instructor sin tu nombre.")


with left:
    _video_block()

    if content.explanation is not None:
        render_explanation(
            explanation_text(content.explanation.content),
            source_note=source_note(content.explanation),
        )
    else:
        st.caption(NO_EXPLANATION_NOTE)
    if content.personal_example:
        st.markdown(f"**{content.personal_example.get('title', 'Ejemplo para ti')}**")
        st.markdown(str(content.personal_example.get("body", "")))

rules, attempts = content.quiz_rules, content.attempts
# Un quiz empezado y sin enviar se retoma: pedir otro intento daría 409 ATTEMPT_IN_PROGRESS (B-024).
action = enrollment.next_action
open_attempt_id = (
    action.attempt_id if action.type == "continue_attempt" and action.step_id == step_id else None
)


def _start_quiz(step_id: int) -> None:
    try:
        created = client.create_attempt(
            enrollment.id,
            step_id,
            "topic",
            idempotency_key=idempotency_key(f"attempt-{enrollment.id}-{step_id}-{attempts.used}"),
        )
    except ApiError as error:
        if error.code != "ATTEMPT_IN_PROGRESS":
            show_action_error(error)
            return
        # Hay un intento abierto que esta página no conocía: la API dice a dónde ir.
        go_to_action(client.get_enrollment(enrollment.id).next_action)
        return
    state.step_id = step_id
    if isinstance(created, Attempt):
        state.attempt_id = created.id
        state.quiz_job_id = None
    else:
        state.quiz_job_id = created.job_id
        state.quiz_job_kind = "prepare"
    st.switch_page(QUIZ_PAGE)


if reviewing:
    # Repaso: sin tarjeta del quiz ni intentos nuevos (la API los rechaza con 409).
    with right, st.container(key="card-topic-review"):
        eyebrow(REVIEW_LABEL.upper())
        note = CLOSED_NOTES.get(content.status or "", DEFAULT_CLOSED_NOTE)
        st.caption(f"{note} Puedes repasar la explicación y el video cuando quieras.")
        if st.button("Volver a mi ruta", key="topic-back"):
            st.switch_page(PATH_PAGE)
    st.stop()

with right, st.container(key="card-quiz-entry"):
    eyebrow("QUIZ DEL TEMA")
    st.markdown("**Cuando termines, presenta el quiz**")
    st.caption(f"{rules.items_per_attempt} preguntas, de opción múltiple y de respuesta corta.")
    total = attempts.max + attempts.extra_granted
    st.caption(
        f"Apruebas con {round(rules.pass_threshold)} %. Este es tu intento "
        f"{min(attempts.used + 1, total)} de {total}."
    )
    st.caption("Durante el quiz no verás el video ni la explicación. Respóndelo sin ayuda de IA.")
    if open_attempt_id is not None:
        if st.button("Continuar quiz", type="primary", key="topic-continue-quiz"):
            state.step_id, state.attempt_id, state.quiz_job_id = step_id, open_attempt_id, None
            st.switch_page(QUIZ_PAGE)
    elif attempts.remaining <= 0:
        st.warning("Usaste todos los intentos de este tema.")
        if st.button("Ver el estado de este tema", key="topic-exhausted"):
            state.attempt_id = None
            st.switch_page(RESULT_PAGE)
    elif st.button("Empezar quiz", type="primary", key="topic-start-quiz"):
        _start_quiz(step_id)
