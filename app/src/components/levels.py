"""Nivel por tema del diagnóstico (E4, D4): nombre, porcentaje y estado escrito además del color."""

from collections.abc import Sequence
from dataclasses import dataclass

import streamlit as st

from clients.models import TopicClassification
from components.formatting import percent_points
from components.theme import LEVEL_BADGE


@dataclass(frozen=True)
class LevelRow:
    topic_id: int
    name: str
    level: float
    """De 0 a 100."""
    classification: TopicClassification


def render_levels(rows: Sequence[LevelRow], *, key: str = "levels") -> None:
    with st.container(border=True, key=f"panel-{key}"):
        for row in rows:
            label, color = LEVEL_BADGE[row.classification]
            name_col, value_col, badge_col = st.columns([5, 1, 2], vertical_alignment="center")
            name_col.markdown(row.name)
            value_col.markdown(f"**{percent_points(row.level)}**")
            with badge_col:
                st.badge(label, color=color)


def render_level_bars(rows: Sequence[LevelRow]) -> None:
    """Variante de D4: nombre, barra y porcentaje, como en Figma (V-021).

    Va dentro de una tarjeta que pone la página. La clasificación no se pinta: la barra y el
    número ya la cuentan, y E4 sigue mostrando la insignia.
    """
    for row in rows:
        name_col, bar_col, value_col = st.columns([5, 4, 1], vertical_alignment="center")
        name_col.markdown(row.name)
        bar_col.progress(min(max(row.level, 0.0), 100.0) / 100)
        value_col.caption(percent_points(row.level))
