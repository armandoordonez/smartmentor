"""`POST /me/events` en los dos clientes y la forma de los eventos (m27, R-003)."""

import json
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import httpx
import pytest
import respx
from jsonschema import Draft202012Validator
from pydantic import ValidationError
from support import REPO_ROOT

from clients.api import ApiClient
from clients.base import ApiError
from clients.fixtures import FixturesClient
from clients.models_learner import InteractionEvent
from clients.ops_learner import EVENTS_TIMEOUT, LearnerScript
from core.learner_state import OpenView
from core.usage_events import MAX_SEGMENT_SECONDS, _closing

BASE = "http://api.test"
OPENAPI = json.loads((REPO_ROOT / "docs" / "contracts" / "openapi-api.json").read_text("utf-8"))
AT = datetime(2026, 11, 14, 15, 30, tzinfo=UTC)


def _event(event_type: str = "topic.open", **payload: object) -> InteractionEvent:
    return InteractionEvent(
        enrollment_id=7,
        event_type=event_type,
        topic_id=12,
        occurred_at=AT,
        payload=dict(payload) or None,
    )


@pytest.fixture
def client() -> Iterator[ApiClient]:
    with httpx.Client(base_url=BASE) as http:
        yield ApiClient(BASE, lambda: "test-only-not-a-secret", http=http)


@respx.mock
def test_api_client_posts_the_batch_with_a_short_timeout(client: ApiClient) -> None:
    route = respx.post(f"{BASE}/api/v1/me/events").mock(
        return_value=httpx.Response(202, json={"accepted": 2})
    )
    events = [_event(step_id=813), _event("topic.close", seconds=42)]
    assert client.record_events(events) == 2
    request = route.calls.last.request
    body = json.loads(request.content)
    assert body["events"][0] == {
        "enrollment_id": 7,
        "event_type": "topic.open",
        "occurred_at": "2026-11-14T15:30:00Z",
        "topic_id": 12,
        "payload": {"step_id": 813},
    }
    assert body["events"][1]["payload"] == {"seconds": 42}
    assert "Idempotency-Key" not in request.headers
    assert request.extensions["timeout"] == EVENTS_TIMEOUT.as_dict()


@respx.mock
def test_api_client_raises_api_error_on_422(client: ApiClient) -> None:
    respx.post(f"{BASE}/api/v1/me/events").mock(
        return_value=httpx.Response(422, json={"code": "VALIDATION_ERROR", "detail": "bad"})
    )
    with pytest.raises(ApiError) as raised:
        client.record_events([_event()])
    assert raised.value.status == 422


@respx.mock
def test_api_client_timeout_is_service_unavailable(client: ApiClient) -> None:
    respx.post(f"{BASE}/api/v1/me/events").mock(side_effect=httpx.ReadTimeout("slow"))
    with pytest.raises(ApiError) as raised:
        client.record_events([_event()])
    assert raised.value.status == 503


def test_the_batch_has_the_shape_of_events_body() -> None:
    schema = {"$ref": "#/components/schemas/EventsBody", "components": OPENAPI["components"]}
    body = {
        "events": [
            _event().model_dump(mode="json"),
            InteractionEvent(enrollment_id=7, event_type="final.start", occurred_at=AT).model_dump(
                mode="json"
            ),
        ]
    }
    errors = [e.message for e in Draft202012Validator(schema).iter_errors(body)]
    assert errors == []


@pytest.mark.parametrize("event_type", ["", "Topic.open", "1topic", "topic-open", "x" * 61])
def test_event_type_follows_the_contract_pattern(event_type: str) -> None:
    with pytest.raises(ValidationError):
        _event(event_type)


def test_fixtures_client_keeps_the_events_in_memory() -> None:
    client = FixturesClient("learner_path")
    assert client.record_events([_event(), _event("topic.close", seconds=3)]) == 2
    assert [e.event_type for e in client.recorded_events] == ["topic.open", "topic.close"]


def test_fixtures_client_validates_the_batch_size_and_goes_offline() -> None:
    client = FixturesClient("learner_path")
    with pytest.raises(ApiError) as raised:
        client.record_events([])
    assert raised.value.status == 422
    with pytest.raises(ApiError):
        client.record_events([_event()] * 101)
    offline = FixturesClient("learner_path", script=LearnerScript(offline=True))
    with pytest.raises(ApiError) as raised:
        offline.record_events([_event()])
    assert raised.value.status == 503
    assert offline.recorded_events == []


def _view(started_at: datetime) -> OpenView:
    return OpenView(
        page="topic",
        close_type="topic.close",
        enrollment_id=7,
        topic_id=12,
        payload={"screen": "E6", "step_id": 813},
        started_at=started_at,
    )


def test_closing_event_carries_the_seconds_of_the_visit() -> None:
    event = _closing(_view(datetime.now(UTC) - timedelta(seconds=90)), "topic.close", None)
    assert event.event_type == "topic.close"
    assert event.topic_id == 12
    assert event.payload is not None
    assert 89 <= event.payload["seconds"] <= 92
    assert event.payload["step_id"] == 813
    assert "capped" not in event.payload


def test_a_long_visit_is_capped() -> None:
    event = _closing(_view(datetime.now(UTC) - timedelta(hours=5)), "quiz.pause", {"x": 1})
    assert event.payload is not None
    assert event.payload["seconds"] == MAX_SEGMENT_SECONDS
    assert event.payload["capped"] is True
    assert event.payload["x"] == 1
