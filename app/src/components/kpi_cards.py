"""Tarjetas de indicadores (E11, D3, AD2) y de métricas con meta (AD3)."""

from collections.abc import Sequence

import streamlit as st

from components.theme import BadgeColor

Kpi = tuple[str, str]
"""(valor ya formateado, etiqueta)."""


def render_kpis(items: Sequence[Kpi]) -> None:
    for column, (value, label) in zip(st.columns(len(items)), items, strict=True):
        column.metric(label, value, border=True)


def render_metric_card(value: str, label: str, badge: str, color: BadgeColor) -> None:
    with st.container(border=True):
        st.metric(label, value)
        st.badge(badge, color=color)
