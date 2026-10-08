"""Tarjeta de una ruta en el catálogo (E1, nodo 5:19 de Figma)."""

import streamlit as st

from clients.models import LearningPath
from components.layout import eyebrow


def render_path_card(path: LearningPath, *, enrolled: bool) -> bool:
    """Devuelve True cuando el estudiante abre la ruta."""
    with st.container(border=True, height="stretch"):
        if path.highlight:
            eyebrow(path.highlight.upper())
        st.subheader(path.title, anchor=False)
        st.caption(f"{path.topic_count} temas · ~{path.estimated_hours} h · {path.level}")
        return st.button(
            "Continuar ruta" if enrolled else "Ver ruta",
            key=f"open-path-{path.id}",
            type="primary",
        )
