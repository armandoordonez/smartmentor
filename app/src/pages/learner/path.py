"""E5 · Vista de ruta y E5b · Ruta fija (grupo de comparación del piloto).

Una sola página con dos variantes: la API dice cuál (`pilot_arm`). Cada tema muestra su estado y el
motivo por el que está en la ruta; «Continuar tema» sigue el `next_action` de la inscripción.
"""

import streamlit as st

from clients.base import ApiError
from clients.models import PathDetail
from components.formatting import percent_points
from components.layout import eyebrow, render_notice, render_page_header
from components.path_rows import render_path_rows
from core.container import get_client
from core.errors import show_action_error
from core.learner_flow import current_enrollment, go_to_action, remember
from core.navigation import CATALOG
from core.session import get_session
from core.usage_events import open_view
from services.learning import continue_label, path_rows, progress_line

TOPIC_PAGE = "pages/learner/topic.py"
DIAGNOSTIC_RESULT_PAGE = "pages/learner/diagnostic_result.py"
# El texto de origen depende de si la ruta ya está confirmada: «confirmado por ti» solo es cierto
# después (B-051).
ORIGIN_LABEL_CONFIRMED = {
    "llm_proposed": "TU OBJETIVO · PROPUESTO CON IA Y CONFIRMADO POR TI",
    "learner_edited": "TU OBJETIVO · EDITADO POR TI",
    "path_default": "TU OBJETIVO · DEFINIDO POR LA RUTA",
}
ORIGIN_LABEL_PENDING = {
    **ORIGIN_LABEL_CONFIRMED,
    "llm_proposed": "TU OBJETIVO · PROPUESTO CON IA, SIN CONFIRMAR",
}
DEFAULT_ORIGIN_LABEL = "TU OBJETIVO"
OBJECTIVE_PENDING = "objective_pending"
OBJECTIVE_PENDING_NOTE = "El objetivo se fija al confirmar la ruta"
OBJECTIVE_FIXED_NOTE = "El objetivo quedó fijado al confirmar tu ruta"

client = get_client()
state = get_session().learner
enrollment = current_enrollment(client)

try:
    path: PathDetail = client.get_path(enrollment.id)
except ApiError as error:
    show_action_error(error)
    st.stop()

fixed = enrollment.pilot_arm == "fixed"
# Tiempo en tarea (m27): `path.view` una vez por visita; `path.close` con los segundos al salir.
open_view(
    client,
    f"path:{enrollment.id}",
    enrollment_id=enrollment.id,
    event_type="path.view",
    close_type="path.close",
    payload={"screen": "E5b" if fixed else "E5", "steps_total": len(path.steps)},
)
rows = path_rows(path, fixed=fixed)
total = enrollment.progress.steps_total
course = enrollment.learning_path.name

if fixed:
    render_page_header(
        "Tu ruta",
        breadcrumb=f"{course} › Mi ruta",
        caption=(
            f"En este piloto tu grupo sigue los {total} temas en el orden del curso, sin omitir "
            "temas."
        ),
    )
    render_notice(
        "Grupo asignado al azar para el piloto. El contenido, los quizzes y los umbrales son los "
        "mismos de la ruta personalizada; solo cambia que no se omiten temas según el diagnóstico.",
        tone="info",
    )
else:
    render_page_header(
        course, breadcrumb=f"Rutas › {course}", caption=progress_line(enrollment, path)
    )
    if enrollment.objective is not None:
        with st.container(key="card-objective"):
            confirmed = enrollment.status != OBJECTIVE_PENDING
            origins = ORIGIN_LABEL_CONFIRMED if confirmed else ORIGIN_LABEL_PENDING
            eyebrow(origins.get(enrollment.objective.origin or "", DEFAULT_ORIGIN_LABEL))
            st.markdown(enrollment.objective.statement)
            # La API solo acepta el objetivo en `objective_pending`; con la ruta confirmada
            # respondería `409 INVALID_STATE_TRANSITION` (B-032, decisión del 2026-11-15).
            if confirmed:
                st.caption(OBJECTIVE_FIXED_NOTE)
            else:
                st.caption(OBJECTIVE_PENDING_NOTE)
                if st.button("Editar objetivo", key="path-edit-objective"):
                    state.edit_objective = True
                    st.switch_page(DIAGNOSTIC_RESULT_PAGE)

opened = render_path_rows(rows, grouped=fixed)
if opened is not None:
    state.step_id = opened
    st.switch_page(TOPIC_PAGE)

threshold = percent_points(path.final.pass_threshold)
with st.container(key="card-final"):
    if fixed:
        st.caption(f"Después de los {total} temas · Evaluación final ({threshold} para el badge)")
    else:
        eyebrow(f"DESPUÉS DE LOS {total} TEMAS")
        st.markdown("**Evaluación final**")
        st.caption(f"Se habilita al completar los temas · aprueba con {threshold}")
    st.badge(
        "Bloqueada" if path.final.locked else "Disponible",
        color="gray" if path.final.locked else "blue",
    )

label = continue_label(enrollment.next_action, path, fixed=fixed)
if st.button(label, type="primary", key="path-continue"):
    remember(enrollment.next_action)
    go_to_action(enrollment.next_action)
st.page_link(CATALOG, label="Ver otras rutas")
