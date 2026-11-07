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
