"""E10 · Badge de la ruta completada."""

import streamlit as st

from components.badge_card import render_badge_hero
from components.layout import render_page_header
from core.container import current_user, get_services
from core.navigation import ACHIEVEMENTS, MY_PATH
from core.session import get_session
from pages.student.context import require_enrollment

services = get_services()
session = get_session()
enrollment = require_enrollment(services, session)
badge = services.assessment.badge_for(enrollment)

if badge is None:
    render_page_header("Badge")
    st.info("Aún no tienes el badge de esta ruta. Se emite al aprobar la evaluación final.")
    st.page_link(MY_PATH, label="Volver a mi ruta", icon=":material/arrow_back:")
    st.stop()

if render_badge_hero(badge, current_user().full_name) == "achievements":
    st.switch_page(ACHIEVEMENTS)
