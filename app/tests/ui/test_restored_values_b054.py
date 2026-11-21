"""B-054: restaurar un borrador sobre widgets que reciben su valor de la API no debe avisar.

Streamlit avisa («The widget with key X was created with a default value but also had its value
set via the Session State API») cuando un widget con `key` lleva `value=`/`index=`/`default=` y
su valor se puso por `st.session_state` en esa misma ejecución, como hace
`widget_state.apply_form_values` en `main.py` al volver de Keycloak (B-040). `AppTest` no sirve
para ponerlo desde fuera (compacta lo que se escribe en `at.session_state` antes de correr), así
que aquí el borrador se aplica dentro de la ejecución, justo después de `set_page_config`.
"""

from typing import Any

import pytest
from apptest import button, session_of, signed_in
from learner_support import (
    DIAGNOSTIC_RESULT,
    PROGRESS,
    QUIZ,
    SURVEY,
    learner_app,
    no_exception,
)
from staff_support import assert_no_exception, click, staff_app
from staff_support import staff_text_reader as staff_text_reader
from streamlit.elements.lib import policies
from streamlit.testing.v1 import AppTest

SYLLABUS = "pages/instructor/syllabus_review.py"
PARTICIPATE_LABEL = "Acepto participar en el piloto y el uso anónimo de mis datos"


def _session_state_warnings(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [r.getMessage() for r in caplog.records if "Session State API" in r.getMessage()]


@pytest.fixture
def fresh_warning_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    """Streamlit avisa una sola vez por proceso: se reinicia para que la prueba lo vea."""
    monkeypatch.setattr(policies, "_shown_default_value_warning", False)


def _restore_on_next_run(monkeypatch: pytest.MonkeyPatch, drafts: dict[str, Any]) -> None:
    """Pone `drafts` en `st.session_state` al inicio de la próxima ejecución, como `main.py`."""
    from core import styles, widget_state

    original = styles.inject_styles
    pending = [drafts]

    def inject_styles() -> None:
        if pending:
            widget_state.apply_form_values(pending.pop())
        original()

    monkeypatch.setattr(styles, "inject_styles", inject_styles)


@pytest.mark.usefixtures("fresh_warning_flag")
def test_restoring_the_topic_draft_over_the_api_values_does_not_warn_d2b_b054(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    at = staff_app(page=SYLLABUS)
    topic_id = at.selectbox(key="sr-selected").value
    at.session_state["sr-edit"] = topic_id
    # Borrador que vuelve de Keycloak: valores propios del tema, distintos de los de la API.
    _restore_on_next_run(
        monkeypatch,
        {
            f"sr-name-{topic_id}": "Álgebra lineal avanzada",
            f"sr-sub-{topic_id}": "Matrices · Vectores propios",
            f"sr-bloom-{topic_id}": "Crear",
            f"sr-pre-{topic_id}": [],
        },
    )
    with caplog.at_level("WARNING", logger="streamlit"):
        at.run()
    assert_no_exception(at)
    assert _session_state_warnings(caplog) == []
    assert at.text_input(key=f"sr-name-{topic_id}").value == "Álgebra lineal avanzada"
    assert at.text_input(key=f"sr-sub-{topic_id}").value == "Matrices · Vectores propios"
    assert at.selectbox(key=f"sr-bloom-{topic_id}").value == "Crear"
    assert at.multiselect(key=f"sr-pre-{topic_id}").value == []


@pytest.mark.usefixtures("fresh_warning_flag")
def test_restoring_the_draft_of_a_new_topic_does_not_warn_d2b_b054(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    at = staff_app(page=SYLLABUS)
    at.session_state["sr-edit"] = -1
    _restore_on_next_run(
        monkeypatch, {"sr-name--1": "Tema nuevo", "sr-sub--1": "Uno · Dos", "sr-bloom--1": "Crear"}
    )
    with caplog.at_level("WARNING", logger="streamlit"):
        at.run()
    assert_no_exception(at)
    assert _session_state_warnings(caplog) == []
    assert at.text_input(key="sr-name--1").value == "Tema nuevo"
    assert at.text_input(key="sr-sub--1").value == "Uno · Dos"
    assert at.selectbox(key="sr-bloom--1").value == "Crear"


@pytest.mark.usefixtures("fresh_warning_flag")
def test_restoring_an_outcome_field_does_not_warn_d2b_b054(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Los resultados de aprendizaje llevan una clave aleatoria por panel; se restaura la de uno
    que sigue en `sr-outcomes-N`, como cuando el panel se vuelve a dibujar tras un `st.rerun`."""
    at = staff_app(page=SYLLABUS)
    at = click(at, "Editar tema")
    topic_id = at.selectbox(key="sr-selected").value
    outcome = next(t for t in at.text_input if t.key and t.key.startswith("sr-os-"))
    assert outcome.key
    _restore_on_next_run(monkeypatch, {outcome.key: "Resultado corregido"})
    with caplog.at_level("WARNING", logger="streamlit"):
        at.run()
    assert_no_exception(at)
    assert _session_state_warnings(caplog) == []
    assert at.text_input(key=outcome.key).value == "Resultado corregido"
    assert at.text_input(key=f"sr-name-{topic_id}").value


@pytest.mark.usefixtures("fresh_warning_flag")
def test_restoring_the_objective_draft_does_not_warn_e4b_b054(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    at = learner_app("learner_objective", DIAGNOSTIC_RESULT)
    session_of(at).learner.edit_objective = True
    _restore_on_next_run(
        monkeypatch,
        {
            "objective-verb": "Evaluar",
            "objective-content": "modelos de regresión",
            "objective-criterion": "con 90 % en la final",
        },
    )
    with caplog.at_level("WARNING", logger="streamlit"):
        at.run()
    no_exception(at)
    assert button(at, "Guardar objetivo")
    assert _session_state_warnings(caplog) == []
    assert at.selectbox(key="objective-verb").value == "Evaluar"
    assert at.text_input(key="objective-content").value == "modelos de regresión"
    assert at.text_input(key="objective-criterion").value == "con 90 % en la final"


def _open_quiz() -> AppTest:
    at = learner_app("learner_path", QUIZ, run=False)
    state = session_of(at).learner
    state.step_id, state.attempt_id = 813, 9002
    at.run()
    return at


@pytest.mark.usefixtures("fresh_warning_flag")
def test_restoring_a_choice_over_the_saved_answer_does_not_warn_quiz_b054(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Se vuelve a una pregunta de opción múltiple que ya tiene respuesta guardada en la hoja."""
    at = _open_quiz()
    # Una opción distinta de la primera: con `index=0` Streamlit no avisa.
    at.radio[0].set_value(at.radio[0].options[1]).run()
    button(at, "Siguiente").click().run()
    button(at, "Anterior").click().run()
    key, options = at.radio[0].key, at.radio[0].options
    assert key
    assert at.radio[0].value == options[1]
    _restore_on_next_run(monkeypatch, {key: options[2]})
    with caplog.at_level("WARNING", logger="streamlit"):
        at.run()
    no_exception(at)
    assert _session_state_warnings(caplog) == []
    assert at.radio(key=key).value == options[2]


@pytest.mark.usefixtures("fresh_warning_flag")
def test_restoring_a_short_answer_over_the_saved_text_does_not_warn_quiz_b054(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    at = _open_quiz()
    for _ in range(4):
        at.radio[0].set_value(at.radio[0].options[0]).run()
        button(at, "Siguiente").click().run()
    at.text_area[0].set_value("Respuesta guardada.").run()
    key = at.text_area[0].key
    assert key
    _restore_on_next_run(monkeypatch, {key: "Respuesta del borrador."})
    with caplog.at_level("WARNING", logger="streamlit"):
        at.run()
    no_exception(at)
    assert _session_state_warnings(caplog) == []
    assert at.text_area(key=key).value == "Respuesta del borrador."


@pytest.mark.usefixtures("fresh_warning_flag")
def test_restoring_the_survey_over_the_saved_answers_does_not_warn_e13_b054(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    at = learner_app("learner_completed", SURVEY)
    for index in range(8):
        at.radio[index].set_value(5).run()
    session_of(at).learner.survey_step = 2
    at.run()
    session_of(at).learner.survey_comment = "Más ejemplos."
    sus_key = at.radio[0].key
    assert sus_key
    _restore_on_next_run(monkeypatch, {sus_key: 2, "survey-comment": "Otro comentario."})
    with caplog.at_level("WARNING", logger="streamlit"):
        at.run()
    no_exception(at)
    assert _session_state_warnings(caplog) == []
    assert at.radio(key=sus_key).value == 2
    assert at.text_area(key="survey-comment").value == "Otro comentario."


@pytest.mark.usefixtures("fresh_warning_flag")
def test_restoring_the_informed_consent_decision_does_not_warn_a3b_b054(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    at = signed_in("learner_new")
    at.button(key="consent-terms-read").click().run()
    assert at.radio(key="consent-informed-decision").value.startswith("Quiero usar")
    _restore_on_next_run(
        monkeypatch,
        {"consent-informed-decision": PARTICIPATE_LABEL},
    )
    with caplog.at_level("WARNING", logger="streamlit"):
        at.run()
    no_exception(at)
    assert _session_state_warnings(caplog) == []
    assert at.radio(key="consent-informed-decision").value.startswith("Acepto")


@pytest.mark.usefixtures("fresh_warning_flag")
def test_restoring_the_goals_over_the_saved_ones_does_not_warn_e11_b054(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    at = learner_app("learner_path", PROGRESS)
    saved = at.segmented_control(key="goal-daily").value
    assert saved is not None
    other = next(o for o in (30, 45, 60) if o != saved)
    _restore_on_next_run(monkeypatch, {"goal-daily": other})
    with caplog.at_level("WARNING", logger="streamlit"):
        at.run()
    no_exception(at)
    assert _session_state_warnings(caplog) == []
    assert at.segmented_control(key="goal-daily").value == other
