"""E8 · Evaluación final y U1d · Calificando la evaluación final.

Se llega por `take_final` (crea el intento con `POST …/final-attempts`) o `continue_attempt`
(retoma uno abierto). Una pregunta a la vez con guardado parcial; si hay respuesta corta la API
responde con un trabajo de IA (U1d) y, si falla, se conserva lo respondido.

En un reintento sin preguntas no vistas la API responde `202` y genera más (B-011): se muestra la
misma carga que en el quiz y, al terminar, se pide otra vez el intento con una clave nueva (la
anterior repetiría el `202`).
"""

import streamlit as st

from clients.base import ApiError
from clients.models import (
    AssessmentItem,
    Attempt,
    AttemptResult,
    LearnerAnswer,
    NextActionType,
)
from components.layout import render_page_header
from core.container import get_client
from core.errors import show_action_error
from core.learner_flow import (
    JobScreen,
    current_enrollment,
    idempotency_key,
    redirect_unless,
    wait_for_job,
)
from core.question_flow import render_question_sheet
from core.session import get_session
from services.learning import bloom_label

PAGE = "pages/learner/final_assessment.py"
RESULT_PAGE = "pages/learner/final_result.py"
BANNER = (
    "Evaluación final · Sin ayuda de IA ni apuntes · Preguntas generadas con IA a partir de los "
    "resultados de aprendizaje y revisadas por tu instructor"
)
GRADING = JobScreen(
    key="final-grade",
    title="Calificando tu respuesta corta",
    steps=(
        "Calificar las preguntas de opción múltiple",
        "Aplicar la rúbrica de 3 criterios a tu respuesta corta",
        "Preparar tu retroalimentación",
    ),
    error_message="No pudimos calificar tu respuesta corta. Tus respuestas están guardadas.",
)

PREPARE = JobScreen(
    key="final-prepare",
    title="Preparando preguntas nuevas para tu evaluación final",
    steps=(
        "Revisar las preguntas que ya respondiste",
        "Generar preguntas nuevas con los mismos resultados de aprendizaje",
        "Verificar que cada pregunta tenga una sola respuesta correcta",
    ),
    error_message="No pudimos preparar las preguntas nuevas. Tu avance está guardado.",
)

client = get_client()
state = get_session().learner
enrollment = current_enrollment(client)
allowed: set[NextActionType] = {"take_final", "continue_attempt", "wait_job"}
if state.quiz_job_id and state.quiz_job_kind == "final-prepare":
    allowed.add("review_final")  # el reintento desde E9 espera preguntas nuevas (B-011)
action = redirect_unless(enrollment, allowed, PAGE)
if action.type == "wait_job" and action.job_id:
    state.quiz_job_id, state.quiz_job_kind = action.job_id, "final-grade"


def _regrade() -> None:
    if state.final_attempt_id is None:
        return
    try:
        sent = client.submit_attempt(
            state.final_attempt_id,
            idempotency_key=idempotency_key(f"submit-{state.final_attempt_id}", fresh=True),
        )
    except ApiError as error:
        show_action_error(error)
        return
    if not isinstance(sent, AttemptResult):
        state.quiz_job_id = sent.job_id
    st.rerun()


def _new_final_request() -> None:
    """Después de generar (o para reintentar), el intento se pide con una clave nueva."""
    state.quiz_job_id = None
    idempotency_key(f"final-{enrollment.id}", fresh=True)
    st.rerun()


# --- Preparando preguntas nuevas (reintento sin preguntas no vistas, B-011) ---------------------

if state.quiz_job_id and state.quiz_job_kind == "final-prepare":
    if wait_for_job(client, state.quiz_job_id, PREPARE, on_retry=_new_final_request) is None:
        st.stop()
    _new_final_request()

# --- U1d · Calificando la evaluación final -------------------------------------------------------

if state.quiz_job_id and state.quiz_job_kind == "final-grade":
    job = wait_for_job(client, state.quiz_job_id, GRADING, on_retry=_regrade)
    if job is None:
        st.stop()
    state.quiz_job_id = None
    if job.next_action and job.next_action.attempt_id:
        state.final_attempt_id = job.next_action.attempt_id
    st.switch_page(RESULT_PAGE)

# --- E8 · Preguntas ------------------------------------------------------------------------------

try:
    if state.final_attempt_id is not None:
        attempt: Attempt = client.get_attempt(state.final_attempt_id)
    elif action.type == "continue_attempt" and action.attempt_id is not None:
        attempt = client.get_attempt(action.attempt_id)
    else:
        created = client.create_final_attempt(
            enrollment.id, idempotency_key=idempotency_key(f"final-{enrollment.id}")
        )
        if not isinstance(created, Attempt):
            state.quiz_job_id, state.quiz_job_kind = created.job_id, "final-prepare"
            st.rerun()
        attempt = created
    path = client.get_path(enrollment.id)
except ApiError as error:
    show_action_error(error)
    st.stop()

state.final_attempt_id = attempt.id
state.sheet.load(f"attempt-{attempt.id}", attempt.answers, len(attempt.items))
number = min(state.sheet.index, max(len(attempt.items) - 1, 0)) + 1
final = path.final
attempt_number = min(final.attempts_used + 1, final.max_attempts)

st.caption(BANNER)
render_page_header(
    "Evaluación final",
    caption=(
        f"{enrollment.learning_path.name} · Pregunta {number} de {len(attempt.items)} · "
        f"Intento {attempt_number} de {final.max_attempts}"
    ),
)


def _context(item: AssessmentItem) -> str | None:
    bloom = bloom_label(item)
    return f"Bloom · {bloom}" if bloom else None


def _save(answers: list[LearnerAnswer]) -> None:
    client.save_attempt_answers(attempt.id, answers)


def _submit(_answers: list[LearnerAnswer]) -> None:
    sent = client.submit_attempt(
        attempt.id, idempotency_key=idempotency_key(f"submit-{attempt.id}")
    )
    if isinstance(sent, AttemptResult):
        st.switch_page(RESULT_PAGE)
    state.quiz_job_id, state.quiz_job_kind = sent.job_id, "final-grade"


render_question_sheet(
    attempt.items,
    state.sheet,
    key="final",
    save=_save,
    submit=_submit,
    submit_label="Enviar evaluación",
    notes=("Tutor IA desactivado durante la evaluación",),
    context=_context,
    hint="Responde en 2 a 4 frases.",
)
