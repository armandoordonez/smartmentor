"""E14 · Prueba de retención (P2): post-test diferido, opcional, que no cambia el badge.

Crea un intento de tipo `retention` (`POST …/steps/{id}/attempts`) y lo responde con el mismo flujo
del quiz. Solo se ofrece cuando la inscripción está completada; la API protege el resto.
"""

import streamlit as st

from clients.base import ApiError
from clients.models import AssessmentItem, Attempt, AttemptResult, LearnerAnswer
from components.layout import render_page_header
from core.container import get_client
from core.errors import show_action_error
from core.learner_flow import current_enrollment, idempotency_key
from core.question_flow import render_question_sheet
from core.session import get_session
from services.learning import item_context

PROGRESS_PAGE = "pages/learner/progress.py"
NOTE = (
    "Preguntas equivalentes a las del diagnóstico y la evaluación final, generadas con IA y "
    "revisadas por tu instructor."
)

client = get_client()
state = get_session().learner
enrollment = current_enrollment(client)
course = enrollment.learning_path.name

if enrollment.status != "completed":
    st.info("La prueba de retención se habilita cuando terminas la ruta.")
    st.page_link(PROGRESS_PAGE, label="Volver a Mi progreso")
    st.stop()

try:
    path = client.get_path(enrollment.id)
    step = path.steps[-1]
    attempt: Attempt = client.create_attempt(  # type: ignore[assignment]
        enrollment.id,
        step.step_id,
        "retention",
        idempotency_key=idempotency_key(f"retention-{enrollment.id}"),
    )
except ApiError as error:
    show_action_error(error)
    st.stop()
if not isinstance(attempt, Attempt):
    st.info("Estamos preparando tus preguntas. Vuelve en unos segundos.")
    st.stop()

state.sheet.load(f"attempt-{attempt.id}", attempt.answers, len(attempt.items))
number = min(state.sheet.index, max(len(attempt.items) - 1, 0)) + 1
render_page_header(
    "Prueba de retención",
    breadcrumb=f"{course} › Prueba de retención",
    caption="Esta prueba mide cuánto recuerdas. Es opcional y no cambia tu badge.",
)
st.markdown(f"**Pregunta {number} de {len(attempt.items)}**")
st.caption("Sin ayuda de IA ni apuntes")


def _save(answers: list[LearnerAnswer]) -> None:
    client.save_attempt_answers(attempt.id, answers)


def _submit(_answers: list[LearnerAnswer]) -> None:
    sent = client.submit_attempt(
        attempt.id, idempotency_key=idempotency_key(f"submit-{attempt.id}")
    )
    if isinstance(sent, AttemptResult):
        st.switch_page(PROGRESS_PAGE)
    st.info("Estamos calificando tu prueba. Verás el resultado en Mi progreso.")


def _context(item: AssessmentItem) -> str | None:
    return item_context(item)


render_question_sheet(
    attempt.items,
    state.sheet,
    key="retention",
    save=_save,
    submit=_submit,
    submit_label="Enviar prueba",
    notes=(NOTE,),
    context=_context,
)
if st.button("Ahora no", key="retention-skip"):
    st.switch_page(PROGRESS_PAGE)
