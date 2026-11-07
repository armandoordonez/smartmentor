"""E2b · Hoja de vida (paso 2 de 4).

Se puede completar ahora o después («Completar más tarde»): sin hoja de vida el peso pasa al
diagnóstico. Al terminar, la página sigue por el `next_action` de la inscripción.
"""

import streamlit as st

from clients.base import ApiError
from components.layout import render_page_header
from components.resume_form import render_resume_form, render_weights_card
from core.container import get_client
from core.errors import show_action_error
from core.identity import refresh_me
from core.navigation import DATA_RIGHTS, page_for_next_action
from core.session import get_session
from services.profile import resume_values, save_resume

session = get_session()
client = get_client()

render_page_header(
    "Tu hoja de vida",
    eyebrow_text="PASO 2 DE 4 · HOJA DE VIDA",
    caption=(
        "Aún no tienes hoja de vida. Solo pedimos lo que ayuda a ajustar tu ruta; si ya la "
        "tuvieras, este paso se omite. Puedes completarla ahora o después desde Mi perfil."
    ),
)

try:
    profile = client.get_profile()
except ApiError as error:
    show_action_error(error)
    st.stop()


def _continue() -> None:
    """Sigue al paso que indica la API para la inscripción (el diagnóstico, E3)."""
    enrollment_id = session.selected_enrollment_id
    target = None
    if enrollment_id is not None:
        target = page_for_next_action(client.get_enrollment(enrollment_id).next_action)
    if target is None:
        st.success("Listo: tu perfil quedó guardado.")
        st.info("El diagnóstico llega en la siguiente parte de la interfaz.")
        return
    st.switch_page(target)


form_col, weights_col = st.columns([2, 1])
with form_col:
    result = render_resume_form(
        resume_values(profile), key="resume", extra_tools=session.extra_tools
    )
with weights_col:
    wants_rights = render_weights_card(key="resume")

if result.added_tool and result.added_tool not in session.extra_tools:
    session.extra_tools.append(result.added_tool)
    st.rerun()
if wants_rights:
    st.switch_page(DATA_RIGHTS)

later_col, save_col = st.columns([1, 1])
try:
    if later_col.button("Completar más tarde", key="resume-later"):
        _continue()
    if save_col.button("Guardar y continuar", type="primary", key="resume-save"):
        save_resume(client, profile, result.values)
        refresh_me()
        _continue()
except ApiError as error:
    show_action_error(error)
