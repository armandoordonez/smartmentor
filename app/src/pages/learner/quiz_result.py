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
from core.learner_flow import current_enrollment, go_to_action
from core.learner_state import PendingAttempt
from core.session import get_session
from services.assessment import rubric_view
from services.content import explanation_text, explanation_title, source_note
from services.learning import passed_next_label

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


def _route_row(index: int, label: str, color: str, text: str) -> None:
    """Una fila de «Qué pasa con tu ruta»: insignia y texto en una línea (V-047)."""
    with st.container(horizontal=True, vertical_alignment="center", key=f"route-row-{index}"):
        st.badge(label, color=color)  # type: ignore[arg-type]
        st.markdown(text)


def _exhausted(content: StepContent, path: PathDetail) -> None:
    """E7c · Intentos agotados."""
    total = content.attempts.max + content.attempts.extra_granted
    # Temas que se pueden seguir sin este: los que la API no dejó «en espera» (B-059). Si todos
    # dependen del agotado no hay nada que prometer ni acción para continuar.
    can_continue = [
        s for s in path.steps if s.step_id != step_id and s.status in ("pending", "in_progress")
    ]
    waiting = [s for s in path.steps if s.status == "on_hold"]
    alert = (
        f"{content.topic.name} queda marcado como tema crítico. Tu instructor ya recibió una "
        "alerta y puede habilitarte nuevos intentos."
    )
    render_page_header(
        f"Usaste los {total} intentos de este tema",
        breadcrumb=_breadcrumb(content, path),
        caption=(
            f"{alert} Mientras tanto, puedes seguir con los temas que no dependen de este."
            if can_continue
            else f"{alert} Tu ruta queda en espera hasta que decida."
        ),
    )
    try:
        history = client.list_attempt_history(enrollment.id, step_id)
    except ApiError as error:
        show_action_error(error)
        history = []
    history_col, route_col = st.columns(2)
    with history_col:
        render_attempt_history(
            [AttemptRow(h.number, h.score, h.correct, h.total, h.extra_grant) for h in history],
            key="topic",
            pass_threshold=content.quiz_rules.pass_threshold,
            exhausted=True,
        )
    with route_col, st.container(key="card-attempts-route"):
        st.subheader("Qué pasa con tu ruta", anchor=False)
        rows = [("Puedes seguir", "green", s.name) for s in can_continue]
        if waiting:
            rows.append(
                ("En espera", "gray", f"Temas que tienen {content.topic.name} como prerrequisito")
            )
        rows.append(
            (
                "En espera",
                "gray",
                f"Evaluación final: se habilita al aprobar los {len(path.steps)} temas",
            )
        )
        for index, (label, color, text) in enumerate(rows):
            _route_row(index, label, color, text)
    with st.container(key="card-attempts-resources"):
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

stems = {item.item_id: item for item in attempt.items}
correct = sum(1 for a in result.answers if a.grading.get("is_correct"))
score = percent_points(result.score)
threshold = percent_points(result.pass_threshold)
used, maximum = result.attempts.used, result.attempts.max


def _review() -> None:
    with st.container(key="card-review"):
        st.subheader("Revisión de respuestas", anchor=False)
        for number, answer in enumerate(result.answers, start=1):
            item = stems.get(answer.item_id)
            stem = item.stem if item else f"Pregunta {number}"
            is_short = answer.grading.get("item_type") == "short_answer"
            ok = bool(answer.grading.get("is_correct"))
            feedback = None if ok or is_short else str(answer.grading.get("feedback", "")) or None
            render_answer_review(
                number=number,
                stem=f"{stem} · Respuesta corta" if is_short else stem,
                correct=ok,
                explanation=feedback,
            )
            if is_short and (view := rubric_view(answer.grading)):
                render_rubric_result(view, key=f"answer-{answer.attempt_answer_id}")
                if not answer.review_requested and st.button(
                    "Pedir revisión del instructor",
                    type="tertiary",
                    key=f"request-review-{answer.attempt_answer_id}",
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
        if st.button(passed_next_label(result.next_action), type="primary", key="result-next"):
            go_to_action(result.next_action)
    st.stop()

# Solo sin aprobar: un tema aprobado queda `passed` y la API ya no entrega su contenido.
content, path = _load_context()
if result.next_action.type == "wait_instructor" or result.attempts.remaining <= 0:
    _exhausted(content, path)
    st.stop()

# E7b · Quiz no aprobado (refuerzo)
explanation = content.explanation
# La API aún no genera la explicación alterna (B-049): solo se promete si llegó en los datos.
has_alternate = explanation is not None and explanation.resource_id == result.remedial_resource_id
render_page_header(
    "Aún no apruebas este tema",
    breadcrumb=_breadcrumb(content, path),
    caption=(
        f"Obtuviste {score} ({correct} de {len(result.answers)}) en el intento {used} de "
        f"{maximum}. Necesitas {threshold}. No pasa nada: "
        + (
            "te mostramos otra forma de verlo y el próximo intento trae preguntas nuevas."
            if has_alternate
            else "el próximo intento trae preguntas nuevas."
        )
    ),
)
review_col, alternate_col = st.columns([3, 2])
with review_col:
    _review()
with alternate_col:
    if explanation is not None and has_alternate:
        with st.container(key="card-alt-view"):
            eyebrow("OTRA FORMA DE VERLO · GENERADO CON IA")
            st.markdown(f"**{explanation_title(explanation)}**")
            st.markdown(explanation_text(explanation.content))
            st.caption(source_note(explanation, alternate=True))
with st.container(key="card-next-attempt"):
    with st.container(horizontal=True, vertical_alignment="center", key="attempts-title-next"):
        st.markdown("**Tu próximo intento**")
        st.badge(f"Intento {used + 1} de {maximum}", color="blue")
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
        # B-060: pedir el intento puede tardar (si hay que generar preguntas). Se pide en la
        # página del quiz, con U1b ya en pantalla, y no aquí con E7b congelada en «Cargando…».
        state.step_id, state.attempt_id, state.quiz_job_id = step_id, None, None
        state.pending_attempt = PendingAttempt(
            key=f"attempt-{enrollment.id}-{step_id}-{used}", number=used + 1
        )
        st.switch_page(QUIZ_PAGE)
