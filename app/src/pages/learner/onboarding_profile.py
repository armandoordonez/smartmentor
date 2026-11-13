"""E2 · Perfil (paso 1 de 4): la descripción libre de la persona.

Guarda con `PUT /me/profile`; la hoja de vida (paso 2) se pide en E2b. La interfaz no calcula el
estado de la inscripción: después de guardar sigue a la hoja de vida y, si ya existe, al paso que
indica la API (el diagnóstico), como promete E2b («si ya la tuvieras, este paso se omite»).
"""

import streamlit as st

from clients.base import ApiError
from components.layout import render_page_header
from core.container import get_client
from core.errors import show_action_error
from core.identity import refresh_me
from core.learner_flow import go_to_action
from core.navigation import CATALOG, ONBOARDING_RESUME
from core.session import get_session
from services.profile import save_description

client = get_client()

render_page_header(
    "Cuéntanos sobre ti",
    eyebrow_text="PASO 1 DE 4 · PERFIL",
    caption=(
        "Describe tu formación, experiencia e intereses con tus palabras. Si aún no tienes hoja "
        "de vida, te la pedimos en el siguiente paso."
    ),
)

try:
    profile = client.get_profile()
except ApiError as error:
    show_action_error(error)
    st.stop()

with st.container(key="card-profile-description"):
    description = st.text_area(
        "Describe tu formación, experiencia e intereses",
        value=profile.description or "",
        height=160,
        max_chars=2000,
        label_visibility="collapsed",
        key="profile-description",
    )

back_col, next_col = st.columns([1, 1])
if back_col.button("Atrás", key="profile-back"):
    st.switch_page(CATALOG)
if next_col.button(
    "Continuar a la hoja de vida",
    type="primary",
    key="profile-next",
    disabled=not description.strip(),
):
    enrollment_id = get_session().selected_enrollment_id
    try:
        save_description(client, profile, description)
        refresh_me()
        action = (
            client.get_enrollment(enrollment_id).next_action
            if profile.resume_completed_at is not None and enrollment_id is not None
            else None
        )
    except ApiError as error:
        show_action_error(error)
    else:
        if action is not None:
            go_to_action(action)
        st.switch_page(ONBOARDING_RESUME)
