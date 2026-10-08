"""Tarjeta de rol del selector de entrada (A1)."""

import streamlit as st

from clients.models import Role
from components.theme import ROLE_BADGE


def render_role_card(role: Role, *, title: str, description: str, can: str, cannot: str) -> bool:
    label, color = ROLE_BADGE[role]
    with st.container(border=True, height="stretch"):
        st.badge(label, color=color)
        st.subheader(title, anchor=False)
        st.markdown(f":gray[{description}]")
        st.caption(f"{can}  \n{cannot}")
        return st.button(f"Entrar como {label.lower()}", key=f"enter-{role}", type="primary")
