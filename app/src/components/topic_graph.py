"""Grafo de temas (D2d): cada flecha va de un prerrequisito al tema que lo necesita.

Usa `st.graphviz_chart` (sin librerías nuevas). Los colores del grafo salen de `tokens.css` por
`core.styles.token`, no se escriben aquí. El estado de revisión de cada tema va también en el texto
del nodo, no solo en el color.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

import streamlit as st

from core.styles import token

ReviewState = Literal["unchanged", "corrected", "added"]

_STATE_TEXT: dict[ReviewState, str] = {
    "unchanged": "Sin cambios",
    "corrected": "Corregido",
    "added": "Agregado por ti",
}
_STATE_COLORS: dict[ReviewState, tuple[str, str]] = {
    # (relleno, borde) como nombres de tokens.
    "unchanged": ("bg-neutral", "text-secondary"),
    "corrected": ("learner-soft", "learner-accent"),
    "added": ("instructor-soft", "instructor-accent"),
}


@dataclass(frozen=True)
class GraphNode:
    topic_id: int
    label: str
    detail: str
    """«Bloom · Aplicar»."""
    state: ReviewState = "unchanged"


@dataclass(frozen=True)
class GraphEdge:
    source: int
    target: int


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def build_dot(nodes: Sequence[GraphNode], edges: Sequence[GraphEdge]) -> str:
    """DOT del grafo, de izquierda a derecha. Los textos se escapan: vienen de la API."""
    lines = [
        "digraph topics {",
        "  rankdir=LR;",
        f'  node [shape=box, style="rounded,filled", fontname="Inter", '
        f'fontcolor="{token("text-primary")}", color="{token("border-field")}"];',
        f'  edge [color="{token("text-tertiary")}"];',
    ]
    for node in nodes:
        fill, border = _STATE_COLORS[node.state]
        label = f"{node.label}\\n{node.detail}\\n{_STATE_TEXT[node.state]}"
        lines.append(
            f'  t{node.topic_id} [label="{_escape(label)}", '
            f'fillcolor="{token(fill)}", color="{token(border)}"];'
        )
    lines.extend(f"  t{edge.source} -> t{edge.target};" for edge in edges)
    lines.append("}")
    return "\n".join(lines)


def render_topic_graph(
    nodes: Sequence[GraphNode], edges: Sequence[GraphEdge], *, validated: bool
) -> None:
    """Dibuja el grafo y el estado «Sin ciclos · validado» (la API valida; aquí solo se informa)."""
    if validated:
        st.badge("Sin ciclos · validado", color="green", icon=":material/check:")
    else:
        st.badge("Con ciclos · sin validar", color="orange", icon=":material/warning:")
    st.graphviz_chart(build_dot(nodes, edges), width="stretch")
