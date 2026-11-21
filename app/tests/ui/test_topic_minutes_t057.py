"""T-057: D2b deja escribir los minutos estimados del tema (la IA casi nunca los encuentra)."""

import pytest
from staff_support import assert_no_exception, click, staff_app
from streamlit.testing.v1 import AppTest

from clients.fixtures import FixturesClient
from clients.models_staff import CourseTopic, TopicWrite

SYLLABUS = "pages/instructor/syllabus_review.py"


def _edit_topic(topic_id: int) -> AppTest:
    at = staff_app(page=SYLLABUS)
    at.selectbox(key="sr-selected").set_value(topic_id).run()
    return click(at, "Editar tema")


def _record_updates(monkeypatch: pytest.MonkeyPatch) -> list[TopicWrite]:
    sent: list[TopicWrite] = []

    def update_topic(self: FixturesClient, topic_id: int, body: TopicWrite) -> CourseTopic:
        del topic_id
        sent.append(body)
        return self.create_topic(1, body)

    monkeypatch.setattr(FixturesClient, "update_topic", update_topic)
    return sent


def test_d2b_shows_the_minutes_the_api_already_has() -> None:
    at = _edit_topic(103)
    field = at.number_input(key="sr-min-103")
    assert field.label == "Minutos estimados (opcional)"
    assert field.value == 120


def test_d2b_saves_the_minutes_the_instructor_writes(monkeypatch: pytest.MonkeyPatch) -> None:
    sent = _record_updates(monkeypatch)
    at = _edit_topic(103)
    at.number_input(key="sr-min-103").set_value(45).run()
    at = click(at, "Guardar cambios")
    assert_no_exception(at)
    assert [body.estimated_minutes for body in sent] == [45]


def test_d2b_keeps_the_minutes_empty_when_nobody_estimated_them(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Un tema sin minutos (lo normal tras la extracción) se guarda sin minutos, no con 1."""
    sent = _record_updates(monkeypatch)
    at = _edit_topic(103)
    at.number_input(key="sr-min-103").set_value(None).run()
    assert at.number_input(key="sr-min-103").value is None
    at = click(at, "Guardar cambios")
    assert_no_exception(at)
    assert [body.estimated_minutes for body in sent] == [None]


def test_new_topic_starts_without_minutes() -> None:
    at = staff_app(page=SYLLABUS)
    at = click(at, "Agregar tema")
    assert_no_exception(at)
    assert at.number_input(key="sr-min--1").value is None
