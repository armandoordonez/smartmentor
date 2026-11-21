"""E15 · Mi perfil: descripción y hoja de vida editables.

Guardar envía todo con `PUT /me/profile`; si hay una ruta en curso, la API recalcula niveles y pasos
pendientes y lo informa en `recalculated_enrollment_ids` (los temas aprobados no se pierden).
"""

import streamlit as st

from clients.base import ApiError
from components.layout import render_action_row, render_page_header
from components.resume_form import render_resume_form, render_weights_card, resume_form_state
from core.container import get_client
from core.errors import show_action_error
from core.identity import refresh_me
from core.navigation import DATA_RIGHTS
from core.session import get_session
from core.widget_state import seed_defaults
from services.profile import resume_values, save_profile

session = get_session()
client = get_client()

render_page_header(
    "Mi perfil",
    eyebrow_text="MI PERFIL",
    caption=(
        "Actualiza tu hoja de vida cuando cambie tu experiencia. Tu ruta se recalcula sola y los "
        "temas que ya aprobaste no se pierden."
    ),
)

try:
    profile = client.get_profile()
except ApiError as error:
    show_action_error(error)
    st.stop()

if profile.description:
    seed_defaults({"profile-description": profile.description})
with st.container(key="card-profile-description"):
    description = st.text_area(
        "Descripción de tu perfil",
        height=140,
        max_chars=2000,
        label_visibility="collapsed",
        key="profile-description",
    )

form_col, weights_col = st.columns([2, 1])
with form_col:
    values = resume_values(profile)
    seed_defaults(resume_form_state(values, key="my-profile"))
    result = render_resume_form(values, key="my-profile", extra_tools=session.extra_tools)
with weights_col:
    wants_rights = render_weights_card(key="my-profile")

if result.added_tool and result.added_tool not in session.extra_tools:
    session.extra_tools.append(result.added_tool)
    st.rerun()
if wants_rights:
    st.switch_page(DATA_RIGHTS)

_, actions = render_action_row("my-profile")
with actions:
    save = st.button("Guardar cambios", type="primary", key="my-profile-save")
if save:
    try:
        saved = save_profile(client, profile, description, result.values)
        refresh_me()
    except ApiError as error:
        show_action_error(error)
    else:
        st.success("Guardamos tu perfil.")
        if saved.recalculated_enrollment_ids:
            st.info("Tu ruta se recalculó con los datos nuevos.")
