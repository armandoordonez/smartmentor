"""Piezas comunes de las páginas del aprendiz: inscripción actual, navegación por `next_action`,
claves de idempotencia y la pantalla de espera de un trabajo de IA (U1a a U1d).

Nada de esto decide el estado de la inscripción: la API lo dice con `next_action` y aquí solo se
navega a la página que corresponde.
"""

import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass

import streamlit as st

from clients.base import ApiError, SmartMentorClient
from clients.jobs import is_done
from clients.models import Enrollment, Job, NextAction, NextActionType
from components.loading_steps import LoadingStep, StepState, render_loading_steps
from core.errors import is_global, show_action_error
from core.navigation import CATALOG, page_for_next_action
from core.polling import enter_wait_mode, leave_wait_mode
from core.session import get_session
from services.assessment import grading_rubric_step

POLL_SECONDS = 2
# Medido en los recorridos del 2026-11-15: preparar preguntas nuevas tardó unos 90 s (B-060).
ESTIMATE = "hasta 2 minutos"
PATH_PAGE = "pages/learner/path.py"
NO_ROUTE = "Todavía no tienes una ruta. Elige una en el catálogo."
# Inscripciones que siguen vivas (no terminadas ni abandonadas), para elegir la de por omisión.
OPEN_STATUSES = frozenset(
    {"enrolled", "profiling", "diagnosing", "objective_pending", "in_path", "final_ready"}
)


def idempotency_key(name: str, *, fresh: bool = False) -> str:
    """Clave estable entre reejecuciones del mismo botón; `fresh` la renueva (reintento)."""
    keys = get_session().idempotency_keys
    if fresh or name not in keys:
        keys[name] = str(uuid.uuid4())
    return keys[name]


def default_enrollment(items: Sequence[Enrollment]) -> Enrollment:
    """La inscripción por omisión: la más reciente en curso o, si no hay, la más reciente."""
    open_items = [e for e in items if e.status in OPEN_STATUSES]
    return max(open_items or items, key=lambda e: e.created_at)


def current_enrollment(client: SmartMentorClient) -> Enrollment:
    """La inscripción de la persona: la elegida o, si no hay, la más reciente en curso."""
    session = get_session()
    try:
        if session.selected_enrollment_id is not None:
            return client.get_enrollment(session.selected_enrollment_id)
        page = client.list_enrollments(limit=100)
    except ApiError as error:
        show_action_error(error)
        st.stop()
    if not page.items:
        st.info(NO_ROUTE)
        st.page_link(CATALOG, label="Ir al catálogo")
        st.stop()
    chosen = default_enrollment(page.items)
    session.selected_enrollment_id = chosen.id
    return chosen


def remember(action: NextAction) -> None:
    """Recuerda a dónde iba la persona (tema, intento, trabajo) antes de cambiar de página."""
    state = get_session().learner
    state.step_id = action.step_id
    state.attempt_id = action.attempt_id
    state.job_id = action.job_id


def go_to_action(action: NextAction) -> None:
    """Navega a la página del `next_action`; si todavía no existe, lo dice y se detiene."""
    remember(action)
    target = page_for_next_action(action)
    if target is None:
        st.info("La pantalla que sigue todavía no está disponible.")
        st.stop()
    leave_wait_mode()
    st.switch_page(target)


def redirect_unless(
    enrollment: Enrollment, allowed: set[NextActionType], current_page: str
) -> NextAction:
    """Si la API manda a otra pantalla, va allí. Devuelve el `next_action` vigente."""
    action = enrollment.next_action
    if action.type not in allowed:
        target = page_for_next_action(action)
        if target is not None and target != current_page:
            remember(action)
            leave_wait_mode()
            st.switch_page(target)
    return action


# --- Espera de un trabajo de IA ------------------------------------------------------------------


@dataclass(frozen=True)
class JobScreen:
    """Textos de una pantalla de carga: título, tres pasos y el mensaje si el trabajo falla."""

    key: str
    title: str
    steps: Sequence[str]
    error_message: str


def grading_screen(
    client: SmartMentorClient, *, key: str, attempt_id: int | None, error_message: str
) -> JobScreen:
    """Pantalla «Calificando tu respuesta corta» (U1c y U1d).

    El paso de la rúbrica dice cuántos criterios tiene la pregunta si el intento los informa; si no
    se puede leer el intento, el paso no lleva número. El paso se calcula una sola vez por intento
    (se guarda en la sesión): la pantalla se repite cada 2 s y no debe sumar una consulta por
    sondeo.
    """
    rubric_step = st.session_state.get(f"grading-rubric-step-{attempt_id}")
    if rubric_step is None:
        items = []
        if attempt_id is not None:
            try:
                items = client.get_attempt(attempt_id).items
            except ApiError:
                items = []
        rubric_step = grading_rubric_step(items)
        st.session_state[f"grading-rubric-step-{attempt_id}"] = rubric_step
    return JobScreen(
        key=key,
        title="Calificando tu respuesta corta",
        steps=(
            "Calificar las preguntas de opción múltiple",
            rubric_step,
            "Preparar tu retroalimentación",
        ),
        error_message=error_message,
    )


def _step_states(job: Job | None, polls: int, count: int) -> list[StepState]:
    """Estado visual de los pasos. La API no da los pasos: se estiman con el estado del trabajo."""
    if job is None or job.status == "queued":
        active = 0
    elif job.status == "running":
        active = min(1 + max(polls - 1, 0), count - 1)
    else:
        active = count
    states: list[StepState] = []
    for index in range(count):
        states.append("done" if index < active else "running" if index == active else "pending")
    return states


def _draw(screen: JobScreen, job: Job | None, polls: int) -> None:
    states = _step_states(job, polls, len(screen.steps))
    steps = [LoadingStep(label, state) for label, state in zip(screen.steps, states, strict=True)]
    render_loading_steps(screen.title, steps, ESTIMATE, key=screen.key)


def draw_waiting(screen: JobScreen) -> None:
    """Dibuja la carga con el primer paso en curso, antes de que exista el trabajo (B-060)."""
    _draw(screen, None, 0)


def wait_for_job(
    client: SmartMentorClient,
    job_id: str,
    screen: JobScreen,
    *,
    on_retry: Callable[[], None],
    back_page: str = PATH_PAGE,
) -> Job | None:
    """Muestra la carga y devuelve el trabajo cuando terminó bien; mientras tanto, None.

    Sondea una vez por ejecución con `st.fragment(run_every=...)`. Si el trabajo falla, muestra
    «Tu avance está guardado» con **Reintentar** (`on_retry`) y **Volver a mi ruta**: nunca
    inventa un resultado ni descarta lo respondido.
    """
    state = get_session().learner
    if state.job_error is not None:
        leave_wait_mode()
        error, state.job_error = state.job_error, None
        raise error
    finished = state.finished_jobs.get(job_id)
    if finished is None or finished.status != "failed":
        # Modo espera: la tarjeta de carga ya está en pantalla y las lecturas que siguen al
        # terminar el trabajo no dibujan «Cargando…» encima (T-054).
        enter_wait_mode(job_id)
    if finished is not None and finished.status != "failed":
        return finished
    if finished is not None:
        leave_wait_mode()  # con el error en pantalla, reintentar o volver sí muestran el spinner
        choice = render_loading_steps(
            screen.title,
            [
                LoadingStep(label, "failed" if i == 1 else "pending")
                for i, label in enumerate(screen.steps)
            ],
            ESTIMATE,
            key=screen.key,
            error_message=screen.error_message,
        )
        if choice == "retry":
            state.finished_jobs.pop(job_id, None)
            on_retry()
        elif choice == "back":
            st.switch_page(back_page)
        return None

    @st.fragment(run_every=POLL_SECONDS)
    def _poll() -> None:
        polls = state.job_polls.get(job_id, 0) + 1
        state.job_polls[job_id] = polls
        try:
            job = client.get_job(job_id)
        except ApiError as error:
            if is_global(error):
                state.job_error = error
            else:
                state.finished_jobs[job_id] = Job(
                    job_id=job_id, job_type="", status="failed", ingested=False
                )
            st.rerun()
            return
        if is_done(job):
            state.finished_jobs[job_id] = job
            st.rerun()
            return
        _draw(screen, job, polls)

    _poll()
    return None
