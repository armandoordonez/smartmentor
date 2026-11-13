"""AD1 · Usuarios y roles.

Solo el administrador (la API responde 403 a los demás). Un usuario puede tener varios roles; la
API reemplaza el conjunto (`PUT /users/{id}/roles`) y se niega a dejar el sistema sin administrador
(`409 LAST_ADMIN`).
"""

import streamlit as st

from clients.base import ApiError
from clients.models import ROLES, Role
from clients.models_staff import AdminUser, UserCreate
from components.layout import render_notice, render_page_header, render_page_header_with_actions
from components.staff_theme import ROLE_TEXT
from components.table import Actions, Badges, PlainText, Row, render_table
from components.theme import ROLE_COLOR
from core.container import get_client
from core.identity import current_me
from core.staff_errors import show_staff_error
from core.staff_state import COURSES_ENROLLMENTS
from services.staff_admin import ordered_roles, users_caption

client = get_client()
me = current_me()

render_notice(
    "Solo Admin · Crear usuarios y asignar roles. Instructores y aprendices no ven esta pantalla "
    "(403)."
)
try:
    page = client.list_users()
except ApiError as error:
    render_page_header("Usuarios y roles")
    show_staff_error(error)
    st.stop()
users = page.items

with render_page_header_with_actions("Usuarios y roles", caption=users_caption(page.total, users)):
    st.button("Importar CSV", key="u-import", disabled=True, help="Llega en una siguiente versión.")
    if st.button("Crear usuario", type="primary", key="u-create"):
        st.session_state["u-panel"] = ("create", None)
    if st.button("Cursos y rutas", key="u-courses"):
        st.switch_page(COURSES_ENROLLMENTS)


def role_badges(roles: list[Role]) -> Badges | str:
    """Una insignia por rol, con el color del rol (V-008); «—» si no tiene ninguno."""
    ordered = ordered_roles(roles)
    if not ordered:
        return "—"
    return Badges(tuple((ROLE_TEXT[role], ROLE_COLOR[role]) for role in ordered))


def _row_actions(user: AdminUser) -> Actions | str:
    if user.id == me.id:
        return "Solo otro admin puede editar"
    if not user.active:
        return Actions((("activate", "Reactivar"),))
    return Actions((("roles", "Cambiar rol"), ("deactivate", "Desactivar")))


rows = [
    Row(
        key=str(user.id),
        cells=[
            user.full_name,
            PlainText(user.email),
            role_badges(user.roles),
            ("Activo", "green") if user.active else ("Inactivo", "gray"),
            _row_actions(user),
        ],
    )
    for user in users
]
clicked = render_table(
    ["Nombre", "Correo", "Rol", "Estado", "Acciones"],
    [3, 4, 2, 2, 3],
    rows,
    key="users",
    empty_text="Todavía no hay usuarios.",
)
if clicked is not None:
    user_id, action = int(clicked[0]), clicked[1]
    if action == "roles":
        st.session_state["u-panel"] = ("roles", user_id)
    else:
        try:
            client.set_user_active(user_id, action == "activate")
        except ApiError as error:
            show_staff_error(error)
        else:
            st.rerun()


def _roles_panel(user: AdminUser) -> None:
    with st.container(border=True, key=f"panel-roles-{user.id}"):
        st.subheader(f"Roles de {user.full_name}", anchor=False)
        chosen: list[Role] = st.multiselect(
            "Roles",
            list(ROLES),
            default=user.roles,
            format_func=lambda role: ROLE_TEXT[role],
            key=f"u-roles-{user.id}",
        )
        st.caption("Un usuario puede tener varios roles. Debe quedar al menos un administrador.")
        with st.container(horizontal=True):
            cancel = st.button("Cancelar", key=f"u-roles-cancel-{user.id}")
            save = st.button(
                "Guardar roles", type="primary", key=f"u-roles-save-{user.id}", disabled=not chosen
            )
    if cancel:
        st.session_state.pop("u-panel", None)
        st.rerun()
    if save:
        try:
            client.set_user_roles(user.id, chosen)
        except ApiError as error:
            show_staff_error(error)
        else:
            st.session_state.pop("u-panel", None)
            st.rerun()


def _create_panel() -> None:
    with st.container(border=True, key="panel-create-user"):
        st.subheader("Crear usuario", anchor=False)
        name = st.text_input("Nombre completo", key="u-new-name")
        email = st.text_input("Correo", key="u-new-email")
        roles: list[Role] = st.multiselect(
            "Roles",
            list(ROLES),
            default=["learner"],
            format_func=lambda role: ROLE_TEXT[role],
            key="u-new-roles",
        )
        with st.container(horizontal=True):
            cancel = st.button("Cancelar", key="u-new-cancel")
            save = st.button(
                "Crear",
                type="primary",
                key="u-new-save",
                disabled=not (name.strip() and email.strip() and roles),
            )
    if cancel:
        st.session_state.pop("u-panel", None)
        st.rerun()
    if save:
        try:
            client.create_user(UserCreate(email=email.strip(), full_name=name.strip(), roles=roles))
        except ApiError as error:
            show_staff_error(error)
        else:
            st.session_state.pop("u-panel", None)
            st.rerun()


panel = st.session_state.get("u-panel")
if panel is not None:
    kind, target = panel
    if kind == "create":
        _create_panel()
    else:
        selected = next((u for u in users if u.id == target), None)
        if selected is not None:
            _roles_panel(selected)
