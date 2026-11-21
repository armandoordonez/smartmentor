"""E9 · Repaso dirigido y E9c · Evaluación final con intentos agotados.

Si la final se aprobó, se sigue el `next_action`: con `answer_survey` o `view_badge` lleva al badge
(E10), que ofrece la encuesta como tarjeta opcional (B-045). Si no, esta página
lista los temas débiles (`review-plan`) y ofrece reintentar con preguntas nuevas; sin intentos
(`attempts.remaining = 0`) muestra el historial y avisa que el instructor ya recibió una alerta.

Si hay un intento abierto o calificándose (`continue_attempt`, el intento recién creado o un `409
ATTEMPT_NOT_GRADED`), abre E8 directamente: no hay pantalla intermedia ni se pide el resultado de
un intento sin calificar (B-041, B-050).
"""

from typing import NoReturn

import streamlit as st

from clients.base import ApiError
from clients.models import Attempt, AttemptResult, PathDetail, ReviewPlan
from components.attempt_history import AttemptRow, render_attempt_history
from components.formatting import percent_points
from components.layout import render_page_header
from core.container import get_client
from core.errors import show_action_error
from core.learner_flow import current_enrollment, go_to_action, idempotency_key
from core.session import get_session

PATH_PAGE = "pages/learner/path.py"
TOPIC_PAGE = "pages/learner/topic.py"
FINAL_PAGE = "pages/learner/final_assessment.py"
SURVEY_PAGE = "pages/learner/final_survey.py"
OPEN_ATTEMPT = "Tu evaluación final sigue abierta: retómala donde la dejaste y entrégala."

client = get_client()
state = get_session().learner
enrollment = current_enrollment(client)
action = enrollment.next_action

attempt_id = state.final_attempt_id or (
    action.attempt_id if action.type == "review_final" else None
)
if attempt_id is None:
    st.switch_page(PATH_PAGE)
    st.stop()


def _open_in_e8(open_attempt_id: int, job_id: object = None) -> NoReturn:
    """Abre E8 con el intento abierto (o su calificación en curso) sin pasar por otra pantalla."""
    state.final_attempt_id = state.pending_final_attempt_id = open_attempt_id
    if isinstance(job_id, str):  # ya se entregó: E8 muestra la calificación en curso
        state.quiz_job_id, state.quiz_job_kind = job_id, "final-grade"
    st.switch_page(FINAL_PAGE)
    st.stop()


def _continue_open_attempt(open_attempt_id: int, error: ApiError) -> NoReturn:
    """E9 con un intento sin calificar: lleva a E8 (preguntas o U1d) sin pantalla intermedia.

    Solo si el intento sigue abierto o tiene un trabajo de calificación; si no, E8 volvería aquí
    y no habría salida, así que se avisa y se ofrece volver a la ruta.
    """
    job_id = error.extra.get("job_id")
    if isinstance(job_id, str):
        _open_in_e8(open_attempt_id, job_id)
    try:
        is_open = client.get_attempt(open_attempt_id).status in ("created", "in_progress")
    except ApiError as attempt_error:
        show_action_error(attempt_error)
        st.stop()
    if is_open:
        _open_in_e8(open_attempt_id)
    render_page_header("Evaluación final", breadcrumb=enrollment.learning_path.name)
    st.info(OPEN_ATTEMPT)
    if st.button("Volver a mi ruta", key="final-open-back"):
        st.switch_page(PATH_PAGE)
    st.stop()


# Un intento abierto (o el recién creado por «Reintentar») se retoma en E8: no tiene resultado
# todavía y pedirlo respondería 409 (B-050). La API lo dice con `continue_attempt`; E9 también
# recuerda el intento que acaba de crear por si la inscripción leída está atrasada (B-041).
state.awaiting_final_questions = False
if action.type == "continue_attempt" and action.attempt_id is not None and action.step_id is None:
    _open_in_e8(action.attempt_id)
if state.pending_final_attempt_id is not None:
    _open_in_e8(state.pending_final_attempt_id)

try:
    result: AttemptResult = client.get_attempt_result(attempt_id)
except ApiError as error:
    if error.code != "ATTEMPT_NOT_GRADED":
        show_action_error(error)
        st.stop()
    _continue_open_attempt(attempt_id, error)
try:
    path: PathDetail = client.get_path(enrollment.id)
    plan: ReviewPlan = client.get_review_plan(enrollment.id)
except ApiError as error:
    show_action_error(error)
    st.stop()

if result.passed:
    go_to_action(result.next_action)
    st.stop()

threshold = percent_points(result.pass_threshold)
step_by_topic = {step.topic_id: step for step in path.steps}


def _review(step_topic_id: int) -> None:
    step = step_by_topic.get(step_topic_id)
    if step is not None:
        state.step_id = step.step_id
        st.switch_page(TOPIC_PAGE)


if result.attempts.remaining <= 0:
    # E9c · Intentos agotados
    try:
        history = client.list_attempt_history(enrollment.id, None)
    except ApiError as error:
        show_action_error(error)
        history = []
    best = max((h.score for h in history), default=result.score)
    render_page_header(
        f"Usaste los {result.attempts.max} intentos de la evaluación final",
        breadcrumb=f"{enrollment.learning_path.name} › Evaluación final",
        caption=(
            f"Tu mejor resultado fue {percent_points(best)} y el badge requiere {threshold}. "
            f"Tus {len(path.steps)} temas siguen aprobados. Tu instructor ya recibió una alerta "
            "y puede habilitarte un nuevo intento después de un repaso."
        ),
    )
    history_col, topics_col = st.columns(2)
    with history_col:
        render_attempt_history(
            [AttemptRow(h.number, h.score, h.correct, h.total, h.extra_grant) for h in history],
            key="final",
            pass_threshold=result.pass_threshold,
            threshold_goal="obtener el badge",
            exhausted=True,
        )
    with topics_col, st.container(key="card-attempts-weak"):
        st.subheader("Temas a repasar", anchor=False)
        for topic in plan.weak_topics:
            name_col, score_col = st.columns([5, 1])
            name_col.markdown(topic.name)
            score_col.markdown(
                f":orange[**{percent_points(topic.score)}**]", text_alignment="right"
            )
        st.caption(
            f"Promedio de las preguntas de cada tema en tus {result.attempts.used} intentos."
        )
    with st.container(horizontal=True):
        if st.button("Volver a mi ruta", key="final-back"):
            st.switch_page(PATH_PAGE)
        if plan.weak_topics and st.button(
            "Repasar temas débiles", type="primary", key="final-review-all"
        ):
            _review(plan.weak_topics[0].topic_id)
    st.stop()

# E9 · Repaso dirigido
render_page_header(
    "Aún no alcanzas el badge",
    caption=(
        f"Obtuviste {percent_points(result.score)} en la evaluación final; necesitas "
        f"{threshold}. Repasa los temas débiles y vuelve a intentar con preguntas nuevas."
    ),
)
# Una sola tarjeta con una fila por tema, como en Figma (V-088 a V-096).
with st.container(key="card-weak-topics"):
    st.subheader("Temas a repasar", anchor=False)
    for topic in plan.weak_topics:
        name_col, score_col, action_col = st.columns([5, 1, 2], vertical_alignment="center")
        name_col.markdown(topic.name)
        score_col.markdown(f":orange[**{percent_points(topic.score)}**]", text_alignment="right")
        if action_col.button("Repasar tema", key=f"review-topic-{topic.topic_id}"):
            _review(topic.topic_id)
st.caption(
    f"Intento {result.attempts.used} de {result.attempts.max} usado. El próximo intento trae "
    "preguntas nuevas sobre los mismos resultados de aprendizaje."
)
if st.button("Reintentar evaluación final", type="primary", key="final-retry"):
    try:
        created = client.create_final_attempt(
            enrollment.id,
            idempotency_key=idempotency_key(f"final-{enrollment.id}-retry", fresh=True),
        )
    except ApiError as error:
        show_action_error(error)
    else:
        if isinstance(created, Attempt):
            # E8 abre este intento aunque la inscripción aún diga `review_final` (B-041).
            state.final_attempt_id = state.pending_final_attempt_id = created.id
        else:  # no quedan preguntas sin ver: E8 muestra la carga mientras se generan (B-011)
            state.final_attempt_id = None
            state.awaiting_final_questions = True  # la inscripción sigue en `review_final`
            state.quiz_job_id, state.quiz_job_kind = created.job_id, "final-prepare"
        st.switch_page(FINAL_PAGE)
with st.container(key="card-survey"):
    st.markdown("**Encuesta final · opcional**")
    st.caption("Ayúdanos a mejorar SmartMentor en unos 3 minutos. No afecta tu badge.")
    if st.button("Responder encuesta", type="primary", key="final-survey"):
        st.switch_page(SURVEY_PAGE)
