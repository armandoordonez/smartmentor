"""Insignia (E10 y E12): la grande de «¡Ruta completada!» y las casillas de los logros."""

import streamlit as st


def render_badge_hero(title: str, subtitle: str) -> None:
    """Insignia obtenida: ícono, título y subtítulo."""
    with st.container(key="card-badge-hero", horizontal_alignment="center"):
        st.markdown("# :blue[:material/workspace_premium:]", width="content")
        st.header(title, anchor=False, width="content")
        st.caption(subtitle, width="content")


def render_badge_slot(name: str, caption: str, *, obtained: bool, key: str) -> None:
    """Casilla de logro: obtenida (con su fecha) o bloqueada (con lo que falta), con texto."""
    with st.container(key=f"card-badge-{key}", border=False):
        icon = ":material/workspace_premium:" if obtained else ":material/lock:"
        st.markdown(f"#### {icon} {name}")
        st.caption(caption)
        st.badge("Obtenida" if obtained else "Bloqueada", color="green" if obtained else "gray")
