"""Tarjeta de ruta del catálogo (E1): antetítulo, nombre, descripción, meta y botón."""

from dataclasses import dataclass

import streamlit as st

from components.layout import eyebrow


@dataclass(frozen=True)
class PathCardView:
    path_id: int
    name: str
    meta: str
    """«5 temas · ~8 h · Intermedio»."""
    tag_text: str | None = None
    """Antetítulo («RECOMENDADA PARA TI»)."""
    description: str | None = None


def render_path_card(card: PathCardView, *, cta_label: str = "Ver ruta") -> bool:
    """Dibuja la tarjeta y devuelve True si se pulsó el botón."""
    with st.container(key=f"path-card-{card.path_id}", border=False):
        if card.tag_text:
            eyebrow(card.tag_text)
        with st.container(key=f"path-title-{card.path_id}"):
            st.markdown(card.name)
        if card.description:
            st.caption(card.description)
        st.caption(card.meta)
        return st.button(cta_label, type="primary", key=f"open-path-{card.path_id}")
