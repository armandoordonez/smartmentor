"""Anotación ciega de una pregunta (D5b): rúbrica de 4 criterios y veredicto.

El evaluador nunca ve la anotación del otro: este componente no recibe datos de ella. Muestra la
respuesta correcta marcada porque el evaluador necesita verla para juzgar el ítem.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

import streamlit as st

CRITERIA: tuple[tuple[str, str], ...] = (
    ("single_correct", "Tiene una sola respuesta correcta"),
    ("clear_stem", "El enunciado es claro"),
    ("bloom_ok", "El nivel de Bloom es correcto"),
    ("plausible_distractors", "Los distractores son plausibles"),
)
_YES, _NO = "Sí", "No"
Verdict = Literal["valid", "invalid"]


@dataclass(frozen=True)
class AnnotationItemView:
    item_id: int
    stem: str
    options: tuple[str, ...]
    correct_index: int | None
    meta: str
    """«Tema 3 · Regresión logística · Bloom: Aplicar»."""


@dataclass(frozen=True)
class AnnotationResult:
    criteria: dict[str, bool | None]
    verdict: Verdict | None
    comment: str
    save: bool
    close: bool

    @property
    def is_complete(self) -> bool:
        return self.verdict is not None and all(v is not None for v in self.criteria.values())


def render_annotation_form(
    item: AnnotationItemView,
    *,
    evaluator_slot: str,
    progress: str,
    key: str,
    criteria: Sequence[tuple[str, str]] = CRITERIA,
    ratio: float | None = None,
) -> AnnotationResult:
    """Formulario de anotación, con la distribución de Figma D5b (V-026).

    `evaluator_slot` es «Evaluador 1 de 2», `progress` es «23 de 60 anotadas» y `ratio`, la
    fracción anotada para la barra (sin ella no se dibuja).
    """
    with st.container(horizontal=True, vertical_alignment="center"):
        st.markdown("#### Anotar pregunta", width="content")
        st.space("stretch")
        st.badge(evaluator_slot, color="violet")
    st.caption(progress)
    if ratio is not None:
        st.progress(min(max(ratio, 0.0), 1.0))
    with st.container(key=f"panel-{key}-item"):
        st.caption(item.meta)
        st.markdown(f"**{item.stem}**")
        for position, option in enumerate(item.options):
            letter = "ABCDEFGH"[position]
            if item.correct_index == position:
                st.markdown(f":green[**{letter}. {option}  ← correcta**]")
            else:
                st.markdown(f"{letter}. {option}")
    st.caption("**RÚBRICA**")
    answers: dict[str, bool | None] = {}
    for code, label in criteria:
        label_col, choice_col = st.columns([4, 1], vertical_alignment="center")
        label_col.markdown(label)
        choice = choice_col.segmented_control(
            label,
            (_YES, _NO),
            selection_mode="single",
            label_visibility="collapsed",
            key=f"{key}-{item.item_id}-{code}",
        )
        answers[code] = None if choice is None else choice == _YES
    st.caption("**VEREDICTO**")
    verdict_choice = st.segmented_control(
        "Veredicto",
        ("Válida", "No válida"),
        selection_mode="single",
        label_visibility="collapsed",
        key=f"{key}-{item.item_id}-verdict",
    )
    comment = st.text_area("Comentario", key=f"{key}-{item.item_id}-comment")
    with st.container(key=f"{key}-blind-note"):
        st.caption(
            "Anotación ciega: no ves la del otro evaluador hasta que ambos terminen. "
            "Así el kappa de Cohen es válido."
        )
    verdict: Verdict | None = (
        None if verdict_choice is None else ("valid" if verdict_choice == "Válida" else "invalid")
    )
    with st.container(horizontal=True):
        close = st.button("Cerrar", key=f"{key}-close")
        result = AnnotationResult(answers, verdict, comment.strip(), save=False, close=close)
        save = st.button(
            "Guardar y siguiente",
            type="primary",
            key=f"{key}-save",
            disabled=not result.is_complete,
        )
    return AnnotationResult(answers, verdict, comment.strip(), save=save, close=close)
