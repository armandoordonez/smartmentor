"""Punto de entrada: estilos, login, consentimiento, rol activo, barra superior y navegación.

- `APP_DATA_SOURCE=api`: `st.login` con Keycloak; el rol sale de `GET /me` (CU-34, CU-35).
- `APP_DATA_SOURCE=fixtures`: se entra por el selector de rol A1 (sin login ni API).
- Una persona sin la autorización de datos solo ve las pantallas de consentimiento (A3, A3b, A3c).
- Un 401 muestra A7 «Tu sesión expiró»; un 403, A6. Si el token venció y la sesión de Keycloak
  sigue viva, se renueva y se vuelve a la misma página con la misma sesión (`core/renewal.py`).
- B-040: la renovación no se hace en medio de una acción si el token aún alcanza; sin acción, se
  adelanta. Si no hay más remedio que renovar con un clic pendiente, se aparcan los valores del
  formulario y el clic, y al volver se ponen de nuevo y se repite el clic.
"""

import logging

import streamlit as st

from clients.base import ApiError
from components.layout import HeaderAction, render_header, render_status_screen
from core import auth, renewal, widget_state
from core.config import get_settings
from core.container import get_client
from core.errors import describe_error, pop_deferred_click, pop_deferred_error
from core.identity import active_role, current_me, label_for, load_me
from core.navigation import (
    active_menu_path,
    build_navigation,
    home_for,
    is_registered,
    menu_links,
    page_for_url_path,
)
from core.session import get_session, replace_session, reset_session
from core.styles import inject_styles
from core.usage_events import close_views_outside

logger = logging.getLogger("smartmentor.app")

st.set_page_config(page_title="SmartMentor", page_icon=":material/school:", layout="wide")
inject_styles()

settings = get_settings()
if settings.app_data_source == "api" and auth.is_logged_in():
    # Vuelta de Keycloak tras renovar el token (B-030): Streamlit abrió una sesión nueva en la raíz;
    # se recupera la que se aparcó antes de redirigir, con la página a la que hay que volver.
    restored = renewal.restore(renewal.STORE, auth.user_key(), get_session())
    if restored is not None:
        replace_session(restored)
        # El borrador va a `st.session_state` antes de cambiar de página: los widgets lo toman
        # al dibujarse (B-040).
        widget_state.apply_form_values(restored.resume_drafts)
        restored.resume_drafts = {}
session = get_session()
# Error global que dejó un fragmento (B-031). Se lee antes de revisar el token: si el token venció,
# lo atiende esa revisión (renovación o A7) y este error ya no se muestra.
deferred_error = pop_deferred_error()
# El clic que ese fragmento no pudo atender porque el token venció (B-040).
deferred_click = pop_deferred_click()


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


def _browser_url() -> str | None:
    try:
        return st.context.url
    except (AttributeError, RuntimeError):
        return None


def _page_in_browser() -> str | None:
    return renewal.page_from_url(_browser_url()) or session.current_page


def _park_session() -> None:
    """Aparca la página, la sesión y el borrador justo antes de `st.login` (B-030, B-040).

    Se usa cuando la página ya corrió (un 401 a mitad de página): el clic no se repite.
    """
    renewal.park(
        renewal.STORE,
        auth.user_key(),
        _page_in_browser(),
        session,
        drafts=widget_state.form_values(),
    )


def _renew(page: str | None, click: widget_state.PressedButton | None) -> None:
    """Aparca y redirige a Keycloak antes de correr la página (B-040); detiene la ejecución."""
    renewal.park(
        renewal.STORE,
        auth.user_key(),
        page,
        session,
        drafts=widget_state.form_values(),
        click=click,
    )
    auth.login()
    st.caption("Renovando tu sesión…")
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
    if (
        error.status == 401
        and error.code == auth.TOKEN_EXPIRED_CODE
        and auth.renew_silently_if_possible(before_redirect=_park_session)
    ):
        # El navegador ya va a Keycloak y vuelve con un token nuevo; no se dibuja A7.
        st.caption("Renovando tu sesión…")
        st.stop()
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

renewal_plan: auth.RenewalPlan = "none"
if settings.app_data_source == "api":
    if not auth.is_logged_in():
        _login_screen()
    # B-040: con una acción pendiente (un botón, un widget cambiado) no se renueva mientras el
    # token alcance para la petición; si ya no alcanza, se renueva y el clic se repite al volver.
    interaction = widget_state.current_interaction()
    renewal_plan = auth.renewal_plan(has_action=interaction.pending)
    if renewal_plan == "now":
        _renew(_page_in_browser(), interaction.pressed or deferred_click)
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
# La página de inicio tiene `url_path` vacío (la raíz).
current_page = page_for_url_path(page.url_path) if page.url_path else home_for(role)
# Tras renovar el token se vuelve a la página en la que estaba la persona (B-030).
resume_page, session.resume_page = session.resume_page, None
if (
    resume_page is not None
    and resume_page != current_page
    and not me.requires_consent
    and is_registered(resume_page)
):
    st.switch_page(resume_page)
session.current_page = current_page
# Sin acción pendiente y con el token a punto de vencer: es el momento seguro para renovar (B-040).
if renewal_plan == "safe_point":
    _renew(current_page, None)
# El clic que interrumpió la renovación se repite en su página, una sola vez (B-040).
click, session.resume_click = session.resume_click, None
if click is not None and click.page == current_page and not me.requires_consent:
    widget_state.press(click.widget_id)
# Tiempo en tarea (m27): al pasar a otra página se cierran las visitas abiertas (tema, quiz…).
close_views_outside(page.url_path, get_client)

with st.container(key=f"role-{role}"):
    other_roles = [(other, label_for(other)) for other in me.roles if other != role]
    action = render_header(
        role=role,
        role_label=label_for(role, short=True),
        active_role_label=label_for(role),
        full_name=me.full_name,
        email=me.email,
        links=[] if me.requires_consent else menu_links(role),
        other_roles=other_roles,
        active_path=active_menu_path(page.url_path, role),
    )
    _handle_header(action)
    try:
        if deferred_error is not None:
            raise deferred_error
        page.run()
    except ApiError as error:
        _error_screen(error, page_title=page.title)
