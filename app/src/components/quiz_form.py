"""Pregunta del quiz o del diagnóstico: opciones de una en una y revisión de una respuesta."""

from collections.abc import Sequence
from typing import Any

import streamlit as st

from components.theme import ANSWER_BADGE

DONT_KNOW = -1
"""Valor devuelto por `render_options` cuando se elige «No lo sé»."""

DONT_KNOW_LABEL = "No lo sé"


def render_stem(stem: str, *, key: str) -> None:
    """Enunciado de la pregunta: negrita grande como en Figma (V-033)."""
    with st.container(key=f"question-stem-{key}"):
        st.markdown(f"**{stem}**")


def options_state(
    *,
    options: Sequence[str],
    key: str,
    selected: int | None,
    allow_dont_know: bool = False,
) -> dict[str, Any]:
    """Valor inicial del radio de `render_options`, para ponerlo en `st.session_state`.

    El radio no lleva `index=`: la opción ya elegida entra solo por el estado de sesión, así que al
    restaurar un borrador (B-040) Streamlit no avisa de que el widget tiene un valor por defecto y
    otro por la API de estado de sesión (B-054). La página lo aplica con `seed_defaults`.
    """
    labels = list(options) + ([DONT_KNOW_LABEL] if allow_dont_know else [])
    index = selected if selected is not None and selected != DONT_KNOW else None
    if selected == DONT_KNOW and allow_dont_know:
        index = len(options)
    if index is None or not 0 <= index < len(labels):
        return {}
    return {f"option-{key}": labels[index]}


def render_options(
    *,
    stem: str,
    options: Sequence[str],
    key: str,
    allow_dont_know: bool = False,
) -> int | None:
    """Pregunta de opción múltiple. Devuelve el índice elegido, `DONT_KNOW` o None sin elegir.

    La opción ya elegida la pone la página con `options_state` (el componente no toca
    `st.session_state`).
    """
    labels = list(options) + ([DONT_KNOW_LABEL] if allow_dont_know else [])
    render_stem(stem, key=key)
    choice = st.radio(stem, labels, index=None, label_visibility="collapsed", key=f"option-{key}")
    if choice is None:
        return None
    position = labels.index(choice)
    return DONT_KNOW if allow_dont_know and position == len(options) else position


def render_answer_review(
    *, number: int, stem: str, correct: bool, explanation: str | None = None
) -> None:
    """Fila de «Revisión de respuestas» (E7): la pregunta, si fue correcta y la explicación."""
    label, color = ANSWER_BADGE[correct]
    with st.container(key=f"answer-review-{number}"):
        # Insignia y pregunta en una sola línea, como en Figma (V-045).
        with st.container(
            horizontal=True, vertical_alignment="center", key=f"answer-line-{number}"
        ):
            st.badge(label, color=color)
            st.markdown(f"**Pregunta {number}** · {stem}")
        if explanation:
            st.caption(explanation)
