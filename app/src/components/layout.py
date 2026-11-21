"""Piezas comunes de todas las pantallas: barra superior (componente Nav de Figma), encabezado de
página, aviso y pantallas de estado (403, sesión expirada).

Los componentes no leen `st.session_state` ni llaman a `clients/`: reciben sus datos por parámetro
y devuelven lo que eligió la persona (`HeaderAction`); la página decide qué hacer.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

import streamlit as st
from streamlit.delta_generator import DeltaGenerator

from clients.models import Role
from components.formatting import initials
from components.theme import ROLE_COLOR

NavLink = tuple[str, str]
"""(archivo de la página, texto del enlace)."""


@dataclass(frozen=True)
class HeaderAction:
    kind: Literal["switch_role", "logout"]
    role: Role | None = None


def eyebrow(text: str) -> None:
    """Antetítulo de color en negrita («PASO 1 DE 4 · PERFIL», «RECOMENDADA PARA TI»)."""
    st.markdown(f":small[:blue[**{text}**]]")


def render_brand(role_label: str | None = None, role: Role | None = None) -> None:
    with st.container(horizontal=True, horizontal_alignment="center", vertical_alignment="center"):
        st.markdown("### :blue[:material/school:] SmartMentor", width="content")
        if role_label is not None and role is not None:
            st.badge(role_label, color=ROLE_COLOR[role])


def render_header(
    *,
    role: Role,
    role_label: str,
    full_name: str,
    email: str,
    links: Sequence[NavLink],
    other_roles: Sequence[tuple[Role, str]] = (),
    logout_label: str = "Cerrar sesión",
    switch_label: str = "Cambiar de perfil",
    active_label: str = "Rol activo",
    active_role_label: str | None = None,
    active_path: str | None = None,
) -> HeaderAction | None:
    """Barra superior: marca, rol, enlaces del rol y menú de la cuenta (CU-35).

    El menú muestra el nombre, el correo y el rol activo (`active_role_label`, con su etiqueta
    larga; si no llega, la corta). `other_roles` son los demás roles del usuario con su etiqueta;
    si hay alguno, el menú ofrece cambiar de perfil (F-004). Devuelve la acción elegida (cambiar
    de rol o cerrar sesión), o None.

    `active_path` es el enlace que se marca como activo (azul y en negrita); la página lo decide
    porque pantallas como el quiz no tienen enlace propio y cuelgan de «Rutas» (V-044).
    """
    action: HeaderAction | None = None
    with st.container(key="app-header", horizontal=True, vertical_alignment="center", gap="medium"):
        st.markdown(":blue[:material/school:] **SmartMentor**", width="content")
        st.badge(role_label, color=ROLE_COLOR[role])
        st.space("stretch")
        for path, text in links:
            # width="content": cada enlace ocupa lo suyo y todos quedan juntos a la derecha, junto
            # al avatar, como en Figma (sin esto la fila los reparte por toda la barra, V-089).
            with st.container(
                key="nav-link-active" if path == active_path else None, width="content"
            ):
                st.page_link(path, label=text)
        with (
            st.container(key="app-avatar", width="content"),
            st.popover(initials(full_name), type="tertiary"),
        ):
            st.markdown(f"**{full_name}**")
            st.caption(email)
            st.caption(f"**{active_label.upper()}**")
            st.markdown(f":material/check: {active_role_label or role_label}")
            if other_roles:
                st.caption(f"**{switch_label.upper()}**")
                for other, label in other_roles:
                    if st.button(label, key=f"switch-role-{other}", icon=":material/swap_horiz:"):
                        action = HeaderAction("switch_role", other)
            if st.button(logout_label, key="logout", icon=":material/logout:"):
                action = HeaderAction("logout")
    return action


def render_page_header(
    title: str,
    *,
    caption: str | None = None,
    eyebrow_text: str | None = None,
    breadcrumb: str | None = None,
) -> None:
    if breadcrumb:
        st.caption(breadcrumb)
    if eyebrow_text:
        eyebrow(eyebrow_text)
    st.title(title, anchor=False)
    if caption:
        st.caption(caption)


def render_page_header_with_actions(
    title: str, *, caption: str | None = None, key: str = "page-actions"
) -> DeltaGenerator:
    """Título y subtítulo a la izquierda y, a la derecha, el contenedor de las acciones (V-002).

    Como en Figma (D1, AD1): los botones de la página van en la misma fila que el título. La página
    pone sus botones dentro del contenedor que devuelve (`with actions: st.button(...)`).
    """
    left, right = st.columns([3, 2], vertical_alignment="center")
    with left:
        render_page_header(title, caption=caption)
    return right.container(horizontal=True, horizontal_alignment="right", key=key)


def render_action_row(key: str) -> tuple[DeltaGenerator, DeltaGenerator]:
    """Fila de botones como en Figma (V-037): salidas a la izquierda y avance a la derecha.

    Devuelve dos contenedores horizontales con un espacio flexible entre ambos. A la izquierda van
    los secundarios de «salida» («No lo sé», «Ahora no», «Completar más tarde») y a la derecha
    «Atrás/Anterior», los secundarios y el principal, juntos. La página pone sus botones dentro
    (`with left: ...`, `with right: ...`) y conserva sus `key` y su lógica.
    """
    with st.container(key=f"action-row-{key}", horizontal=True, vertical_alignment="center"):
        left = st.container(horizontal=True, width="content", key=f"action-row-{key}-left")
        st.space("stretch")
        right = st.container(horizontal=True, width="content", key=f"action-row-{key}-right")
    return left, right


def render_notice(text: str, *, tone: Literal["warning", "info", "success"] = "warning") -> None:
    """Aviso de permisos o reglas («Tu rol: Instructor · Solo corriges tus cursos»).

    Ámbar por defecto. Con `tone="info"` va en una caja azul suave (nota del grupo, E5b) y con
    `tone="success"` es la nota verde informativa (E4b: «El 80 % para obtener el badge…»).
    """
    if tone == "info":
        with st.container(key="notice-info"):
            st.markdown(text)
    elif tone == "success":
        st.success(text)
    else:
        st.warning(text)


def render_status_screen(
    *,
    role: Role | None,
    role_label: str | None,
    code: str | None,
    title: str,
    message: str,
    primary_label: str,
    secondary_label: str | None = None,
    card: bool = False,
) -> tuple[bool, bool]:
    """Pantalla centrada de estado (A6 · 403, A7 · sesión expirada). Devuelve qué botón se pulsó.

    Con `card=True` es la variante de A7 (V-031): tarjeta blanca con el texto a la izquierda, el
    botón principal a todo el ancho y el secundario como enlace.
    """
    st.space("large")
    render_brand(role_label, role)
    if card:
        with st.container(key="status-card"):
            st.subheader(title, anchor=False)
            st.caption(message)
            primary = st.button(
                primary_label, type="primary", key="status-primary", width="stretch"
            )
            secondary = (
                st.button(secondary_label, key="status-secondary", type="tertiary")
                if secondary_label
                else False
            )
        return primary, secondary
    with st.container(key="status-screen", horizontal_alignment="center"):
        if code:
            st.markdown(f"# :red[{code}]", width="content")
        st.subheader(title, anchor=False, width="content")
        st.caption(message, width="content")
        with st.container(horizontal=True, horizontal_alignment="center"):
            primary = st.button(primary_label, type="primary", key="status-primary")
            secondary = (
                st.button(secondary_label, key="status-secondary") if secondary_label else False
            )
    return primary, secondary
