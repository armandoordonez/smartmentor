"""Eventos de uso del aprendiz para el tiempo en tarea (m27, R-003).

Cada pantalla manda su evento de vista una sola vez por visita (aunque Streamlit la vuelva a
ejecutar), cierra la visita con `payload.seconds` y un fallo al enviar no rompe la página.
"""

from typing import Any

import pytest
from apptest import button, session_of
from learner_support import (
    FINAL,
    PATH,
    QUIZ,
    TOPIC,
    client_of,
    fail,
    learner_app,
    no_exception,
)
from streamlit.testing.v1 import AppTest

from clients.base import ApiError
from clients.models_learner import InteractionEvent
from clients.ops_learner import LearnerScript

GRADE_SCRIPT = LearnerScript({"submit_attempt": "learner/job_accepted_grading"})


def _events(at: AppTest, event_type: str | None = None) -> list[InteractionEvent]:
    events = client_of(at).recorded_events
    return [e for e in events if event_type is None or e.event_type == event_type]


def _payload(event: InteractionEvent) -> dict[str, Any]:
    assert event.payload is not None
    return event.payload


def _open_topic(script: LearnerScript | None = None) -> AppTest:
    at = learner_app("learner_path", TOPIC, script=script, run=False)
    session_of(at).learner.step_id = 813
    at.run()
    return at


def _open_quiz(script: LearnerScript | None = None) -> AppTest:
    at = learner_app("learner_path", QUIZ, script=script, run=False)
    state = session_of(at).learner
    state.step_id, state.attempt_id = 813, 9002
    at.run()
    return at


def _answer_quiz(at: AppTest) -> None:
    for _ in range(5):
        if at.radio:
            at.radio[0].set_value(at.radio[0].options[0]).run()
            label = "Siguiente"
        else:
            at.text_area[0].set_value("Porque no detectar un fraude cuesta más.").run()
            label = "Enviar quiz"
        button(at, label).click().run()


def _answer_final(at: AppTest) -> None:
    for index in range(8):
        at.radio[0].set_value(at.radio[0].options[0]).run()
        button(at, "Siguiente" if index < 7 else "Enviar evaluación").click().run()


def _assert_seconds(event: InteractionEvent) -> None:
    payload = _payload(event)
    assert isinstance(payload["seconds"], int)
    assert 0 <= payload["seconds"] <= 3600
    assert "started_at" in payload


# --- E5 · Ruta -----------------------------------------------------------------------------------


def test_e5_sends_path_view_once_per_visit() -> None:
    at = learner_app("learner_path", PATH)
    at.run()
    at.run()  # reejecuciones de la misma visita
    no_exception(at)
    views = _events(at, "path.view")
    assert len(views) == 1
    enrollment_id = session_of(at).selected_enrollment_id
    assert views[0].enrollment_id == enrollment_id
    assert views[0].topic_id is None
    assert _payload(views[0])["screen"] == "E5"
    assert views[0].occurred_at.tzinfo is not None


def test_e5b_fixed_path_names_its_screen() -> None:
    at = learner_app("learner_fixed_path", PATH)
    no_exception(at)
    assert _payload(_events(at, "path.view")[0])["screen"] == "E5b"


def test_e5_new_visit_sends_a_new_view_and_closes_the_previous_one() -> None:
    at = learner_app("learner_path", PATH)
    at.switch_page(TOPIC).run()
    at.switch_page(PATH).run()
    no_exception(at)
    assert len(_events(at, "path.view")) == 2
    closes = _events(at, "path.close")
    assert len(closes) == 1
    _assert_seconds(closes[0])


# --- E6 · Tema -----------------------------------------------------------------------------------


def test_e6_sends_topic_open_and_resources_once_per_visit() -> None:
    at = _open_topic()
    at.run()
    at.run()
    no_exception(at)
    opens = _events(at, "topic.open")
    assert len(opens) == 1
    assert opens[0].topic_id is not None
    assert _payload(opens[0])["step_id"] == 813
    assert _payload(opens[0])["screen"] == "E6"
    resources = {_payload(e)["resource"]: e for e in _events(at, "resource.view")}
    assert set(resources) == {"explanation", "video"}
    assert all(e.topic_id == opens[0].topic_id for e in resources.values())
    assert "resource_id" in _payload(resources["explanation"])
    assert "video_candidate_id" in _payload(resources["video"])
    assert _events(at, "topic.close") == []


def test_e6_leaving_the_topic_sends_topic_close_with_seconds() -> None:
    at = _open_topic()
    at.switch_page(PATH).run()
    at.run()
    no_exception(at)
    closes = _events(at, "topic.close")
    assert len(closes) == 1
    assert closes[0].topic_id == _events(at, "topic.open")[0].topic_id
    _assert_seconds(closes[0])


# --- E6b, E6c · Quiz -----------------------------------------------------------------------------


def test_e6_start_quiz_closes_the_topic_and_starts_the_quiz_once() -> None:
    at = _open_topic()
    button(at, "Empezar quiz").click().run()
    at.run()
    no_exception(at)
    assert len(_events(at, "topic.close")) == 1
    starts = _events(at, "quiz.start")
    assert len(starts) == 1
    payload = _payload(starts[0])
    assert payload["attempt_id"] == 9002
    assert payload["step_id"] == 813
    assert payload["screen"] == "E6b"
    assert starts[0].topic_id == _events(at, "topic.open")[0].topic_id


def test_e6b_answering_does_not_repeat_the_start() -> None:
    at = _open_quiz()
    at.radio[0].set_value(at.radio[0].options[0]).run()
    button(at, "Siguiente").click().run()
    no_exception(at)
    assert len(_events(at, "quiz.start")) == 1
    assert _events(at, "quiz.submit") == []


def test_e6c_submit_sends_quiz_submit_once_with_seconds() -> None:
    at = _open_quiz()
    _answer_quiz(at)
    at.run()
    no_exception(at)
    submits = _events(at, "quiz.submit")
    assert len(submits) == 1
    _assert_seconds(submits[0])
    assert _payload(submits[0])["attempt_id"] == 9002
    assert _payload(submits[0])["grading"] == "done"
    assert submits[0].topic_id == _events(at, "quiz.start")[0].topic_id
    # La entrega cerró la visita: salir después no manda una pausa.
    assert _events(at, "quiz.pause") == []


def test_e6c_submit_with_short_answer_grading_job() -> None:
    at = _open_quiz(script=GRADE_SCRIPT)
    _answer_quiz(at)
    at.run()  # U1c termina
    no_exception(at)
    submits = _events(at, "quiz.submit")
    assert len(submits) == 1
    assert _payload(submits[0])["grading"] == "job"


def test_e6b_leaving_without_submitting_sends_a_pause_and_a_return_keeps_one_start() -> None:
    at = _open_quiz()
    at.switch_page(PATH).run()
    at.switch_page(QUIZ).run()
    no_exception(at)
    pauses = _events(at, "quiz.pause")
    assert len(pauses) == 1
    _assert_seconds(pauses[0])
    assert len(_events(at, "quiz.start")) == 1


# --- E8 · Evaluación final -----------------------------------------------------------------------


def test_e8_sends_final_start_once_and_final_submit_with_seconds() -> None:
    at = learner_app("learner_final_ready", FINAL)
    at.run()
    starts = _events(at, "final.start")
    assert len(starts) == 1
    assert starts[0].topic_id is None
    assert _payload(starts[0])["attempt_id"] == 9100
    assert _payload(starts[0])["screen"] == "E8"
    _answer_final(at)
    no_exception(at)
    assert len(_events(at, "final.start")) == 1
    submits = _events(at, "final.submit")
    assert len(submits) == 1
    _assert_seconds(submits[0])
    assert _payload(submits[0])["attempt_id"] == 9100


# --- Fallos al enviar ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "error",
    [
        ApiError(503, "SERVICE_UNAVAILABLE", "API unreachable"),
        ApiError(422, "VALIDATION_ERROR", "bad event"),
        RuntimeError("boom"),
    ],
    ids=["503", "422", "unexpected"],
)
@pytest.mark.parametrize("page", [PATH, TOPIC, QUIZ])
def test_an_events_error_never_breaks_the_page(page: str, error: Exception) -> None:
    at = learner_app("learner_path", page, run=False)
    state = session_of(at).learner
    state.step_id, state.attempt_id = 813, 9002
    calls: list[int] = []

    def boom(events: list[InteractionEvent]) -> int:
        calls.append(len(events))
        raise error

    client_of(at).record_events = boom  # type: ignore[method-assign]
    at.run()
    no_exception(at)
    assert calls, "la página debía intentar enviar eventos"
    assert not at.error
    assert not [w for w in at.warning if "evento" in str(w.value).lower()]


def test_e8_events_error_does_not_block_the_submission() -> None:
    at = learner_app("learner_final_ready", FINAL, run=False)
    fail(at, "record_events", ApiError(503, "SERVICE_UNAVAILABLE", "API unreachable"))
    at.run()
    _answer_final(at)
    no_exception(at)
    assert session_of(at).learner.final_attempt_id == 9100


def test_unsent_events_go_out_with_the_next_batch() -> None:
    at = learner_app("learner_path", PATH, run=False)
    client = client_of(at)
    original = client.record_events

    def offline(events: list[InteractionEvent]) -> int:
        del events
        raise ApiError(503, "SERVICE_UNAVAILABLE", "API unreachable")

    client.record_events = offline  # type: ignore[method-assign]
    at.run()
    assert len(session_of(at).learner.usage.pending) == 1
    client.record_events = original  # type: ignore[method-assign]
    at.switch_page(TOPIC).run()
    no_exception(at)
    assert session_of(at).learner.usage.pending == []
    sent = [e.event_type for e in client.recorded_events]
    assert sent[0] == "path.view"
    assert sent.count("path.view") == 1
    assert "path.close" in sent


def test_a_rejected_batch_is_not_retried() -> None:
    at = learner_app("learner_path", PATH, run=False)
    fail(at, "record_events", ApiError(422, "VALIDATION_ERROR", "bad event"))
    at.run()
    no_exception(at)
    assert session_of(at).learner.usage.pending == []
