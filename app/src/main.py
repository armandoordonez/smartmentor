"""Punto de entrada: página, rol de la sesión, barra superior y navegación.

Prototipo de la Fase 0 sin login: se entra eligiendo un rol (A1) y los datos son de ejemplo. Cuando
exista el login con Keycloak (ADR 0006), el rol saldrá de `GET /api/v1/me`.
"""

import streamlit as st

from clients.base import ApiError
from components.layout import render_header, render_status_screen
from core.container import current_user
from core.errors import describe_error
from core.navigation import HOME, LINKS, build_navigation
from core.session import end_session, get_session

st.set_page_config(page_title="SmartMentor", page_icon=":material/school:", layout="wide")

session = get_session()
page = build_navigation(session.role)

if session.role is None:
    page.run()
    st.stop()

role = session.role
user = current_user()
if render_header(role, user.full_name, user.email, LINKS[role]):
    end_session()
    st.rerun()

try:
    page.run()
except ApiError as error:
    view = describe_error(error, role, page.title)
    if view.kind in ("forbidden", "session_expired"):
        go_home, switch = render_status_screen(
            role=role,
            code="403" if view.kind == "forbidden" else None,
            title=view.title,
            message=view.message,
            primary_label="Volver a mi inicio" if view.kind == "forbidden" else "Volver a entrar",
            secondary_label="Cambiar de rol",
        )
        if go_home:
            st.switch_page(HOME[role])
        if switch:
            end_session()
            st.rerun()
    else:
        st.warning(f"**{view.title}.** {view.message}")
        if st.button("Volver a mi inicio", type="primary"):
            st.switch_page(HOME[role])
