"""E5 · Vista de ruta y E5b · Ruta fija (grupo de comparación del piloto).

Una sola página con dos variantes: la API dice cuál (`pilot_arm`). Cada tema muestra su estado y el
motivo por el que está en la ruta; «Continuar tema» sigue el `next_action` de la inscripción.
"""

import streamlit as st

from clients.base import ApiError
from clients.models import PathDetail
from components.formatting import percent_points
from components.layout import eyebrow, render_page_header
from components.path_rows import render_path_rows
from core.container import get_client
from core.errors import show_action_error
from core.learner_flow import current_enrollment, go_to_action, remember
from core.navigation import CATALOG
from core.session import get_session
from services.learning import path_rows, progress_line, step_name

TOPIC_PAGE = "pages/learner/topic.py"
DIAGNOSTIC_RESULT_PAGE = "pages/learner/diagnostic_result.py"
ORIGIN_LABEL = {
    "llm_proposed": "TU OBJETIVO · PROPUESTO CON IA Y CONFIRMADO POR TI",
    "learner_edited": "TU OBJETIVO · EDITADO POR TI",
    "path_default": "TU OBJETIVO · DEFINIDO POR LA RUTA",
}

client = get_client()
state = get_session().learner
enrollment = current_enrollment(client)

try:
    path: PathDetail = client.get_path(enrollment.id)
except ApiError as error:
    show_action_error(error)
    st.stop()

fixed = enrollment.pilot_arm == "fixed"
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
    st.caption(
        "Grupo asignado al azar para el piloto. El contenido, los quizzes y los umbrales son los "
        "mismos de la ruta personalizada; solo cambia que no se omiten temas según el diagnóstico."
    )
else:
    render_page_header(
        course, breadcrumb=f"Rutas › {course}", caption=progress_line(enrollment, path)
    )
    if enrollment.objective is not None:
        with st.container(key="card-objective"):
            eyebrow(ORIGIN_LABEL[enrollment.objective.origin])
            st.markdown(f"**{enrollment.objective.statement}**")
            if st.button("Editar objetivo", key="path-edit-objective"):
                state.edit_objective = True
                st.switch_page(DIAGNOSTIC_RESULT_PAGE)

opened = render_path_rows(rows)
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

next_step = step_name(path, enrollment.next_action.step_id)
label = f"Continuar con {next_step}" if fixed and next_step else "Continuar tema"
if st.button(label, type="primary", key="path-continue"):
    remember(enrollment.next_action)
    go_to_action(enrollment.next_action)
st.page_link(CATALOG, label="Ver otras rutas")
