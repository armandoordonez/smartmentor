"""E3 · Diagnóstico (paso 3 de 4) y U1a · Calculando tu nivel.

Las preguntas se responden de una en una y cada paso se guarda en la API (guardado parcial), así
que se puede salir y retomar. La pantalla que sigue la dicta `next_action`: `start_diagnostic` crea
el diagnóstico, `continue_diagnostic` lo retoma y `wait_job` espera el cálculo de la IA (U1a).
"""

import streamlit as st

from clients.base import ApiError
from clients.models import Diagnostic, LearnerAnswer
from components.layout import eyebrow, render_page_header
from core.container import get_client
from core.errors import show_action_error
from core.learner_flow import (
    JobScreen,
    current_enrollment,
    go_to_action,
    idempotency_key,
    redirect_unless,
    wait_for_job,
)
from core.question_flow import render_question_sheet
from core.session import get_session
from services.learning import item_context

PAGE = "pages/learner/diagnostic.py"
NOTES = (
    "Este diagnóstico no cuenta para tu nota. Si no sabes, elige «No lo sé»: adivinar no te sube "
    "el nivel, porque una respuesta incorrecta cuenta igual que «No lo sé».",
    "Las preguntas se generan con IA a partir del syllabus y las revisa tu instructor.",
)
CALCULATING = JobScreen(
    key="diagnostic",
    title="Calculando tu nivel y proponiendo tu objetivo",
    steps=(
        "Calificar tus respuestas del diagnóstico",
        "Combinar el resultado con tu perfil",
        "Proponer tu objetivo de aprendizaje",
    ),
    error_message="No pudimos calcular tu nivel. Tu avance está guardado.",
)

client = get_client()
session = get_session()
state = session.learner

enrollment = current_enrollment(client)
action = redirect_unless(enrollment, {"start_diagnostic", "continue_diagnostic", "wait_job"}, PAGE)
if action.type == "wait_job" and action.job_id:
    state.diagnostic_job_id = action.job_id


def _submit() -> None:
    accepted = client.submit_diagnostic(
        enrollment.id, idempotency_key=idempotency_key(f"diagnostic-{enrollment.id}")
    )
    state.diagnostic_job_id = accepted.job_id


def _retry() -> None:
    try:
        accepted = client.submit_diagnostic(
            enrollment.id,
            idempotency_key=idempotency_key(f"diagnostic-{enrollment.id}", fresh=True),
        )
    except ApiError as error:
        show_action_error(error)
        return
    state.diagnostic_job_id = accepted.job_id
    st.rerun()


# --- U1a · Calculando tu nivel -------------------------------------------------------------------

if state.diagnostic_job_id:
    job = wait_for_job(client, state.diagnostic_job_id, CALCULATING, on_retry=_retry)
    if job is None:
        st.stop()
    state.diagnostic_job_id = None
    go_to_action(job.next_action or client.get_enrollment(enrollment.id).next_action)
    st.stop()

# --- E3 · Diagnóstico ----------------------------------------------------------------------------

try:
    if action.type == "start_diagnostic":
        diagnostic: Diagnostic = client.create_diagnostic(enrollment.id)
    else:
        diagnostic = client.get_diagnostic(enrollment.id)
except ApiError as error:
    show_action_error(error)
    st.stop()

state.sheet.load(f"diagnostic-{diagnostic.id}", diagnostic.answers, len(diagnostic.items))


def _save(answers: list[LearnerAnswer]) -> None:
    client.save_diagnostic_answers(enrollment.id, answers)


@st.fragment
def _sheet() -> None:
    """Encabezado y pregunta actual. Va en un fragmento: cada clic solo redibuja esta parte y no
    vuelve a pedir la inscripción ni el diagnóstico a la API (B-018)."""
    position = min(state.sheet.index, max(len(diagnostic.items) - 1, 0)) + 1
    eyebrow(
        f"PASO 3 DE 4 · DIAGNÓSTICO · {enrollment.learning_path.name.upper()} · "
        f"Pregunta {position} de {len(diagnostic.items)}"
    )
    render_page_header("Diagnóstico")
    render_question_sheet(
        diagnostic.items,
        state.sheet,
        key="diagnostic",
        save=_save,
        submit=lambda _answers: _submit(),
        submit_label="Enviar diagnóstico",
        notes=NOTES,
        context=item_context,
        allow_dont_know=True,
        rerun_scope="fragment",
    )


_sheet()
