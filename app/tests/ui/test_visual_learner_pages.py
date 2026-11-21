"""Correcciones visuales del recorrido real frente a Figma v3 (V-088 a V-096).

E7b, E9, E10, U1a a U1d, E4b, E3 y A3c. Lo que dibuja el CSS se comprueba leyendo el archivo; lo
que decide la página, con `AppTest`.
"""

from apptest import button, container_keys, page_texts, session_of
from learner_support import (
    BADGE,
    DIAGNOSTIC,
    DIAGNOSTIC_RESULT,
    FINAL_RESULT,
    QUIZ_RESULT,
    client_of,
    learner_app,
    no_exception,
)
from streamlit.testing.v1 import AppTest
from support import APP_DIR

from clients.models import AttemptResult

STYLES = APP_DIR / "src" / "static" / "styles" / "components"
ALT_VIEW = "OTRA FORMA DE VERLO · GENERADO CON IA"
DATA_RIGHTS = "pages/common/data_rights.py"


def _css(name: str) -> str:
    return (STYLES / name).read_text("utf-8")


def _has_key(at: AppTest, fragment: str) -> bool:
    return any(fragment in key for key in container_keys(at))


# --- E7b · «Otra forma de verlo» -----------------------------------------------------------------


def _failed_result(at: AppTest, *, remedial: int | None) -> None:
    """La API real aún no genera la explicación alterna: sin `remedial_resource_id`."""
    client = client_of(at)
    original = client.get_attempt_result

    def result(attempt_id: int) -> AttemptResult:
        return original(attempt_id).model_copy(update={"remedial_resource_id": remedial})

    client.get_attempt_result = result  # type: ignore[method-assign]


def _e7b(*, remedial: int | None) -> AppTest:
    at = learner_app("learner_quiz_failed", QUIZ_RESULT, run=False)
    session_of(at).learner.step_id = 813
    _failed_result(at, remedial=remedial)
    at.run()
    return at


def test_e7b_alternative_view_card_needs_the_remedial_resource() -> None:
    with_card = _e7b(remedial=121)
    no_exception(with_card)
    shown = page_texts(with_card)
    assert _has_key(with_card, "card-alt-view")
    assert any(ALT_VIEW.split(" · ")[0] in t.upper() for t in shown)
    without = _e7b(remedial=None)
    no_exception(without)
    assert not _has_key(without, "card-alt-view")
    assert not any(ALT_VIEW in t for t in page_texts(without))
    # Sin la tarjeta, la página sigue completa: revisión, próximo intento y reintento.
    assert "Revisión de respuestas" in page_texts(without)
    assert "Reintentar con preguntas nuevas" in page_texts(without)


def test_e7b_header_does_not_promise_the_alternative_view_without_it_b052() -> None:
    with_card = " ".join(page_texts(_e7b(remedial=121)))
    without = " ".join(page_texts(_e7b(remedial=None)))
    assert "te mostramos otra forma de verlo" in with_card
    assert "otra forma de verlo" not in without.lower()
    assert "el próximo intento trae preguntas nuevas" in without


# --- E9 · una sola tarjeta ----------------------------------------------------------------------


def test_e9_weak_topics_are_rows_of_one_card() -> None:
    at = learner_app("learner_final_failed", FINAL_RESULT)
    no_exception(at)
    assert sum("card-weak-topics" in key for key in container_keys(at)) == 1
    assert not _has_key(at, "panel-weak-")
    # Una fila por tema, con su botón.
    assert at.button(key="review-topic-12") is not None
    assert len([b for b in at.button if b.label == "Repasar tema"]) == 2


# --- E10 · KPI en una tarjeta y «Descargar JSON» dentro del expansor -----------------------------


def test_e10_stats_share_one_compact_card() -> None:
    at = learner_app("learner_badge", BADGE)
    no_exception(at)
    assert _has_key(at, "card-badge-stats")
    assert not _has_key(at, "kpi-badge-")
    css = _css("kpi_cards.css")
    assert ".st-key-card-badge-stats" in css
    assert "max-width" in css


def test_e10_json_download_lives_inside_the_verification_expander() -> None:
    at = learner_app("learner_badge", BADGE)
    no_exception(at)
    expander = next(e for e in at.expander if e.label == "Verificación pública")
    inside = [str(getattr(d, "key", "")) for d in expander.get("download_button")]
    assert any("badge-download-json" in key for key in inside)
    everywhere = [str(getattr(d, "key", "")) for d in at.get("download_button")]
    assert sum("badge-download-json" in key for key in everywhere) == 1
    assert any("badge-download" in key and "json" not in key for key in everywhere)


# --- U1a a U1d · anillo de progreso -------------------------------------------------------------


def test_u1_loading_card_has_a_big_spinning_ring_while_running() -> None:
    at = learner_app("learner_calculating", DIAGNOSTIC)
    no_exception(at)
    assert _has_key(at, "spinner-diagnostic")
    assert any(e.value == ":material/progress_activity:" for e in at.markdown)
    css = _css("loading_steps.css")
    assert "animation:" in css and "@keyframes" in css
    assert "prefers-reduced-motion" in css
    assert "vh auto 0" in css  # la tarjeta baja hacia el centro de la ventana


def test_u1_failed_loading_has_no_spinner() -> None:
    at = learner_app("learner_calculating_error", DIAGNOSTIC)
    at.run()
    no_exception(at)
    assert not _has_key(at, "spinner-")


# --- E4b · botones a la derecha del enlace --------------------------------------------------------


def test_e4b_cancel_and_save_sit_on_the_right_of_the_proposal_link() -> None:
    at = learner_app("learner_objective", DIAGNOSTIC_RESULT)
    button(at, "Editar el objetivo").click().run()
    no_exception(at)
    keys = container_keys(at)
    assert any("action-row-objective-editor-left" in k for k in keys)
    assert any("action-row-objective-editor-right" in k for k in keys)
    # Los botones conservan sus `key` y su orden: enlace primero, luego «Cancelar» y «Guardar».
    labels = [b.label for b in at.button if b.key and b.key.startswith("objective-")]
    assert labels[-3:] == ["Volver a la propuesta de la IA", "Cancelar", "Guardar objetivo"]
    assert at.button(key="objective-reset").proto.type == "tertiary"
    assert at.button(key="objective-save").proto.type == "primary"


# --- E3 · sin título y «No lo sé» como enlace ---------------------------------------------------


def test_e3_has_no_title_above_the_question_and_dont_know_is_a_link() -> None:
    at = learner_app("learner_diagnostic", DIAGNOSTIC)
    no_exception(at)
    assert not at.title
    assert any(t.startswith("PASO 3 DE 4 · DIAGNÓSTICO") for t in page_texts(at))
    dont_know = next(b for b in at.button if b.label == "No lo sé")
    assert dont_know.proto.type == "tertiary"
    assert "-dont-know-" in (dont_know.key or "")
    assert "-dont-know-" in _css("quiz_form.css")


def test_e3_dont_know_still_saves_the_answer() -> None:
    at = learner_app("learner_diagnostic", DIAGNOSTIC)
    button(at, "No lo sé").click().run()
    no_exception(at)
    assert any(a.dont_know for a in session_of(at).learner.sheet.answers.values())


# --- A3c · el título dentro de la tarjeta -------------------------------------------------------


def test_a3c_who_sees_each_datum_title_and_table_share_one_card() -> None:
    at = learner_app("learner", DATA_RIGHTS)
    no_exception(at)
    assert sum("card-rights-who-sees" in key for key in container_keys(at)) == 1
    assert "Quién ve cada dato" in page_texts(at)
    css = _css("data_rights.css")
    assert ".st-key-card-rights-who-sees" in css
