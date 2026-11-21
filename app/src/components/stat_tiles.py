"""Cifras con su etiqueta debajo (E10 y E11), como en Figma: el valor arriba y la etiqueta abajo.

A diferencia de `st.metric` (etiqueta arriba), aquí el orden de lectura es el del diseño.
"""

from collections.abc import Sequence

import streamlit as st


def render_stat_tiles(
    stats: Sequence[tuple[str, str]], *, key: str, single_card: bool = False
) -> None:
    """Una columna por cifra: `(valor, etiqueta)`.

    Con `single_card` las cifras van juntas en una sola tarjeta compacta y centrada (E10); por
    omisión, una tarjeta por cifra (E11).
    """
    if single_card:
        with st.container(key=f"card-{key}-stats"):
            for column, (value, label) in zip(st.columns(len(stats)), stats, strict=True):
                with column:
                    st.markdown(f"## {value}", text_alignment="center")
                    st.caption(label, text_alignment="center")
        return
    for index, (column, (value, label)) in enumerate(
        zip(st.columns(len(stats)), stats, strict=True)
    ):
        with column, st.container(key=f"kpi-{key}-{index}"):
            st.markdown(f"## {value}")
            st.caption(label)
