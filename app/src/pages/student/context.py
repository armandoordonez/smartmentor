"""Apoyo de las páginas del estudiante: la inscripción de la ruta elegida en la sesión.

No es una página: no está registrada en `core/navigation.py`.
"""

import streamlit as st

from clients.models import Enrollment
from core.container import Services
from core.navigation import CATALOG
from core.session import AppSession


def require_enrollment(services: Services, session: AppSession) -> Enrollment:
    """Devuelve la inscripción de la ruta elegida o, si no hay, la que esté en curso. Si el
    estudiante no tiene ninguna, muestra cómo elegir una ruta y detiene la página."""
    enrollment = None
    if session.selected_path_id is not None:
        enrollment = services.enrollment.active_enrollment(session.selected_path_id)
    if enrollment is None:
        in_progress = [
            e
            for e in services.catalog.list_path_cards()
            if e.enrollment is not None and e.enrollment.status == "in_progress"
        ]
        if in_progress and in_progress[0].enrollment is not None:
            enrollment = in_progress[0].enrollment
            session.selected_path_id = enrollment.learning_path_id
    if enrollment is None:
        st.info("Primero elige una ruta en el catálogo.")
        st.page_link(CATALOG, label="Ver rutas", icon=":material/arrow_forward:")
        st.stop()
    return enrollment
