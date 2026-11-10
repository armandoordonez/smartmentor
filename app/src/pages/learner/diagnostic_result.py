"""E4 · Resultado del diagnóstico y objetivo (paso 4 de 4) y E4b · Editar el objetivo.

Muestra el nivel por tema y el objetivo propuesto por la IA. «Confirmar» o «Guardar objetivo»
llaman a `PUT /me/enrollments/{id}/objective`; el objetivo medible lo valida la API
(`OBJECTIVE_NOT_MEASURABLE`). La pantalla que sigue la dicta el `next_action` de la respuesta.
"""

import streamlit as st

from clients.base import ApiError
from clients.models import DiagnosticResult, Objective
from components.layout import eyebrow, render_page_header
from components.levels import LevelRow, render_levels
from components.objective_editor import ObjectiveDraft, render_objective_editor
from core.container import get_client
from core.errors import show_action_error
from core.learner_flow import current_enrollment, go_to_action, redirect_unless
from core.session import get_session

PAGE = "pages/learner/diagnostic_result.py"
FORMULA = (
    "Nivel por tema: diagnóstico 80 % + hoja de vida 10 % + descripción 10 %. Si falta un dato, "
    "su peso pasa al diagnóstico. Desde 80 % el tema se omite."
)
ORIGIN_LABEL = {
    "llm_proposed": "OBJETIVO PROPUESTO PARA TI · GENERADO CON IA",
    "learner_edited": "TU OBJETIVO · EDITADO POR TI",
    "path_default": "OBJETIVO DE LA RUTA",
}

client = get_client()
state = get_session().learner

enrollment = current_enrollment(client)
if not state.edit_objective:
    redirect_unless(enrollment, {"confirm_objective"}, PAGE)

try:
    result: DiagnosticResult = client.get_diagnostic_result(enrollment.id)
except ApiError as error:
    show_action_error(error)
    st.stop()

objective: Objective = enrollment.objective or result.proposed_objective

eyebrow("PASO 4 DE 4 · OBJETIVO")
render_page_header("Tu punto de partida", caption=FORMULA)
render_levels(
    [LevelRow(t.topic_id, t.name, t.level, t.classification) for t in result.level_by_topic]
)

with st.container(key="card-objective"):
    eyebrow(ORIGIN_LABEL[objective.origin])
    st.markdown(f"**{objective.statement}**")


def _save(chosen: Objective) -> None:
    try:
        updated = client.set_objective(enrollment.id, chosen)
    except ApiError as error:
        show_action_error(error)
        return
    state.edit_objective = False
    go_to_action(updated.next_action)


if not state.edit_objective:
    edit_col, confirm_col = st.columns(2)
    if edit_col.button("Editar el objetivo", key="objective-edit"):
        state.edit_objective = True
        st.rerun()
    if confirm_col.button("Confirmar y ver mi ruta", type="primary", key="objective-confirm"):
        _save(objective)
    st.stop()

# --- E4b · Editar el objetivo -------------------------------------------------------------------

proposal = result.proposed_objective
base = proposal if st.session_state.get("objective-use-proposal") else objective
editor = render_objective_editor(
    ObjectiveDraft(base.bloom_verb, base.content, base.criterion),
    key="objective",
    topics_count=sum(1 for t in result.level_by_topic if t.classification != "mastered"),
)
if editor.cancel:
    state.edit_objective = False
    st.session_state.pop("objective-use-proposal", None)
    st.rerun()
if editor.reset_to_proposal:
    for suffix in ("verb", "content", "criterion"):
        st.session_state.pop(f"objective-{suffix}", None)
    st.session_state["objective-use-proposal"] = True
    st.rerun()
if editor.save:
    _save(
        Objective(
            statement=editor.draft.statement,
            bloom_verb=editor.draft.bloom_verb,
            content=editor.draft.content,
            criterion=editor.draft.criterion,
            origin="learner_edited",
        )
    )
