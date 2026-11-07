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
    exhausted: bool = False,
    title: str = "Historial de intentos",
) -> None:
    with st.container(key=f"attempt-history-{key}"):
        title_col, badge_col = st.columns([4, 2], vertical_alignment="center")
        title_col.subheader(title, anchor=False)
        if exhausted:
            with badge_col:
                st.badge("Intentos agotados", color="orange")
        for row in rows:
            name_col, score_col = st.columns([2, 4])
            extra = " · intento extra" if row.extra_grant else ""
            name_col.markdown(f"**Intento {row.number}**{extra}")
            score_col.markdown(f"{percent_points(row.score)} · {row.correct} de {row.total}")
        if pass_threshold is not None:
            st.caption(f"Necesitas {percent_points(pass_threshold)} para aprobar.")
