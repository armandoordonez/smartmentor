"""Punto de entrada: estilos, login, consentimiento, rol activo, barra superior y navegación.

- `APP_DATA_SOURCE=api`: `st.login` con Keycloak; el rol sale de `GET /me` (CU-34, CU-35).
- `APP_DATA_SOURCE=fixtures`: se entra por el selector de rol A1 (sin login ni API).
- Una persona sin la autorización de datos solo ve las pantallas de consentimiento (A3, A3b, A3c).
- Un 401 muestra A7 «Tu sesión expiró»; un 403, A6.
"""

import logging

import streamlit as st

from clients.base import ApiError
from components.layout import HeaderAction, render_header, render_status_screen
from core import auth
from core.config import get_settings
from core.errors import describe_error
from core.identity import active_role, current_me, label_for, load_me
from core.navigation import (
    build_navigation,
    home_for,
    menu_links,
)
from core.session import get_session, reset_session
from core.styles import inject_styles

logger = logging.getLogger("smartmentor.app")

st.set_page_config(page_title="SmartMentor", page_icon=":material/school:", layout="wide")
inject_styles()

settings = get_settings()
session = get_session()


def _logout() -> None:
    """Cierra la sesión: en `api` también la de Keycloak; en `fixtures` solo olvida la de demo."""
    reset_session()
    if settings.app_data_source == "api":
        auth.logout()
    st.rerun()


def _login_screen() -> None:
    """Pantalla previa al login (A2 es de Keycloak): un botón que redirige al realm."""
    redirect_url = auth.pending_end_session_url()
    primary, _ = render_status_screen(
        role=None,
        role_label=None,
        code=None,
        title="Inicia sesión para continuar",
        message="Tu cuenta y tu contraseña las gestiona Keycloak; SmartMentor nunca las ve.",
        primary_label="Iniciar sesión",
        card=True,
    )
    if primary:
        auth.clear_end_session_url()
        auth.login()
    if redirect_url:
        st.link_button("Cerrar también la sesión de Keycloak", redirect_url)
    st.stop()


def _error_screen(error: ApiError, *, page_title: str) -> None:
    """A6 (403), A7 (401) y demás errores de una página, sin detalles técnicos."""
    logger.info(
        "Error de página %s: %s %s (request_id=%s)",
        page_title,
        error.status,
        error.code,
        error.request_id,
    )
    if error.status == 401 and error.code == auth.TOKEN_EXPIRED_CODE:
        auth.renew_silently_if_possible()  # redirige y no regresa si la sesión SSO sigue viva
    role = session.active_role
    role_text = label_for(role) if role and session.me else None
    view = describe_error(error, role_text, page_title)
    if view.kind in ("forbidden", "session_expired", "blocked"):
        is_forbidden = view.kind == "forbidden"
        go_home, switch = render_status_screen(
            role=role,
            role_label=role_text,
            code="403" if is_forbidden else None,
            title=view.title,
            message=view.message,
            primary_label="Volver a mi inicio" if is_forbidden else "Iniciar sesión",
            secondary_label="Cambiar de cuenta",
            card=not is_forbidden,
        )
        if go_home and is_forbidden and role is not None:
            st.switch_page(home_for(role))
        if go_home and not is_forbidden:
            _logout()
        if switch:
            _logout()
    else:
        st.warning(f"**{view.title}.** {view.message}")
        if st.button("Volver a mi inicio", type="primary") and session.active_role:
            st.switch_page(home_for(session.active_role))


def _handle_header(action: HeaderAction | None) -> None:
    if action is None:
        return
    if action.kind == "logout":
        _logout()
    elif action.kind == "switch_role" and action.role is not None:
        session.switch_role(action.role)
        st.switch_page(home_for(action.role))


# --- 1. Identidad ------------------------------------------------------------------------------

if settings.app_data_source == "api":
    if not auth.is_logged_in():
        _login_screen()
    try:
        auth.access_token()  # revisa `exp` antes de cada ejecución
        load_me()
    except ApiError as error:
        _error_screen(error, page_title="SmartMentor")
        st.stop()
elif not session.is_authenticated:
    # Modo fixtures sin sesión: solo el selector de rol (A1).
    build_navigation(None, authenticated=False).run()
    st.stop()

# --- 2. Navegación, barra superior y página ------------------------------------------------------

me = current_me()
role = active_role(session)
page = build_navigation(role, authenticated=True, consent_only=me.requires_consent)

with st.container(key=f"role-{role}"):
    other_roles = [(other, label_for(other)) for other in me.roles if other != role]
    action = render_header(
        role=role,
        role_label=label_for(role, short=True),
        full_name=me.full_name,
        email=me.email,
        links=[] if me.requires_consent else menu_links(role),
        other_roles=other_roles,
    )
    _handle_header(action)
    try:
        page.run()
    except ApiError as error:
        _error_screen(error, page_title=page.title)
