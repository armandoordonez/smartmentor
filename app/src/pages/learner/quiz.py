"""E6b y E6c · Quiz del tema (opción múltiple y respuesta corta), U1b y U1c · Carga.

Una pregunta a la vez, con guardado parcial. «Enviar quiz» entrega el intento: la API califica de
inmediato si todo es de opción múltiple o responde con un trabajo de IA (U1c) si hay respuesta
corta. U1b espera las preguntas nuevas de un reintento. Si el trabajo falla se ofrece reintentar y
se conserva lo respondido.
"""

import streamlit as st

from clients.base import ApiError
from clients.models import AssessmentItem, Attempt, AttemptResult, LearnerAnswer
from components.layout import render_page_header
from core.container import get_client
from core.errors import show_action_error
from core.learner_flow import (
    JobScreen,
    current_enrollment,
    idempotency_key,
    wait_for_job,
)
from core.question_flow import render_question_sheet
from core.session import get_session
from services.learning import bloom_label

PAGE = "pages/learner/quiz.py"
TOPIC_PAGE = "pages/learner/topic.py"
RESULT_PAGE = "pages/learner/quiz_result.py"
PATH_PAGE = "pages/learner/path.py"
MC_NOTE = "Tutor IA desactivado durante el quiz"
SA_NOTE = "Responde sin ayuda de IA."

client = get_client()
state = get_session().learner
enrollment = current_enrollment(client)

step_id = state.step_id or enrollment.next_action.step_id
if step_id is None:
    st.switch_page(PATH_PAGE)
    st.stop()

try:
    content = client.get_step_content(enrollment.id, step_id)
    path = client.get_path(enrollment.id)
except ApiError as error:
    show_action_error(error)
    st.stop()

total_attempts = content.attempts.max + content.attempts.extra_granted
attempt_number = min(content.attempts.used + 1, total_attempts)
step = next((s for s in path.steps if s.step_id == step_id), None)
position = f"Tema {step.step_order} de {len(path.steps)}" if step else ""
breadcrumb = f"{enrollment.learning_path.name} › {position}"


def _prepare() -> None:
    """Pide de nuevo las preguntas del intento (reintento de U1b)."""
    if step_id is None:
        return
    try:
        created = client.create_attempt(
            enrollment.id,
            step_id,
            "topic",
            idempotency_key=idempotency_key(f"attempt-{enrollment.id}-{step_id}", fresh=True),
        )
    except ApiError as error:
        show_action_error(error)
        return
    if isinstance(created, Attempt):
        state.attempt_id, state.quiz_job_id = created.id, None
    else:
        state.quiz_job_id, state.quiz_job_kind = created.job_id, "prepare"
    st.rerun()


def _regrade() -> None:
    """Entrega de nuevo el intento (reintento de U1c)."""
    if state.attempt_id is None:
        return
    try:
        sent = client.submit_attempt(
            state.attempt_id,
            idempotency_key=idempotency_key(f"submit-{state.attempt_id}", fresh=True),
        )
    except ApiError as error:
        show_action_error(error)
        return
    if not isinstance(sent, AttemptResult):
        state.quiz_job_id = sent.job_id
    st.rerun()


# --- U1b y U1c · Carga ---------------------------------------------------------------------------

if state.quiz_job_id:
    if state.quiz_job_kind == "prepare":
        screen = JobScreen(
            key="quiz-prepare",
            title=f"Preparando preguntas nuevas para tu intento {attempt_number}",
            steps=(
                f"Revisar lo que fallaste en el intento {max(attempt_number - 1, 1)}",
                f"Generar {content.quiz_rules.items_per_attempt} preguntas nuevas con los mismos "
                "resultados de aprendizaje",
                "Verificar que cada pregunta tenga una sola respuesta correcta",
            ),
            error_message="No pudimos preparar las preguntas nuevas. Tu avance está guardado.",
        )
        job = wait_for_job(client, state.quiz_job_id, screen, on_retry=_prepare)
        if job is None:
            st.stop()
        state.quiz_job_id = None
        if job.next_action and job.next_action.attempt_id:
            state.attempt_id = job.next_action.attempt_id
        st.rerun()
    else:
        screen = JobScreen(
            key="quiz-grade",
            title="Calificando tu respuesta corta",
            steps=(
                "Calificar las preguntas de opción múltiple",
                "Aplicar la rúbrica de 3 criterios a tu respuesta corta",
                "Preparar tu retroalimentación",
            ),
            error_message=(
                "No pudimos calificar tu respuesta corta. Tus respuestas están guardadas."
            ),
        )
        job = wait_for_job(client, state.quiz_job_id, screen, on_retry=_regrade)
        if job is None:
            st.stop()
        state.quiz_job_id = None
        if job.next_action and job.next_action.attempt_id:
            state.attempt_id = job.next_action.attempt_id
        st.switch_page(RESULT_PAGE)

# --- E6b y E6c · Preguntas -----------------------------------------------------------------------

attempt_id = state.attempt_id or (
    enrollment.next_action.attempt_id if enrollment.next_action.type == "continue_attempt" else None
)
if attempt_id is None:
    st.switch_page(TOPIC_PAGE)
    st.stop()
state.attempt_id = attempt_id

try:
    attempt = client.get_attempt(attempt_id)
except ApiError as error:
    show_action_error(error)
    st.stop()

state.sheet.load(f"attempt-{attempt.id}", attempt.answers, len(attempt.items))
number = min(state.sheet.index, max(len(attempt.items) - 1, 0)) + 1

st.caption(
    f"Quiz del tema · Sin ayuda de IA ni apuntes. Apruebas con "
    f"{round(content.quiz_rules.pass_threshold)} %. Intento {attempt_number} de {total_attempts}."
)
render_page_header(
    f"Quiz: {content.topic.name}",
    breadcrumb=f"{breadcrumb} · Pregunta {number} de {len(attempt.items)}",
)


def _context(item: AssessmentItem) -> str | None:
    if item.item_type == "short_answer":
        return "Respuesta corta"
    bloom = bloom_label(item)
    return f"Bloom · {bloom}" if bloom else None


def _notes(item: AssessmentItem) -> tuple[str, ...]:
    return (MC_NOTE,) if item.item_type == "multiple_choice" else (SA_NOTE,)


def _save(answers: list[LearnerAnswer]) -> None:
    client.save_attempt_answers(attempt.id, answers)


def _submit(_answers: list[LearnerAnswer]) -> None:
    sent = client.submit_attempt(
        attempt.id, idempotency_key=idempotency_key(f"submit-{attempt.id}")
    )
    if isinstance(sent, AttemptResult):
        st.switch_page(RESULT_PAGE)
    state.quiz_job_id, state.quiz_job_kind = sent.job_id, "grade"


render_question_sheet(
    attempt.items,
    state.sheet,
    key="quiz",
    save=_save,
    submit=_submit,
    submit_label="Enviar quiz",
    notes=_notes,
    context=_context,
    hint="Responde en 2 a 4 frases.",
)
