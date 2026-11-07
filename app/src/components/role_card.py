"""Tarjeta de rol del selector A1 (solo en modo `fixtures`)."""

import streamlit as st

from clients.models import Role
from components.theme import ROLE_COLOR


def render_role_card(
    *,
    role: Role,
    badge_label: str,
    title: str,
    description: str,
    permissions: str,
    cta_label: str,
    key: str,
) -> bool:
    """Dibuja la tarjeta y devuelve True si se pulsó el botón de entrada."""
    with st.container(key=f"card-role-{key}"):
        st.badge(badge_label, color=ROLE_COLOR[role])
        st.markdown(f"#### {title}")
        st.caption(description)
        st.caption(permissions)
        return st.button(cta_label, type="primary", key=f"enter-{key}")
