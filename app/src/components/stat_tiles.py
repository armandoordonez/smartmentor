"""Cifras con su etiqueta debajo (E10 y E11), como en Figma: el valor arriba y la etiqueta abajo.

A diferencia de `st.metric` (etiqueta arriba), aquí el orden de lectura es el del diseño.
"""

from collections.abc import Sequence

import streamlit as st


def render_stat_tiles(stats: Sequence[tuple[str, str]], *, key: str) -> None:
    """Una columna por cifra: `(valor, etiqueta)`."""
    for index, (column, (value, label)) in enumerate(
        zip(st.columns(len(stats)), stats, strict=True)
    ):
        with column, st.container(key=f"kpi-{key}-{index}"):
            st.markdown(f"## {value}")
            st.caption(label)
