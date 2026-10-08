"""Preguntas de opción múltiple (diagnóstico, quiz del tema y evaluación final) y la revisión de
respuestas (E7)."""

from collections.abc import Sequence

import streamlit as st

from clients.models import AnswerReview, Question
from components.theme import ANSWER_BADGE


def render_options(question: Question, *, selected: int | None, key: str) -> int | None:
    """Opciones de la pregunta. Devuelve el índice elegido (o None si aún no elige)."""
    options = list(range(len(question.options)))
    choice: int | None = st.radio(
        question.prompt,
        options,
        index=selected,
        format_func=lambda i: question.options[i],
        key=f"{key}-{question.id}",
        label_visibility="collapsed",
        width="stretch",
    )
    return choice


def render_answer_review(reviews: Sequence[AnswerReview]) -> None:
    with st.container(border=True):
        st.markdown("#### Revisión de respuestas")
        for review in reviews:
            label, color = ANSWER_BADGE[review.correct]
            with st.container(horizontal=True, vertical_alignment="center"):
                st.badge(label, color=color)
                st.markdown(f"Pregunta {review.number} · {review.prompt}")
