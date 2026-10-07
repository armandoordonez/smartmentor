import httpx
import pytest

from tests.integration.conftest import MakeFn

pytestmark = pytest.mark.integration

LOGS = "/api/v1/llm-call-logs"


async def test_log_and_filter_llm_calls(
    client: httpx.AsyncClient, make: MakeFn, world: dict[str, int]
) -> None:
    await make(
        "llm-call-logs",
        {
            "task": "generate_quiz",
            "model": "modelo-a",
            "enrollment_id": world["enrollment"],
            "prompt_version": "quiz-v1",
            "input_tokens": 1200,
            "output_tokens": 800,
            "cost_usd": 0.0123,
            "latency_ms": 4200,
        },
    )
    await make(
        "llm-call-logs", {"task": "extract_syllabus", "model": "modelo-a", "status": "error"}
    )

    assert (await client.get(LOGS)).json()["total"] == 2
    quizzes = await client.get(LOGS, params={"task": "generate_quiz"})
    assert quizzes.json()["total"] == 1
    assert quizzes.json()["items"][0]["cost_usd"] == pytest.approx(0.0123)
    errors = await client.get(LOGS, params={"status": "error"})
    assert errors.json()["total"] == 1


async def test_only_status_and_error_message_can_be_corrected(
    client: httpx.AsyncClient, make: MakeFn
) -> None:
    log = await make("llm-call-logs", {"task": "grade", "model": "modelo-a"})
    ok = await client.patch(
        f"{LOGS}/{log['id']}", json={"status": "error", "error_message": "timeout"}
    )
    assert ok.json()["status"] == "error"
    forbidden = await client.patch(f"{LOGS}/{log['id']}", json={"model": "otro"})
    assert forbidden.status_code == 422


async def test_log_needs_an_existing_enrollment(client: httpx.AsyncClient) -> None:
    response = await client.post(LOGS, json={"task": "grade", "model": "m", "enrollment_id": 999})
    assert response.status_code == 422
    assert response.json()["code"] == "ENROLLMENT_NOT_FOUND"
