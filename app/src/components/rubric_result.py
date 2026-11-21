"""Detalle por criterio de la rúbrica de una respuesta corta (E7).

Recibe una vista ya armada (`RubricView`); quien la arma es `services/assessment.py`, a partir del
`grading.v1` que devuelve la API. El resultado de cada criterio va escrito («Cumple», «No cumple»).
Debajo de cada criterio va la razón de la IA y, si hay, la cita de la respuesta del aprendiz
(«En tu respuesta: «…»»). Las calificaciones anteriores al prompt v2 no traen razón (B-038): en
ellas `evidence` se muestra tal cual, como antes.
"""

from dataclasses import dataclass

import streamlit as st


@dataclass(frozen=True)
class CriterionView:
    name: str
    met: bool
    evidence: str
    """Cita literal de la respuesta del aprendiz; vacía si no hay nada que citar."""
    reason: str = ""
    """Por qué se cumple o no el criterio; vacía en calificaciones anteriores al prompt v2."""


@dataclass(frozen=True)
class RubricView:
    criteria: tuple[CriterionView, ...]
    criteria_met: int
    criteria_total: int
    min_met: int | None
    """Mínimo de criterios para contar como correcta (por omisión, 2 de 3)."""
    is_correct: bool
    graded_by: str
    """«IA» o «un instructor»."""


def render_rubric_result(view: RubricView, *, key: str) -> None:
    with st.container(key=f"rubric-{key}"):
        st.markdown(
            f"**Puntaje: {view.criteria_met} de {view.criteria_total} criterios** · "
            f"calificado con {view.graded_by} según la rúbrica"
        )
        if view.min_met is not None:
            verdict = "Cuenta como correcta" if view.is_correct else "No cuenta como correcta"
            st.caption(
                f"{verdict}: cumple {view.criteria_met} de {view.criteria_total} criterios "
                f"(mínimo {view.min_met})."
            )
        for criterion in view.criteria:
            # Verde y rojo como en Figma; el resultado va escrito además del color.
            word, color = ("Cumple", "green") if criterion.met else ("No cumple", "red")
            st.markdown(f":{color}[{word} · {criterion.name}]")
            if criterion.reason:
                st.caption(criterion.reason)
                if criterion.evidence:
                    st.caption(f"En tu respuesta: «{criterion.evidence}»")
            elif criterion.evidence:
                st.caption(criterion.evidence)
