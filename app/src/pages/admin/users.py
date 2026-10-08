"""AD1 · Admin · Usuarios y roles."""

import csv
import io

import streamlit as st

from clients.base import ApiError
from clients.models import Role, User
from components.layout import render_notice, render_page_header
from components.table import Actions, Cell, Row, render_table
from components.theme import ROLE_BADGE, USER_STATUS_BADGE
from core.container import get_services
from core.errors import action_message

services = get_services()
me = services.admin.me()
users = services.admin.users()
counts = services.admin.counts(users)
ROLES: list[Role] = ["student", "teacher", "admin"]


def role_label(role: Role) -> str:
    return ROLE_BADGE[role][0]


@st.dialog("Nuevo usuario")
def new_user() -> None:
    full_name = st.text_input("Nombre completo")
    email = st.text_input("Correo institucional", placeholder="nombre@universidad.edu.co")
    role = st.selectbox("Rol", ROLES, format_func=role_label)
    st.caption("La persona entra con su cuenta institucional; no se le asigna contraseña aquí.")
    if st.button("Crear usuario", type="primary"):
        try:
            services.admin.create_user(full_name, email, role)
        except ApiError as error:
            st.error(action_message(error))
            return
        st.rerun()


@st.dialog("Cambiar rol")
def change_role(user: User) -> None:
    st.markdown(f"**{user.full_name}** · {user.email}")
    current = user.roles[0] if user.roles else "student"
    role = st.selectbox("Nuevo rol", ROLES, index=ROLES.index(current), format_func=role_label)
    if st.button("Guardar", type="primary"):
        try:
            services.admin.set_role(user.id, role)
        except ApiError as error:
            st.error(action_message(error))
            return
        st.rerun()


def users_csv(users: list[User]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["nombre", "correo", "rol", "activo"])
    for user in users:
        writer.writerow([user.full_name, user.email, ",".join(user.roles), user.active])
    return buffer.getvalue()


render_notice(
    "Solo Admin · Crear usuarios y asignar roles. Docentes y estudiantes no ven esta pantalla "
    "(403)."
)
heading, actions = st.columns([3, 2], vertical_alignment="center")
with heading:
    render_page_header(
        "Usuarios y roles",
        caption=(
            f"{counts.total} usuarios · {counts.teachers} docentes · {counts.admins} "
            f"{'admin' if counts.admins == 1 else 'admins'}"
        ),
    )
with actions.container(horizontal=True, horizontal_alignment="right"):
    if st.button("Nuevo usuario", type="primary", icon=":material/person_add:"):
        new_user()
    st.download_button(
        "Exportar CSV",
        data=users_csv(users),
        file_name="usuarios.csv",
        mime="text/csv",
        on_click="ignore",
    )

rows = []
for user in users:
    role = user.roles[0] if user.roles else "student"
    action: Cell = ":gray[Solo otro admin puede editar]"
    if user.id != me.id:
        toggle = ("deactivate", "Desactivar") if user.active else ("activate", "Reactivar")
        action = Actions((("role", "Cambiar rol"), toggle))
    rows.append(
        Row(
            key=str(user.id),
            cells=[
                user.full_name,
                user.email,
                ROLE_BADGE[role],
                USER_STATUS_BADGE[user.active],
                action,
            ],
        )
    )

clicked = render_table(
    ["Nombre", "Correo", "Rol", "Estado", "Acciones"],
    [1.8, 2.6, 1, 1, 2.2],
    rows,
    key="users",
)
if clicked:
    user = next(u for u in users if u.id == int(clicked[0]))
    if clicked[1] == "role":
        change_role(user)
    else:
        try:
            services.admin.set_active(user.id, clicked[1] == "activate")
        except ApiError as error:
            st.error(action_message(error))
        else:
            st.rerun()
