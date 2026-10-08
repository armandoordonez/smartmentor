"""Tabla del diseño: encabezados en mayúsculas grises, celdas con texto, badges o acciones.

`st.dataframe` no muestra badges ni botones dentro de las celdas; por eso cada fila se arma con
columnas. Sirve para listas cortas (decenas de filas), que son las del piloto.
"""

from collections.abc import Sequence
from dataclasses import dataclass

import streamlit as st

from components.theme import BadgeStyle


@dataclass(frozen=True)
class Actions:
    items: tuple[tuple[str, str], ...]
    """(id de la acción, texto del botón)."""


Cell = str | BadgeStyle | Actions | None


@dataclass(frozen=True)
class Row:
    key: str
    cells: Sequence[Cell]


def _render_cell(cell: Cell, key: str) -> str | None:
    if cell is None:
        return None
    if isinstance(cell, Actions):
        clicked = None
        with st.container(horizontal=True, gap="small"):
            for action_id, label in cell.items:
                if st.button(label, key=f"{key}-{action_id}", type="tertiary"):
                    clicked = action_id
        return clicked
    if isinstance(cell, tuple):
        label, color = cell
        st.badge(label, color=color)
        return None
    st.markdown(cell)
    return None


def render_table(
    headers: Sequence[str], widths: Sequence[float], rows: Sequence[Row], *, key: str
) -> tuple[str, str] | None:
    """Dibuja la tabla y devuelve (clave de la fila, acción) si se pulsó una acción."""
    clicked: tuple[str, str] | None = None
    with st.container(border=True, gap="small"):
        for column, header in zip(st.columns(widths), headers, strict=True):
            if header:
                column.caption(f"**{header.upper()}**")
        if not rows:
            st.caption("No hay registros todavía.")
        for row in rows:
            columns = st.columns(widths, vertical_alignment="center")
            for column, cell in zip(columns, row.cells, strict=True):
                with column:
                    action = _render_cell(cell, f"{key}-{row.key}")
                    if action:
                        clicked = (row.key, action)
    return clicked
