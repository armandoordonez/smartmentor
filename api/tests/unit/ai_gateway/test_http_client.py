"""`HttpAiService` contra un servidor simulado (`httpx.MockTransport`)."""

import json
from collections.abc import Callable

import httpx
import pytest

from app.core.logging import request_id_var
from app.domains.ai_gateway.entities import JobRefs
from app.domains.ai_gateway.exceptions import (
    AiBudgetExceededError,
    AiJobNotFoundError,
    AiServiceUnavailableError,
)
from app.domains.ai_gateway.http_client import ClientCredentialsTokenProvider, HttpAiService

JOB_ID = "0b8e3c1e-6a4f-4f51-9a39-7d2a1f0c9e11"
Handler = Callable[[httpx.Request], httpx.Response]


class StaticToken:
    async def token(self) -> str:
        return "test-only-service-token"


def service(handler: Handler, *, tokens: bool = True) -> HttpAiService:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://ai.test")
    return HttpAiService(client, StaticToken() if tokens else None)


async def test_submit_job_sends_the_contract_body_token_and_request_id() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["authorization"]
        seen["request_id"] = request.headers.get("x-request-id")
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            202, json={"job_id": JOB_ID, "job_type": "syllabus.structure", "status": "queued"}
        )

    token = request_id_var.set("req-123")
    try:
        ref = await service(handler).submit_job(
            "syllabus.structure",
            {"syllabus_document_id": 7},
            "syllabus.structure:syllabus_document:7:v1",
            JobRefs(course_id=3),
        )
    finally:
        request_id_var.reset(token)
    assert ref.job_id == JOB_ID
    assert ref.status == "queued"
    assert seen["url"] == "http://ai.test/v1/jobs"
    assert seen["auth"] == "Bearer test-only-service-token"
    assert seen["request_id"] == "req-123"
    assert seen["body"] == {
        "job_type": "syllabus.structure",
        "idempotency_key": "syllabus.structure:syllabus_document:7:v1",
        "input": {"syllabus_document_id": 7},
        "refs": {"course_id": 3, "topic_id": None, "enrollment_id": None},
        "requested_by": "api",
    }


async def test_an_existing_job_answers_200_and_is_accepted() -> None:
    ai = service(
        lambda _r: httpx.Response(
            200, json={"job_id": JOB_ID, "job_type": "syllabus.structure", "status": "running"}
        )
    )
    assert (await ai.submit_job("syllabus.structure", {}, "k")).status == "running"


async def test_get_job_parses_the_result_error_and_refs() -> None:
    body = {
        "job_id": JOB_ID,
        "job_type": "syllabus.structure",
        "status": "failed",
        "contract": None,
        "result": None,
        "error": {"code": "INVALID_OUTPUT", "message": "x", "retryable": True},
        "attempts": 2,
        "cost_usd": 0.0042,
        "refs": {"course_id": 3, "topic_id": None, "enrollment_id": None},
        "created_at": "2026-11-07T15:00:00Z",
        "started_at": "2026-11-07T15:00:01Z",
        "finished_at": "2026-11-07T15:00:09Z",
    }
    job = await service(lambda _r: httpx.Response(200, json=body)).get_job(JOB_ID)
    assert job.status == "failed"
    assert job.error is not None
    assert (job.error.code, job.error.retryable) == ("INVALID_OUTPUT", True)
    assert job.refs.course_id == 3
    assert job.attempts == 2
    assert job.finished_at is not None
    assert job.is_finished


async def test_a_404_is_job_not_found() -> None:
    ai = service(lambda _r: httpx.Response(404, json={"code": "JOB_NOT_FOUND"}))
    with pytest.raises(AiJobNotFoundError):
        await ai.get_job(JOB_ID)


@pytest.mark.parametrize("status", [500, 502, 503])
async def test_a_5xx_is_service_unavailable_and_retryable(status: int) -> None:
    ai = service(lambda _r: httpx.Response(status, json={"code": "INTERNAL_ERROR"}))
    with pytest.raises(AiServiceUnavailableError) as error:
        await ai.get_job(JOB_ID)
    assert error.value.extra == {"retryable": True}
    assert error.value.status_code == 503


async def test_a_network_failure_is_service_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sin red", request=request)

    with pytest.raises(AiServiceUnavailableError):
        await service(handler).get_job(JOB_ID)


async def test_a_synchronous_task_over_budget_is_a_503_budget_error() -> None:
    ai = service(lambda _r: httpx.Response(503, json={"code": "BUDGET_EXCEEDED"}))
    with pytest.raises(AiBudgetExceededError):
        await ai.run_task("levels.estimate", {})


async def test_a_rejected_job_input_is_reported_with_the_ai_error_code() -> None:
    ai = service(lambda _r: httpx.Response(422, json={"code": "INVALID_JOB_INPUT"}))
    with pytest.raises(AiServiceUnavailableError, match="INVALID_JOB_INPUT"):
        await ai.submit_job("syllabus.structure", {}, "k")


async def test_list_jobs_filters_and_caps_the_limit() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(dict(request.url.params))
        return httpx.Response(
            200,
            json={
                "items": [{"job_id": JOB_ID, "job_type": "course.generate_content", "status": "running"}],
                "total": 1,
                "limit": 100,
                "offset": 0,
            },
        )

    jobs = await service(handler).list_jobs(job_type="course.generate_content", course_id=3, limit=500)
    assert [j.job_id for j in jobs] == [JOB_ID]
    assert seen == {"job_type": "course.generate_content", "course_id": "3", "limit": "100"}


async def test_run_task_returns_the_body() -> None:
    ai = service(lambda _r: httpx.Response(200, json={"steps": []}))
    assert await ai.run_task("path.sequence", {"topics": []}) == {"steps": []}


async def test_without_a_token_provider_no_authorization_header_is_sent() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "authorization" not in request.headers
        return httpx.Response(200, json={"items": []})

    assert await service(handler, tokens=False).list_jobs() == []


# --- token de servicio ------------------------------------------------------------------------


async def test_the_service_token_is_requested_with_client_credentials_and_cached() -> None:
    calls: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(dict(httpx.QueryParams(request.content.decode())))
        return httpx.Response(200, json={"access_token": "abc", "expires_in": 300})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = ClientCredentialsTokenProvider(
        token_url="http://keycloak.test/token",
        client_id="smartmentor-api-service",
        client_secret="test-only-not-a-secret",
        client=client,
    )
    assert await provider.token() == "abc"
    assert await provider.token() == "abc"
    assert len(calls) == 1
    assert calls[0]["grant_type"] == "client_credentials"
    assert calls[0]["client_id"] == "smartmentor-api-service"


async def test_a_failing_token_endpoint_is_service_unavailable() -> None:
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda _r: httpx.Response(401)))
    provider = ClientCredentialsTokenProvider(
        token_url="http://keycloak.test/token", client_id="c", client_secret="s", client=client
    )
    with pytest.raises(AiServiceUnavailableError):
        await provider.token()
