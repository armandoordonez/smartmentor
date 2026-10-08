"""E11 · Mi progreso."""

import streamlit as st

from components.formatting import decimal, duration
from components.kpi_cards import render_kpis
from components.layout import render_notice, render_page_header
from core.container import get_services
from core.navigation import CATALOG, MY_PATH
from core.session import get_session

services = get_services()
session = get_session()
overview = services.learning_path.progress_overview()

render_notice("Tu rol: Estudiante · Solo ves tu propio avance, nunca el de otros estudiantes.")
render_page_header("Mi progreso")

if not overview.paths:
    st.info("Todavía no tienes rutas en curso.")
    st.page_link(CATALOG, label="Ver rutas", icon=":material/arrow_forward:")
    st.stop()

render_kpis(
    [
        (f"{overview.done_topics} de {overview.total_topics}", "Temas aprobados"),
        (decimal(overview.attempts_per_topic), "Intentos por tema"),
        (duration(overview.saved_minutes), "Ahorrados por diagnóstico"),
    ]
)

for view in overview.paths:
    with st.container(border=True):
        st.markdown(f"#### {view.path.title}")
        st.progress(view.completion)
        if view.progress.final_passed:
            st.caption("Ruta completada · badge emitido")
        elif view.current is not None:
            st.caption(f"Siguiente paso: {view.current.topic.title}")
        elif view.progress.final_available:
            st.caption("Siguiente paso: evaluación final")
        if st.button("Continuar mi ruta", type="primary", key=f"continue-{view.path.id}"):
            session.selected_path_id = view.path.id
            st.switch_page(MY_PATH)
