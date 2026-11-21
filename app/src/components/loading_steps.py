"""Estado de carga de la IA (U1a a U1d y D1c): tres pasos con su estado escrito además del color.

El componente solo dibuja. El sondeo del trabajo (`GET /jobs/{id}`) lo hace la página, que pasa
el estado de cada paso y, si el trabajo falló, el mensaje de error; el reintento y la salida a la
ruta los decide la página según lo que devuelve este componente.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

import streamlit as st

StepState = Literal["done", "running", "pending", "failed"]

_STATE_TEXT: dict[StepState, str] = {
    "done": "Listo",
    "running": "En curso",
    "pending": "Pendiente",
    "failed": "Falló",
}
_STATE_ICON: dict[StepState, str] = {
    "done": ":material/check_circle:",
    "running": ":material/progress_activity:",
    "pending": ":material/radio_button_unchecked:",
    "failed": ":material/error:",
}
_STATE_COLOR: dict[StepState, str] = {
    "done": "green",
    "running": "blue",
    "pending": "gray",
    "failed": "red",
}
_FOOTNOTE = "Si tarda más: tu avance está guardado; puedes volver a tu ruta."


@dataclass(frozen=True)
class LoadingStep:
    label: str
    state: StepState


def render_loading_steps(
    title: str,
    steps: Sequence[LoadingStep],
    estimate: str,
    *,
    key: str,
    error_message: str | None = None,
    retry_label: str = "Reintentar",
    back_label: str = "Volver a mi ruta",
) -> Literal["retry", "back"] | None:
    """Dibuja la carga y devuelve «retry» o «back» si hay error y se pulsó el botón."""
    result: Literal["retry", "back"] | None = None
    with st.container(key=f"loading-{key}"):
        if not error_message:
            # Anillo grande que gira, como el de Figma; el CSS lo anima (V-088 a V-096).
            with st.container(key=f"spinner-{key}", horizontal_alignment="center"):
                st.markdown(":material/progress_activity:", width="content")
        st.markdown(f"#### {title}", text_alignment="center")
        for step in steps:
            color = _STATE_COLOR[step.state]
            icon = _STATE_ICON[step.state]
            st.markdown(f":{color}[{icon} {_STATE_TEXT[step.state]} · {step.label}]")
        st.caption(f"Tiempo estimado: {estimate}", text_alignment="center")
        if error_message:
            st.error(error_message)
            with st.container(horizontal=True):
                if st.button(retry_label, type="primary", key=f"loading-retry-{key}"):
                    result = "retry"
                if st.button(back_label, key=f"loading-back-{key}"):
                    result = "back"
        else:
            st.caption(_FOOTNOTE, text_alignment="center")
    return result
