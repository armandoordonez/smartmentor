"""Pregunta del quiz o del diagnóstico: opciones de una en una y revisión de una respuesta."""

from collections.abc import Sequence

import streamlit as st

from components.theme import ANSWER_BADGE

DONT_KNOW = -1
"""Valor devuelto por `render_options` cuando se elige «No lo sé»."""

DONT_KNOW_LABEL = "No lo sé"


def render_options(
    *,
    stem: str,
    options: Sequence[str],
    key: str,
    selected: int | None = None,
    allow_dont_know: bool = False,
) -> int | None:
    """Pregunta de opción múltiple. Devuelve el índice elegido, `DONT_KNOW` o None sin elegir."""
    labels = list(options) + ([DONT_KNOW_LABEL] if allow_dont_know else [])
    index = selected if selected is not None and selected != DONT_KNOW else None
    if selected == DONT_KNOW and allow_dont_know:
        index = len(options)
    choice = st.radio(stem, labels, index=index, key=f"option-{key}")
    if choice is None:
        return None
    position = labels.index(choice)
    return DONT_KNOW if allow_dont_know and position == len(options) else position


def render_answer_review(
    *, number: int, stem: str, correct: bool, explanation: str | None = None
) -> None:
    """Fila de «Revisión de respuestas» (E7): la pregunta, si fue correcta y la explicación."""
    label, color = ANSWER_BADGE[correct]
    with st.container(border=True, key=f"panel-review-{number}"):
        st.badge(label, color=color)
        st.markdown(f"**Pregunta {number}** · {stem}")
        if explanation:
            st.caption(explanation)
