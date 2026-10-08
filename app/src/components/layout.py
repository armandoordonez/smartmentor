"""Piezas comunes de todas las pantallas: barra superior (componente Nav de Figma), encabezado de
página, aviso de permisos y pantallas de estado (403, sesión vencida).
"""

from collections.abc import Sequence

import streamlit as st

from clients.models import Role
from components.formatting import initials
from components.theme import ROLE_BADGE

NavLink = tuple[str, str]
"""(ruta del archivo de la página, texto del enlace)."""


def eyebrow(text: str) -> None:
    """Antetítulo azul en negrita («PASO 1 DE 3 · PERFIL», «RECOMENDADA PARA TI»)."""
    st.markdown(f":small[:blue[**{text}**]]")


def render_brand(role: Role | None = None) -> None:
    with st.container(horizontal=True, horizontal_alignment="center", vertical_alignment="center"):
        st.markdown("### :blue[:material/school:] SmartMentor", width="content")
        if role is not None:
            label, color = ROLE_BADGE[role]
            st.badge(label, color=color)


def render_header(role: Role, full_name: str, email: str, links: Sequence[NavLink]) -> bool:
    """Barra superior con la marca, el rol, los enlaces del rol y el menú de la cuenta.

    Devuelve True si el usuario eligió cambiar de rol.
    """
    label, color = ROLE_BADGE[role]
    with st.container(border=True, horizontal=True, vertical_alignment="center", gap="medium"):
        st.markdown(":blue[:material/school:] **SmartMentor**", width="content")
        st.badge(label, color=color)
        st.space("stretch")
        for path, text in links:
            st.page_link(path, label=text)
        with st.popover(initials(full_name), type="tertiary"):
            st.markdown(f"**{full_name}**")
            st.caption(email)
            return st.button("Cambiar de rol", icon=":material/swap_horiz:", key="switch-role")


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


def render_notice(text: str) -> None:
    """Aviso ámbar de permisos o reglas («Tu rol: Docente · Solo ves...»)."""
    st.warning(text)


def render_status_screen(
    *,
    role: Role | None,
    code: str | None,
    title: str,
    message: str,
    primary_label: str,
    secondary_label: str | None = None,
) -> tuple[bool, bool]:
    """Pantalla centrada de estado (A6 · 403, A7 · sesión expirada). Devuelve qué botón se pulsó."""
    st.space("large")
    render_brand(role)
    with st.container(horizontal_alignment="center"):
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
