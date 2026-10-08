"""Nivel por tema según el diagnóstico (E4 y D4)."""

from collections.abc import Sequence

import streamlit as st

from clients.models import TopicLevel
from components.formatting import percent
from components.theme import LEVEL_BADGE


def render_levels(levels: Sequence[TopicLevel], *, title: str | None = None) -> None:
    with st.container(border=True):
        if title:
            st.caption(f"**{title}**")
        for level in levels:
            label, color = LEVEL_BADGE[level.status]
            name, score, badge = st.columns([8, 1, 1.6], vertical_alignment="center")
            name.markdown(level.topic_title)
            score.markdown(f":gray[{percent(level.score)}]")
            with badge.container(horizontal=True, horizontal_alignment="right"):
                st.badge(label, color=color)
