"""Cliente HTTP: token en cada llamada, errores RFC 9457, Idempotency-Key y sondeo de trabajos."""

import json
from collections.abc import Iterator

import httpx
import pytest
import respx
from support import FIXTURES_DIR

from clients.api import ApiClient
from clients.base import ApiError
from clients.jobs import is_done, next_poll_delay, wait_for_job
from clients.models import Job

BASE = "http://api.test"


def fixture(name: str) -> object:
    return json.loads((FIXTURES_DIR / f"{name}.json").read_text(encoding="utf-8"))


class Tokens:
    """Entrega un token distinto en cada llamada: el cliente no debe guardarlo."""

    def __init__(self) -> None:
        self.calls = 0

    def __call__(self) -> str:
        self.calls += 1
        return f"test-only-not-a-secret-{self.calls}"


@pytest.fixture
def tokens() -> Tokens:
    return Tokens()


@pytest.fixture
def client(tokens: Tokens) -> Iterator[ApiClient]:
    with httpx.Client(base_url=BASE) as http:
        yield ApiClient(BASE, tokens, http=http)


@respx.mock
def test_every_call_sends_a_fresh_bearer_token_and_request_id(client: ApiClient) -> None:
    route = respx.get(f"{BASE}/api/v1/me").mock(
        return_value=httpx.Response(200, json=fixture("me_learner"))
    )
    client.get_me()
    client.get_me()
    first, second = (call.request for call in route.calls)
    assert first.headers["Authorization"] == "Bearer test-only-not-a-secret-1"
    assert second.headers["Authorization"] == "Bearer test-only-not-a-secret-2"
    assert first.headers["X-Request-ID"] != second.headers["X-Request-ID"]
    assert "Idempotency-Key" not in first.headers


@respx.mock
def test_get_me_parses_roles_and_labels(client: ApiClient) -> None:
    respx.get(f"{BASE}/api/v1/me").mock(
        return_value=httpx.Response(200, json=fixture("me_instructor"))
    )
    me = client.get_me()
    assert me.roles == ["instructor", "learner"]
    assert me.default_role == "instructor"
    assert me.role_short_labels["admin"] == "Admin"


@respx.mock
def test_problem_json_becomes_api_error_with_code_and_extensions(client: ApiClient) -> None:
    body = {
        "type": "https://smartmentor/errors/max-attempts-exceeded",
        "title": "Max attempts exceeded",
        "status": 422,
        "detail": "No attempts left.",
        "code": "MAX_ATTEMPTS_EXCEEDED",
        "request_id": "req-1",
        "attempts_used": 3,
        "max_attempts": 3,
        "retryable": False,
    }
    respx.post(f"{BASE}/api/v1/me/enrollments/7/steps/812/attempts").mock(
        return_value=httpx.Response(
            422, json=body, headers={"Content-Type": "application/problem+json"}
        )
    )
    with pytest.raises(ApiError) as caught:
        client.create_attempt(7, 812, "topic", idempotency_key="key-1")
    error = caught.value
    assert (error.status, error.code, error.request_id) == (422, "MAX_ATTEMPTS_EXCEEDED", "req-1")
    assert error.extra == {"attempts_used": 3, "max_attempts": 3}


@respx.mock
def test_plain_error_without_body_gets_http_code(client: ApiClient) -> None:
    respx.get(f"{BASE}/api/v1/me").mock(return_value=httpx.Response(502, text="bad gateway"))
    with pytest.raises(ApiError) as caught:
        client.get_me()
    assert (caught.value.status, caught.value.code) == (502, "HTTP_502")


@respx.mock
def test_connection_failure_becomes_service_unavailable(client: ApiClient) -> None:
    respx.get(f"{BASE}/api/v1/me").mock(side_effect=httpx.ConnectError("down"))
    with pytest.raises(ApiError) as caught:
        client.get_me()
    assert (caught.value.status, caught.value.code) == (503, "SERVICE_UNAVAILABLE")


@respx.mock
def test_invalid_response_body_is_a_502(client: ApiClient) -> None:
    respx.get(f"{BASE}/api/v1/me").mock(return_value=httpx.Response(200, json={"id": "x"}))
    with pytest.raises(ApiError) as caught:
        client.get_me()
    assert caught.value.code == "INVALID_RESPONSE"


@respx.mock
def test_idempotent_operations_send_the_key(client: ApiClient) -> None:
    submit = respx.post(f"{BASE}/api/v1/me/enrollments/7/diagnostic/submit").mock(
        return_value=httpx.Response(202, json=fixture("job_accepted"))
    )
    job = client.submit_diagnostic(7, idempotency_key="3f6c2a52-0000-4000-8000-000000000001")
    assert job.status == "queued"
    assert submit.calls.last.request.headers["Idempotency-Key"].endswith("0001")

    final = respx.post(f"{BASE}/api/v1/me/enrollments/7/final-attempts").mock(
        return_value=httpx.Response(201, json=fixture("attempt"))
    )
    client.create_final_attempt(7, idempotency_key="key-final")
    assert final.calls.last.request.headers["Idempotency-Key"] == "key-final"


@respx.mock
def test_create_attempt_returns_attempt_or_job(client: ApiClient) -> None:
    url = f"{BASE}/api/v1/me/enrollments/7/steps/812/attempts"
    respx.post(url).mock(
        side_effect=[
            httpx.Response(201, json=fixture("attempt")),
            httpx.Response(202, json=fixture("job_accepted")),
        ]
    )
    assert client.create_attempt(7, 812, "topic", idempotency_key="k1").__class__.__name__ == (
        "Attempt"
    )
    assert client.create_attempt(7, 812, "topic", idempotency_key="k2").__class__.__name__ == (
        "JobAccepted"
    )


@respx.mock
def test_paginated_catalog_and_profile_put(client: ApiClient) -> None:
    respx.get(f"{BASE}/api/v1/learning-paths").mock(
        return_value=httpx.Response(200, json=fixture("learning_paths"))
    )
    page = client.list_learning_paths(limit=100)
    assert page.total == 6
    assert page.items[0].name == "Fundamentos de Machine Learning"

    put = respx.put(f"{BASE}/api/v1/me/profile").mock(
        return_value=httpx.Response(200, json=fixture("profile"))
    )
    from clients.models import ProfileUpdate

    client.update_profile(ProfileUpdate(description="Hola"))
    sent = json.loads(put.calls.last.request.content)
    assert sent["description"] == "Hola"
    assert sent["tools"] == []


# --- Sondeo de trabajos ---------------------------------------------------------------------------


def test_poll_delay_grows_and_is_capped() -> None:
    delays = [next_poll_delay(attempt) for attempt in range(8)]
    assert delays == [1.0, 2.0, 3.0, 4.0, 5.0, 5.0, 5.0, 5.0]


class ScriptedJobs:
    def __init__(self, statuses: list[Job]) -> None:
        self.statuses = statuses
        self.polls = 0

    def get_job(self, job_id: str) -> Job:
        del job_id
        job = self.statuses[min(self.polls, len(self.statuses) - 1)]
        self.polls += 1
        return job


def _job(**changes: object) -> Job:
    return Job.model_validate({**fixture("job_running"), **changes})  # type: ignore[dict-item]


def test_wait_for_job_polls_until_ingested() -> None:
    source = ScriptedJobs([_job(), _job(), Job.model_validate(fixture("job_succeeded"))])
    slept: list[float] = []
    job = wait_for_job(source, "job-1", sleep=slept.append)  # type: ignore[arg-type]
    assert job.status == "succeeded"
    assert slept == [1.0, 2.0]


def test_wait_for_job_stops_on_failure() -> None:
    failed = _job(status="failed", error={"code": "AI_TASK_FAILED", "retryable": True})
    assert is_done(failed)
    assert wait_for_job(ScriptedJobs([failed]), "job-1", sleep=lambda _: None).error is not None  # type: ignore[arg-type]


def test_succeeded_but_not_ingested_keeps_waiting() -> None:
    assert not is_done(_job(status="succeeded", ingested=False))


def test_wait_for_job_times_out() -> None:
    with pytest.raises(ApiError) as caught:
        wait_for_job(ScriptedJobs([_job()]), "job-1", timeout=5, sleep=lambda _: None)  # type: ignore[arg-type]
    assert caught.value.code == "JOB_TIMEOUT"
    assert caught.value.retryable
