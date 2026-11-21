"""Filas de la ruta (E5 y E5b): número, tema, motivo de inclusión, detalle y estado.

A diferencia de `path_timeline`, el motivo y el detalle van en dos líneas, como en Figma v3. Los
textos ya llegan armados (los arma `services/learning.py` con lo que dice la API).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

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
    tone: Literal["green", "blue"] | None = None
    """Color de la línea del motivo: verde si se omitió, azul si se incluyó por el diagnóstico."""


def render_path_rows(
    rows: Sequence[PathRow], *, open_label: str = "Abrir", grouped: bool = False
) -> int | None:
    """Dibuja las filas y devuelve el `step_id` del botón pulsado.

    Con `grouped=True` (E5b) van en una sola tarjeta con separadores; si no (E5), cada fila es una
    tarjeta compacta y la que está en curso lleva borde azul.
    """
    if grouped:
        with st.container(key="card-path-rows"):
            return _render_rows(rows, open_label)
    return _render_rows(rows, open_label)


def _render_rows(rows: Sequence[PathRow], open_label: str) -> int | None:
    clicked: int | None = None
    for row in rows:
        label, color = STEP_BADGE[row.status]
        current = "-current" if row.status == "in_progress" else ""
        with st.container(border=True, key=f"panel-step-{row.step_id}{current}"):
            number_col, body_col, badge_col, action_col = st.columns(
                [1, 12, 2, 2], vertical_alignment="center"
            )
            number_col.markdown(f"**{row.order}**")
            with body_col, st.container(key=f"step-body-{row.step_id}"):
                st.markdown(f"**{row.name}**")
                reason = f":{row.tone}[{row.reason}]" if row.tone and row.reason else row.reason
                st.caption(f"{reason}  \n{row.detail}" if row.detail else reason)
            with badge_col:
                st.badge(label, color=color)
            with action_col:
                if row.openable and st.button(
                    open_label, key=f"open-step-{row.step_id}", icon=":material/chevron_right:"
                ):
                    clicked = row.step_id
    return clicked
