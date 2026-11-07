"""Escalas de 1 a 5 de la encuesta final (E13a y E13b): satisfacción, utilidad y SUS."""

from collections.abc import Sequence
from dataclasses import dataclass

import streamlit as st

SCALE_HINT = "1 = Totalmente en desacuerdo · 5 = Totalmente de acuerdo"
SCALE = (1, 2, 3, 4, 5)

# Escala de usabilidad del sistema (SUS), ítems 1 a 10 (E13a y E13b).
SUS_ITEMS: tuple[str, ...] = (
    "Creo que me gustaría usar esta plataforma con frecuencia.",
    "Encontré la plataforma innecesariamente compleja.",
    "Pensé que la plataforma era fácil de usar.",
    "Creo que necesitaría el apoyo de una persona técnica para poder usarla.",
    "Encontré que las funciones de la plataforma estaban bien integradas.",
    "Pensé que había demasiada inconsistencia en la plataforma.",
    "Imagino que la mayoría de las personas aprendería a usarla muy rápido.",
    "Encontré la plataforma muy difícil de usar.",
    "Me sentí muy seguro usando la plataforma.",
    "Necesité aprender muchas cosas antes de poder usar la plataforma.",
)

EXPERIENCE_ITEMS: tuple[tuple[str, str], ...] = (
    ("q1", "Estoy satisfecho con la ruta que seguí."),
    ("q2", "Lo que aprendí me será útil."),
    ("q3", "Me siento capaz de aplicar estos temas por mi cuenta."),
)


@dataclass(frozen=True)
class LikertQuestion:
    code: str
    statement: str


def render_likert(statement: str, *, key: str, value: int | None = None) -> int | None:
    """Una afirmación con su escala de 1 a 5. Devuelve el valor elegido o None."""
    with st.container(key=f"likert-{key}"):
        st.markdown(statement)
        return st.radio(
            statement,
            SCALE,
            index=SCALE.index(value) if value in SCALE else None,
            horizontal=True,
            label_visibility="collapsed",
            key=f"likert-radio-{key}",
        )


def render_likert_block(
    title: str, questions: Sequence[LikertQuestion], *, key: str
) -> dict[str, int | None]:
    """Bloque de afirmaciones con la leyenda de la escala. Devuelve las respuestas por código."""
    st.subheader(title, anchor=False)
    st.caption(SCALE_HINT)
    return {
        question.code: render_likert(question.statement, key=f"{key}-{question.code}")
        for question in questions
    }
