"""E9 · Repaso dirigido y E9c · Evaluación final con intentos agotados.

Si la final se aprobó, la API manda al badge o a la encuesta (`next_action`). Si no, esta página
lista los temas débiles (`review-plan`) y ofrece reintentar con preguntas nuevas; sin intentos
(`attempts.remaining = 0`) muestra el historial y avisa que el instructor ya recibió una alerta.
"""

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

try:
    result: AttemptResult = client.get_attempt_result(attempt_id)
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
    render_attempt_history(
        [AttemptRow(h.number, h.score, h.correct, h.total, h.extra_grant) for h in history],
        key="final",
        pass_threshold=result.pass_threshold,
        exhausted=True,
    )
    st.caption(f"Necesitas {threshold} para obtener el badge.")
    st.subheader("Temas a repasar", anchor=False)
    for topic in plan.weak_topics:
        name_col, score_col = st.columns([5, 1])
        name_col.markdown(topic.name)
        score_col.markdown(f"**{percent_points(topic.score)}**")
    st.caption(f"Promedio de las preguntas de cada tema en tus {result.attempts.used} intentos.")
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
st.subheader("Temas a repasar", anchor=False)
for topic in plan.weak_topics:
    with st.container(border=True, key=f"panel-weak-{topic.topic_id}"):
        name_col, score_col, action_col = st.columns([5, 1, 2], vertical_alignment="center")
        name_col.markdown(f"**{topic.name}**")
        score_col.markdown(f"**{percent_points(topic.score)}**")
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
            state.final_attempt_id = created.id
        else:  # no quedan preguntas sin ver: E8 muestra la carga mientras se generan (B-011)
            state.final_attempt_id = None
            state.quiz_job_id, state.quiz_job_kind = created.job_id, "final-prepare"
        st.switch_page(FINAL_PAGE)
with st.container(key="card-survey"):
    st.markdown("**Encuesta final · opcional**")
    st.caption("Ayúdanos a mejorar SmartMentor en unos 3 minutos. No afecta tu badge.")
    if st.button("Responder encuesta", key="final-survey"):
        st.switch_page(SURVEY_PAGE)
