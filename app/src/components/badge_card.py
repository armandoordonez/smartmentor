"""Insignia (E10 y E12): la grande de «¡Ruta completada!» y las casillas de los logros."""

import streamlit as st


def render_badge_hero(title: str, subtitle: str) -> None:
    """Insignia obtenida: ícono, título y subtítulo."""
    with st.container(key="card-badge-hero", horizontal_alignment="center"):
        st.markdown("# :blue[:material/workspace_premium:]", width="content")
        st.header(title, anchor=False, width="content")
        st.caption(subtitle, width="content")


def render_badge_slot(
    name: str, caption: str, *, obtained: bool, key: str, action_label: str | None = None
) -> bool:
    """Casilla de logro: obtenida (con su fecha) o bloqueada (con lo que falta).

    El estado va una sola vez, en el texto de `caption` y en el ícono (V-052). Con `action_label`
    se dibuja dentro de la tarjeta un botón («Ver badge») y se devuelve si se pulsó.
    """
    with st.container(key=f"card-badge-{key}", border=False):
        icon = ":material/workspace_premium:" if obtained else ":material/lock:"
        st.markdown(f"#### {icon} {name}")
        st.caption(caption)
        if action_label is None:
            return False
        return st.button(action_label, key=f"view-badge-{key}")
