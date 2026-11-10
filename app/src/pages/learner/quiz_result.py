"""E7, E7b y E7c · Resultado del quiz.

- E7: tema aprobado, con la revisión de respuestas y la rúbrica de la respuesta corta.
- E7b: tema no aprobado con intentos: explicación alterna y reintento con preguntas nuevas.
- E7c: intentos agotados: historial, qué pasa con la ruta y recursos de repaso.

Qué variante se muestra lo dicen los datos de la API (`passed`, `attempts.remaining` y el
`next_action` `wait_instructor`); la página no calcula aprobados ni intentos.
"""

import streamlit as st

from clients.base import ApiError
from clients.models import Attempt, AttemptResult, PathDetail, StepContent
from components.attempt_history import AttemptRow, render_attempt_history
from components.formatting import percent_points
from components.layout import eyebrow, render_page_header
from components.quiz_form import render_answer_review
from components.rubric_result import render_rubric_result
from core.container import get_client
from core.errors import show_action_error
from core.learner_flow import current_enrollment, go_to_action, idempotency_key
from core.session import get_session
from services.assessment import rubric_view
from services.content import explanation_text, explanation_title, source_note

PATH_PAGE = "pages/learner/path.py"
TOPIC_PAGE = "pages/learner/topic.py"
QUIZ_PAGE = "pages/learner/quiz.py"

client = get_client()
state = get_session().learner
enrollment = current_enrollment(client)
action = enrollment.next_action

step_id = state.step_id or action.step_id
attempt_id = state.attempt_id or (
    action.attempt_id if action.type == "view_attempt_result" else None
)


def _back_to_path() -> None:
    if st.button("Volver a mi ruta", key="result-back"):
        st.switch_page(PATH_PAGE)


def _load_context() -> tuple[StepContent, PathDetail]:
    if step_id is None:
        st.switch_page(PATH_PAGE)
    try:
        return client.get_step_content(enrollment.id, step_id), client.get_path(enrollment.id)
    except ApiError as error:
        show_action_error(error)
        st.stop()


def _breadcrumb(content: StepContent, path: PathDetail, *, topic: bool = True) -> str:
    step = next((s for s in path.steps if s.step_id == step_id), None)
    place = f"Tema {step.step_order} de {len(path.steps)}" if step else ""
    text = f"{enrollment.learning_path.name} › {place}"
    return f"{text} · {content.topic.name}" if topic else text


def _exhausted(content: StepContent, path: PathDetail) -> None:
    """E7c · Intentos agotados."""
    total = content.attempts.max + content.attempts.extra_granted
    render_page_header(
        f"Usaste los {total} intentos de este tema",
        breadcrumb=_breadcrumb(content, path),
        caption=(
            f"{content.topic.name} queda marcado como tema crítico. Tu instructor ya recibió una "
            "alerta y puede habilitarte nuevos intentos. Mientras tanto, puedes seguir con los "
            "temas que no dependen de este."
        ),
    )
    try:
        history = client.list_attempt_history(enrollment.id, step_id)
    except ApiError as error:
        show_action_error(error)
        history = []
    render_attempt_history(
        [AttemptRow(h.number, h.score, h.correct, h.total, h.extra_grant) for h in history],
        key="topic",
        pass_threshold=content.quiz_rules.pass_threshold,
        exhausted=True,
    )
    st.subheader("Qué pasa con tu ruta", anchor=False)
    can_continue = [
        s for s in path.steps if s.step_id != step_id and s.status in ("pending", "in_progress")
    ]
    waiting = [s for s in path.steps if s.status == "on_hold"]
    if can_continue:
        st.badge("Puedes seguir", color="green")
        for s in can_continue:
            st.markdown(s.name)
    if waiting:
        st.badge("En espera", color="orange")
        st.caption(f"Temas que tienen {content.topic.name} como prerrequisito")
    st.badge("En espera", color="orange")
    st.caption(f"Evaluación final: se habilita al aprobar los {len(path.steps)} temas")
    st.subheader("Recursos de repaso", anchor=False)
    if content.explanation is not None:
        st.markdown(f"•  Releer la explicación «{explanation_title(content.explanation)}»")
    if content.video is not None:
        st.markdown("•  Ver el video de respaldo curado por tu instructor")
    st.markdown(f"•  Revisar tus respuestas de los {len(history)} intentos")
    with st.container(horizontal=True):
        _back_to_path()
        if can_continue and st.button(
            f"Continuar con {can_continue[0].name}", type="primary", key="result-continue"
        ):
            state.step_id = can_continue[0].step_id
            st.switch_page(TOPIC_PAGE)


# --- Sin intento que mostrar: solo la variante E7c -----------------------------------------------

if attempt_id is None:
    content, path = _load_context()
    if action.type == "wait_instructor" or content.attempts.remaining <= 0:
        _exhausted(content, path)
        st.stop()
    st.switch_page(TOPIC_PAGE)
    st.stop()

try:
    result: AttemptResult = client.get_attempt_result(attempt_id)
    attempt: Attempt = client.get_attempt(attempt_id)
except ApiError as error:
    show_action_error(error)
    st.stop()

content, path = _load_context()
if not result.passed and (
    result.next_action.type == "wait_instructor" or result.attempts.remaining <= 0
):
    _exhausted(content, path)
    st.stop()

stems = {item.item_id: item for item in attempt.items}
correct = sum(1 for a in result.answers if a.grading.get("is_correct"))
score = percent_points(result.score)
threshold = percent_points(result.pass_threshold)
used, maximum = result.attempts.used, result.attempts.max


def _review() -> None:
    st.subheader("Revisión de respuestas", anchor=False)
    for number, answer in enumerate(result.answers, start=1):
        item = stems.get(answer.item_id)
        stem = item.stem if item else f"Pregunta {number}"
        is_short = answer.grading.get("item_type") == "short_answer"
        ok = bool(answer.grading.get("is_correct"))
        render_answer_review(
            number=number,
            stem=f"{stem} · Respuesta corta" if is_short else stem,
            correct=ok,
            explanation=None if ok or is_short else str(answer.grading.get("feedback", "")) or None,
        )
        if is_short and (view := rubric_view(answer.grading)):
            render_rubric_result(view, key=f"answer-{answer.attempt_answer_id}")
            if not answer.review_requested and st.button(
                "Pedir revisión del instructor", key=f"review-{answer.attempt_answer_id}"
            ):
                try:
                    client.request_answer_review(answer.attempt_answer_id, "")
                except ApiError as error:
                    show_action_error(error)
                else:
                    st.success("Listo: tu instructor revisará esta respuesta.")


if result.passed:
    # E7 · Tema aprobado
    render_page_header(
        "¡Tema aprobado!",
        caption=(
            f"Obtuviste {score} ({correct} de {len(result.answers)}) en el intento {used} de "
            f"{maximum}. El umbral es {threshold}. Tu avance quedó registrado."
        ),
    )
    _review()
    with st.container(horizontal=True):
        _back_to_path()
        if st.button("Siguiente tema", type="primary", key="result-next"):
            go_to_action(result.next_action)
    st.stop()

# E7b · Quiz no aprobado (refuerzo)
render_page_header(
    "Aún no apruebas este tema",
    breadcrumb=_breadcrumb(content, path),
    caption=(
        f"Obtuviste {score} ({correct} de {len(result.answers)}) en el intento {used} de "
        f"{maximum}. Necesitas {threshold}. No pasa nada: te mostramos otra forma de verlo y el "
        "próximo intento trae preguntas nuevas."
    ),
)
_review()
explanation = content.explanation
if explanation is not None and explanation.resource_id == result.remedial_resource_id:
    with st.container(key="card-alternate"):
        eyebrow("OTRA FORMA DE VERLO · GENERADO CON IA")
        st.markdown(f"**{explanation_title(explanation)}**")
        st.markdown(explanation_text(explanation.content))
        st.caption(source_note(explanation, alternate=True))
with st.container(key="card-next-attempt"):
    st.markdown("**Tu próximo intento**")
    st.markdown(f"**Intento {used + 1} de {maximum}**")
    st.markdown(
        f"•  {len(attempt.items)} preguntas nuevas sobre los mismos resultados de aprendizaje, "
        "no las mismas que ya viste."
    )
    st.markdown("•  Más peso en lo que fallaste.")
    st.markdown(
        f"•  Responde sin ayuda de IA. Si usas los {maximum} intentos, tu instructor verá este "
        "tema como crítico y podrá apoyarte."
    )
with st.container(horizontal=True):
    _back_to_path()
    if st.button("Reintentar con preguntas nuevas", type="primary", key="result-retry"):
        try:
            created = client.create_attempt(
                enrollment.id,
                step_id or 0,
                "topic",
                idempotency_key=idempotency_key(f"attempt-{enrollment.id}-{step_id}-{used}"),
            )
        except ApiError as error:
            show_action_error(error)
        else:
            if isinstance(created, Attempt):
                state.attempt_id, state.quiz_job_id = created.id, None
            else:
                state.quiz_job_id, state.quiz_job_kind = created.job_id, "prepare"
            st.switch_page(QUIZ_PAGE)
