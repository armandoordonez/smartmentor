"""Historial de intentos (E7c, E9c, D4b): un intento por fila y el aviso de intentos agotados."""

from collections.abc import Sequence
from dataclasses import dataclass

import streamlit as st

from components.formatting import percent_points


@dataclass(frozen=True)
class AttemptRow:
    number: int
    score: float
    """De 0 a 100."""
    correct: int
    total: int
    extra_grant: bool = False
    """El intento salió de un permiso del instructor (se reporta aparte)."""


def render_attempt_history(
    rows: Sequence[AttemptRow],
    *,
    key: str,
    pass_threshold: float | None = None,
    threshold_goal: str = "aprobar",
    exhausted: bool = False,
    title: str = "Historial de intentos",
) -> None:
    with st.container(key=f"card-attempts-{key}"):
        # Título e insignia en una línea, como en Figma (V-047).
        with st.container(
            horizontal=True, vertical_alignment="center", key=f"attempts-title-{key}"
        ):
            st.subheader(title, anchor=False)
            if exhausted:
                st.badge("Intentos agotados", color="orange")
        for row in rows:
            name_col, score_col = st.columns([1, 1])
            extra = " · intento extra" if row.extra_grant else ""
            name_col.markdown(f"**Intento {row.number}**{extra}")
            with score_col.container(key=f"attempt-score-{key}-{row.number}"):
                st.markdown(f":red[{percent_points(row.score)} · {row.correct} de {row.total}]")
        if pass_threshold is not None:
            # Un solo texto de umbral por tarjeta; `threshold_goal` dice para qué es (B-059).
            st.caption(f"Necesitas {percent_points(pass_threshold)} para {threshold_goal}.")
