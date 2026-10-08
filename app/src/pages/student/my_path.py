"""E5 · Vista de ruta."""

import streamlit as st

from components.formatting import duration
from components.layout import render_page_header
from components.path_timeline import render_path_timeline
from core.container import get_services
from core.navigation import BADGE, DIAGNOSTIC, FINAL_ASSESSMENT, TOPIC
from core.session import get_session
from pages.student.context import require_enrollment

services = get_services()
session = get_session()
enrollment = require_enrollment(services, session)
if enrollment.status == "onboarding":
    st.switch_page(DIAGNOSTIC)

view = services.learning_path.path_view(enrollment)
progress = view.progress

summary = f"Progreso: {view.done_count} de {len(view.steps)} temas"
if view.skipped_count:
    omitted = "omitido" if view.skipped_count == 1 else "omitidos"
    summary += (
        f" · {view.skipped_count} {omitted} por tu diagnóstico "
        f"(ahorro {duration(progress.saved_minutes)})"
    )
render_page_header(view.path.title, breadcrumb=f"Rutas › {view.path.title}", caption=summary)

opened = render_path_timeline([(s.topic, s.step) for s in view.steps], progress)
if opened == -1:
    st.switch_page(BADGE if progress.final_passed else FINAL_ASSESSMENT)
if opened is not None:
    session.open_topic(opened)
    st.switch_page(TOPIC)

current = view.current
if current is not None:
    if st.button("Continuar tema", type="primary"):
        session.open_topic(current.topic.id)
        st.switch_page(TOPIC)
elif progress.final_available:
    if st.button("Presentar evaluación final", type="primary"):
        st.switch_page(FINAL_ASSESSMENT)
elif progress.final_passed and st.button("Ver mi badge", type="primary"):
    st.switch_page(BADGE)
