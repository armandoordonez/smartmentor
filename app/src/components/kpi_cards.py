"""Indicadores en tarjetas (E11, D3, AD2, AD3). El valor ya llega formateado por la página."""

from collections.abc import Sequence
from dataclasses import dataclass

import streamlit as st


@dataclass(frozen=True)
class Kpi:
    key: str
    label: str
    value: str
    help: str | None = None


def render_metric_card(kpi: Kpi) -> None:
    with st.container(key=f"kpi-{kpi.key}"):
        st.metric(kpi.label, kpi.value, help=kpi.help)


def render_kpis(kpis: Sequence[Kpi]) -> None:
    """Fila de tarjetas de indicadores (hasta 4 columnas; se apilan en pantallas angostas)."""
    for column, kpi in zip(st.columns(len(kpis)), kpis, strict=True):
        with column:
            render_metric_card(kpi)
