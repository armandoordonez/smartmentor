"""Línea de la ruta (E5, E5b): cada paso con su estado, su motivo de inclusión y su detalle."""

from collections.abc import Sequence
from dataclasses import dataclass

import streamlit as st

from clients.models import InclusionReason, StepStatus
from components.theme import INCLUSION_REASON_TEXT, STEP_BADGE


@dataclass(frozen=True)
class StepView:
    step_id: int
    order: int
    name: str
    status: StepStatus
    reason: InclusionReason
    detail: str
    """«90 min · intento 2 de 3, último 60 %»."""
    openable: bool = True


def render_path_timeline(steps: Sequence[StepView], *, open_label: str = "Abrir") -> int | None:
    """Dibuja los pasos y devuelve el `step_id` del botón pulsado."""
    clicked: int | None = None
    for step in steps:
        label, color = STEP_BADGE[step.status]
        with st.container(border=True, key=f"panel-step-{step.step_id}"):
            number_col, body_col, badge_col, action_col = st.columns(
                [1, 8, 2, 2], vertical_alignment="center"
            )
            number_col.markdown(f"**{step.order}**")
            with body_col:
                st.markdown(f"**{step.name}**")
                st.caption(f"{INCLUSION_REASON_TEXT[step.reason]} · {step.detail}")
            with badge_col:
                st.badge(label, color=color)
            with action_col:
                if step.openable and st.button(
                    open_label, key=f"open-step-{step.step_id}", icon=":material/chevron_right:"
                ):
                    clicked = step.step_id
    return clicked
