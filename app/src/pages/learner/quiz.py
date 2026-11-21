"""E6b y E6c · Quiz del tema (opción múltiple y respuesta corta), U1b y U1c · Carga.

Una pregunta a la vez, con guardado parcial. «Enviar quiz» entrega el intento: la API califica de
inmediato si todo es de opción múltiple o responde con un trabajo de IA (U1c) si hay respuesta
corta. U1b espera las preguntas nuevas de un reintento. Si el trabajo falla se ofrece reintentar y
se conserva lo respondido.
"""

import streamlit as st

from clients.base import ApiError
from clients.models import AssessmentItem, Attempt, AttemptResult, LearnerAnswer
from components.layout import render_notice, render_page_header
from core.container import get_client
from core.errors import show_action_error
from core.learner_flow import (
    JobScreen,
    current_enrollment,
    draw_waiting,
    go_to_action,
    grading_screen,
    idempotency_key,
    wait_for_job,
)
from core.polling import CREATING_ATTEMPT, enter_wait_mode, leave_wait_mode
from core.question_flow import SHORT_ANSWER_HINT, render_question_sheet
from core.session import get_session
from core.usage_events import build_event, close_view, open_view, record_once
from services.learning import bloom_label

PAGE = "pages/learner/quiz.py"
TOPIC_PAGE = "pages/learner/topic.py"
RESULT_PAGE = "pages/learner/quiz_result.py"
PATH_PAGE = "pages/learner/path.py"
FINAL_PAGE = "pages/learner/final_assessment.py"
OPEN_STATUSES = frozenset({"created", "in_progress"})
MC_NOTE = "Tutor IA desactivado durante el quiz"
SA_NOTE = "Responde sin ayuda de IA."

client = get_client()
state = get_session().learner
enrollment = current_enrollment(client)

# U1c al volver: la API manda esperar la calificación (`wait_job`) con el intento y el trabajo,
# pero sin el tema. El intento dice de qué tema es, o si es la evaluación final (U1d).
waiting = enrollment.next_action
if waiting.type == "wait_job" and waiting.attempt_id and waiting.job_id and not state.quiz_job_id:
    try:
        graded = client.get_attempt(waiting.attempt_id)
    except ApiError as error:
        show_action_error(error)
        st.stop()
    if graded.assessment_type == "final":
        state.final_attempt_id = graded.id
        st.switch_page(FINAL_PAGE)
        st.stop()
    state.step_id, state.attempt_id = graded.step_id, graded.id
    state.quiz_job_id, state.quiz_job_kind = waiting.job_id, "grade"

# --- U1c · Calificando ---------------------------------------------------------------------------
# Va antes de pedir el contenido del tema: si el quiz se aprueba, el tema queda `passed` y la API ya
# no entrega su contenido (`STEP_NOT_AVAILABLE`). Esta espera no lo necesita.


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


if state.quiz_job_id and state.quiz_job_kind == "grade":
    grading = grading_screen(
        client,
        key="quiz-grade",
        attempt_id=state.attempt_id,
        error_message="No pudimos calificar tu respuesta corta. Tus respuestas están guardadas.",
    )
    graded_job = wait_for_job(client, state.quiz_job_id, grading, on_retry=_regrade)
    if graded_job is None:
        st.stop()
    state.quiz_job_id = None
    if graded_job.next_action and graded_job.next_action.attempt_id:
        state.attempt_id = graded_job.next_action.attempt_id
    st.switch_page(RESULT_PAGE)
    st.stop()

# --- U1b · Pidiendo el intento de un reintento (B-060) -------------------------------------------
# E7b deja el reintento pedido y viene aquí: U1b se dibuja antes de llamar a la API, que puede
# tardar si tiene que generar preguntas. Si responde con un trabajo, sigue la espera de abajo.

requested = state.pending_attempt
if requested is not None and state.step_id is not None:
    draw_waiting(
        JobScreen(
            key="quiz-prepare",
            title=f"Preparando preguntas nuevas para tu intento {requested.number}",
            steps=(
                f"Revisar lo que fallaste en el intento {max(requested.number - 1, 1)}",
                "Elegir preguntas nuevas con los mismos resultados de aprendizaje",
                "Verificar que cada pregunta tenga una sola respuesta correcta",
            ),
            error_message="",
        )
    )
    enter_wait_mode(CREATING_ATTEMPT)
    try:
        created = client.create_attempt(
            enrollment.id,
            state.step_id,
            "topic",
            idempotency_key=idempotency_key(requested.key),
        )
    except ApiError as error:
        state.pending_attempt = None
        leave_wait_mode()
        if error.code == "ATTEMPT_IN_PROGRESS":
            # Ya hay un intento abierto: la API dice a dónde ir.
            go_to_action(client.get_enrollment(enrollment.id).next_action)
        show_action_error(error)
        st.stop()
    state.pending_attempt = None
    leave_wait_mode()
    if isinstance(created, Attempt):
        state.attempt_id, state.quiz_job_id = created.id, None
    else:
        state.quiz_job_id, state.quiz_job_kind = created.job_id, "prepare"
    st.rerun()

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


# --- U1b · Preparando preguntas nuevas -----------------------------------------------------------

if state.quiz_job_id and state.quiz_job_kind == "prepare":
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
    else:
        # La API no dice qué intento abrir: con las preguntas ya generadas, pedir el intento
        # de nuevo (con otra clave de idempotencia) lo crea.
        _prepare()
    st.rerun()

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

# Un intento ya enviado no se vuelve a responder (con «Atrás» del navegador se llegaba aquí y
# guardar daba 409, B-026): si se está calificando se espera; si no, se ve el resultado.
if attempt.status not in OPEN_STATUSES:
    pending = enrollment.next_action
    if pending.type == "wait_job" and pending.attempt_id == attempt.id and pending.job_id:
        state.quiz_job_id, state.quiz_job_kind = pending.job_id, "grade"
        st.rerun()
    st.switch_page(RESULT_PAGE)

state.sheet.load(f"attempt-{attempt.id}", attempt.answers, len(attempt.items))
number = min(state.sheet.index, max(len(attempt.items) - 1, 0)) + 1

# Tiempo en tarea (m27): `quiz.start` una vez por intento; cada visita a las preguntas es un tramo
# que se cierra con `quiz.submit` al entregar o con `quiz.pause` si sale sin entregar.
quiz_view = f"quiz:{attempt.id}"
quiz_payload = {
    "screen": "E6b",
    "attempt_id": attempt.id,
    "step_id": step_id,
    "attempt_number": attempt.attempt_number or attempt_number,
}
record_once(
    client,
    f"quiz.start:{attempt.id}",
    lambda: [
        build_event(enrollment.id, "quiz.start", topic_id=content.topic.id, payload=quiz_payload)
    ],
)
open_view(
    client,
    quiz_view,
    enrollment_id=enrollment.id,
    close_type="quiz.pause",
    topic_id=content.topic.id,
    payload=quiz_payload,
)

render_notice(
    f"Quiz del tema · Sin ayuda de IA ni apuntes. Apruebas con "
    f"{round(content.quiz_rules.pass_threshold)} %. Intento {attempt_number} de {total_attempts}."
)
current = attempt.items[min(state.sheet.index, len(attempt.items) - 1)] if attempt.items else None
if current is not None and current.item_type == "short_answer":
    # E6c: título único; la posición va en el chip «Pregunta n de N · Respuesta corta».
    render_page_header(
        "Quiz del tema",
        breadcrumb=f"{breadcrumb} · {content.topic.name} · Intento {attempt_number} de "
        f"{total_attempts}",
    )
else:
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
    graded = isinstance(sent, AttemptResult)
    close_view(
        client,
        quiz_view,
        event_type="quiz.submit",
        payload={"items": len(attempt.items), "grading": "done" if graded else "job"},
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
    hint=SHORT_ANSWER_HINT,
    card=True,
    notes_style="chip",
)
