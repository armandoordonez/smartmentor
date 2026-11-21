"""E4 · Resultado del diagnóstico y objetivo (paso 4 de 4) y E4b · Editar el objetivo.

Muestra el nivel por tema y el objetivo propuesto por la IA. «Confirmar» o «Guardar objetivo»
llaman a `PUT /me/enrollments/{id}/objective`; el objetivo medible y el verbo de Bloom los valida
la API (`OBJECTIVE_NOT_MEASURABLE`, `INVALID_BLOOM_VERB`) y el error se muestra con el texto de
`core/errors.py`. La pantalla que sigue la dicta el `next_action` de la respuesta, salvo que si
apunta al primer tema se pasa antes por la ruta (E5, B-044).

`result.proposed_objective` es la propuesta original guardada por la API, aparte del objetivo
confirmado (B-033): «Volver a la propuesta de la IA» la usa aunque el objetivo ya se haya editado.
"""

import streamlit as st

from clients.base import ApiError
from clients.models import DiagnosticResult, Objective
from components.layout import eyebrow, render_action_row, render_page_header
from components.levels import LevelRow, render_levels
from components.objective_editor import (
    ObjectiveDraft,
    objective_editor_state,
    render_objective_editor,
)
from core.container import get_client
from core.errors import show_action_error
from core.learner_flow import current_enrollment, go_to_action, redirect_unless, remember
from core.navigation import page_for_next_action
from core.session import get_session
from core.widget_state import seed_defaults

PAGE = "pages/learner/diagnostic_result.py"
PATH_PAGE = "pages/learner/path.py"
TOPIC_PAGE = "pages/learner/topic.py"
FORMULA = (
    "Nivel por tema: diagnóstico 80 % + hoja de vida 10 % + descripción 10 %. Si falta un dato, "
    "su peso pasa al diagnóstico. Desde 80 % el tema se omite."
)
ORIGIN_LABEL = {
    "llm_proposed": "OBJETIVO PROPUESTO PARA TI · GENERADO CON IA",
    "learner_edited": "TU OBJETIVO · EDITADO POR TI",
    "path_default": "OBJETIVO DE LA RUTA",
}
DEFAULT_ORIGIN_LABEL = "TU OBJETIVO"
# Porcentaje de la nota verde de E4b, tal como aparece en Figma (V-041).
PASS_THRESHOLD_NOTE = 80

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

objective: Objective | None = enrollment.objective or result.proposed_objective
if objective is None:
    # La IA no propuso objetivo: la persona lo escribe (E4b).
    state.edit_objective = True

eyebrow("PASO 4 DE 4 · OBJETIVO")
render_page_header("Tu punto de partida", caption=FORMULA)
render_levels(
    [LevelRow(t.topic_id, t.name, t.level, t.classification) for t in result.level_by_topic]
)

if objective is not None:
    with st.container(key="card-objective"):
        eyebrow(ORIGIN_LABEL.get(objective.origin or "", DEFAULT_ORIGIN_LABEL))
        st.markdown(objective.statement)


def _save(chosen: Objective) -> None:
    try:
        updated = client.set_objective(enrollment.id, chosen)
    except ApiError as error:
        show_action_error(error)
        return
    state.edit_objective = False
    if page_for_next_action(updated.next_action) == TOPIC_PAGE:
        # B-044: al confirmar el objetivo la API apunta al primer tema (E6); antes se ve la ruta
        # (E5), cuyo botón principal sigue ese mismo `next_action`.
        remember(updated.next_action)
        st.switch_page(PATH_PAGE)
    go_to_action(updated.next_action)


def _forget_editor_fields() -> None:
    """Borra lo escrito en el editor (E4b).

    E4 termina en `st.stop()` y Streamlit 1.67 conserva el estado de un widget con `key` aunque
    no se dibuje; sin esto, al volver a editar se veía lo cancelado en vez del objetivo.
    """
    for suffix in ("verb", "content", "criterion"):
        st.session_state.pop(f"objective-{suffix}", None)


# --- E4b · Editar el objetivo (ventana modal) ---------------------------------------------------


def _close_editor() -> None:
    """Cierra la ventana (también con la «x» o Esc) y descarta lo escrito."""
    state.edit_objective = False
    st.session_state.pop("objective-use-proposal", None)
    _forget_editor_fields()


@st.dialog("Editar tu objetivo", width="medium", on_dismiss=_close_editor)
def _edit_dialog() -> None:
    proposal = result.proposed_objective
    base = (proposal if st.session_state.get("objective-use-proposal") else None) or objective
    draft = (
        ObjectiveDraft(base.bloom_verb, base.content, base.criterion)
        if base
        else ObjectiveDraft("", "", "")
    )
    # El valor inicial entra por el estado de sesión y no pisa un borrador restaurado (B-054).
    seed_defaults(objective_editor_state(draft, key="objective"))
    editor = render_objective_editor(
        draft,
        key="objective",
        can_reset=proposal is not None,
        topics_count=sum(1 for t in result.level_by_topic if t.classification != "mastered"),
        pass_threshold=PASS_THRESHOLD_NOTE,
    )
    if editor.cancel:
        _close_editor()
        st.rerun()
    if editor.reset_to_proposal:
        _forget_editor_fields()
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


if objective is not None:
    _, actions = render_action_row("objective")
    with actions:
        edit = st.button("Editar el objetivo", key="objective-edit")
        confirm = st.button("Confirmar y ver mi ruta", type="primary", key="objective-confirm")
    if edit:
        state.edit_objective = True
        _forget_editor_fields()
        st.rerun()
    if confirm:
        _save(objective)

if state.edit_objective:
    _edit_dialog()
