"""Filas de la ruta (E5 y E5b): número, tema, motivo de inclusión, detalle y estado.

A diferencia de `path_timeline`, el motivo y el detalle van en dos líneas, como en Figma v3. Los
textos ya llegan armados (los arma `services/learning.py` con lo que dice la API).
"""

from collections.abc import Sequence
from dataclasses import dataclass

import streamlit as st

from clients.models import StepStatus
from components.theme import STEP_BADGE


@dataclass(frozen=True)
class PathRow:
    step_id: int
    order: int
    name: str
    status: StepStatus
    reason: str
    detail: str | None = None
    openable: bool = True


def render_path_rows(rows: Sequence[PathRow], *, open_label: str = "Abrir") -> int | None:
    """Dibuja las filas y devuelve el `step_id` del botón pulsado."""
    clicked: int | None = None
    for row in rows:
        label, color = STEP_BADGE[row.status]
        with st.container(border=True, key=f"panel-step-{row.step_id}"):
            number_col, body_col, badge_col, action_col = st.columns(
                [1, 8, 2, 2], vertical_alignment="center"
            )
            number_col.markdown(f"**{row.order}**")
            with body_col:
                st.markdown(f"**{row.name}**")
                st.caption(row.reason)
                if row.detail:
                    st.caption(row.detail)
            with badge_col:
                st.badge(label, color=color)
            with action_col:
                if row.openable and st.button(
                    open_label, key=f"open-step-{row.step_id}", icon=":material/chevron_right:"
                ):
                    clicked = row.step_id
    return clicked
