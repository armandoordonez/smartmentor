"""``LlmRunner``: validation with retries, cache, budget, provider errors and the call log."""

from __future__ import annotations

import json
from decimal import Decimal

import pytest

from app.adapters.fake_llm import FakeLlmProvider
from app.adapters.memory import InMemoryCallLogRepository
from app.application.llm_runner import CallContext
from app.application.pricing import PriceTable
from app.container import Container
from app.domain.contracts.syllabus import SyllabusLLM
from app.domain.contracts.validation import check_syllabus
from app.domain.errors import TaskError
from app.ports.budget import BudgetScope
from app.ports.llm import (
    LlmContentBlockedError,
    LlmProviderError,
    LlmQuotaError,
    LlmTimeoutError,
)
from tests.conftest import example_llm, make_container, make_settings

CTX = CallContext(task="syllabus.structure", scope=BudgetScope(course_id=3))
VARS = {"syllabus": "Unidad 1"}


async def _run(container: Container) -> tuple[SyllabusLLM, object]:
    return await container.runner.run(
        "syllabus_structuring", VARS, SyllabusLLM, CTX, check=check_syllabus
    )


async def test_valid_answer_is_logged_with_cost(
    container: Container, call_logs: InMemoryCallLogRepository
) -> None:
    syllabus, meta = await _run(container)
    assert syllabus.course_key == "fundamentos_machine_learning"
    [row] = call_logs.rows
    assert (row.status, row.json_valid, row.call_attempt, row.from_cache) == (
        "success",
        True,
        1,
        False,
    )
    assert row.prompt_id == "syllabus_structuring"
    assert row.prompt_version == "v1"
    expected = TEST_COST = (
        Decimal(row.input_tokens) * Decimal("0.30") + Decimal(row.output_tokens) * Decimal("2.50")
    ) / Decimal(1_000_000)
    assert row.cost_usd == expected.quantize(Decimal("0.000001"))
    assert TEST_COST > 0
    assert row.input_sha256 == getattr(meta, "input_sha256", None)


async def test_invalid_json_is_retried_with_the_issues(
    container: Container, fake_llm: FakeLlmProvider, call_logs: InMemoryCallLogRepository
) -> None:
    fake_llm.script("syllabus_structuring", "{not json")
    await _run(container)
    assert [(r.status, r.json_valid, r.call_attempt) for r in call_logs.rows] == [
        ("invalid_output", False, 1),
        ("success", True, 2),
    ]
    second = fake_llm.calls("syllabus_structuring")[1]
    assert "Tu respuesta anterior no cumplió" in second.user


async def test_code_check_failure_counts_as_invalid_output(
    container: Container, fake_llm: FakeLlmProvider, call_logs: InMemoryCallLogRepository
) -> None:
    bad = example_llm("syllabus_structuring")
    bad["topics"][0]["prerequisites"] = ["does_not_exist"]
    fake_llm.script("syllabus_structuring", json.dumps(bad), json.dumps(bad), json.dumps(bad))
    with pytest.raises(TaskError) as error:
        await _run(container)
    assert error.value.code == "INVALID_OUTPUT"
    assert error.value.retryable
    assert [(r.status, r.json_valid) for r in call_logs.rows] == [("invalid_output", True)] * 3


async def test_cache_hit_skips_the_provider(
    container: Container, fake_llm: FakeLlmProvider, call_logs: InMemoryCallLogRepository
) -> None:
    await _run(container)
    _, meta = await _run(container)
    assert getattr(meta, "from_cache", False)
    assert len(fake_llm.requests) == 1
    assert call_logs.rows[-1].from_cache
    assert call_logs.rows[-1].cost_usd == 0


async def test_provider_errors_are_retried_then_fail(
    container: Container, fake_llm: FakeLlmProvider, call_logs: InMemoryCallLogRepository
) -> None:
    fake_llm.script(
        "syllabus_structuring",
        LlmProviderError("503"),
        LlmProviderError("503"),
        LlmTimeoutError("slow"),
    )
    with pytest.raises(TaskError) as error:
        await _run(container)
    assert error.value.code == "LLM_PROVIDER_TIMEOUT"
    assert [r.status for r in call_logs.rows] == ["error"] * 3
    assert [r.call_attempt for r in call_logs.rows] == [1, 2, 3]


async def test_transient_error_then_success(
    container: Container, fake_llm: FakeLlmProvider
) -> None:
    fake_llm.script("syllabus_structuring", LlmProviderError("503"))
    syllabus, _ = await _run(container)
    assert syllabus.topics


async def test_blocked_content_is_not_retried(
    container: Container, fake_llm: FakeLlmProvider
) -> None:
    fake_llm.script("syllabus_structuring", LlmContentBlockedError("SAFETY"))
    with pytest.raises(TaskError) as error:
        await _run(container)
    assert error.value.code == "LLM_CONTENT_BLOCKED"
    assert not error.value.retryable
    assert len(fake_llm.requests) == 1


async def test_budget_exhausted_blocks_the_call() -> None:
    container = make_container(make_settings(ai_course_budget_usd=Decimal("0.000001")))
    assert isinstance(container.llm, FakeLlmProvider)
    await _run(container)  # first call spends more than the cap
    with pytest.raises(TaskError) as error:
        await container.runner.run(
            "syllabus_structuring", {"syllabus": "otro"}, SyllabusLLM, CTX, check=check_syllabus
        )
    assert error.value.code == "BUDGET_EXCEEDED"
    assert not error.value.retryable
    logs = container.call_logs
    assert isinstance(logs, InMemoryCallLogRepository)
    assert logs.rows[-1].status == "budget_exceeded"
    assert len(container.llm.requests) == 1


async def test_real_provider_without_price_fails_before_calling() -> None:
    settings = make_settings(ai_llm_provider="gemini", gemini_api_key="test-only-not-a-secret")
    fake = FakeLlmProvider(settings.ai_prompts_dir / "examples" / "llm")
    container = make_container(settings, llm=fake, prices=PriceTable({}))
    with pytest.raises(TaskError) as error:
        await _run(container)
    assert error.value.code == "PRICE_NOT_CONFIGURED"
    assert fake.requests == []


async def test_quota_exhausted_is_not_retried(
    container: Container, fake_llm: FakeLlmProvider, call_logs: InMemoryCallLogRepository
) -> None:
    fake_llm.script("syllabus_structuring", LlmQuotaError("monthly spending cap"))
    with pytest.raises(TaskError) as error:
        await _run(container)
    assert error.value.code == "LLM_QUOTA_EXHAUSTED"
    assert [r.status for r in call_logs.rows] == ["error"]  # un solo intento: reintentar no sirve
    assert "spending cap" in (call_logs.rows[0].error_message or "")
