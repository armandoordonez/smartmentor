"""Content tasks end to end with the fakes: indexing, explanations, faithfulness and examples."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.adapters.fake_embedding import FakeEmbeddingProvider
from app.adapters.fake_llm import FakeLlmProvider
from app.application.content.context import TaskContext, TaskResult
from app.domain.contracts.content import (
    FaithfulnessCheck,
    PersonalizedExample,
    TopicExplanation,
)
from app.domain.errors import InputReferenceNotFoundError, TaskError
from app.ports.jobs import JobRefs
from app.ports.llm import LlmProviderError
from eval.fake_answers import explanation
from eval.pipeline import DEFAULT_SYLLABUS, EvalWorld, PipelineOptions
from eval.runtime import EvalRuntime

REFS = JobRefs(course_id=1)
PROFILE = (
    "Me llamo Ana María Gómez, mi correo es ana.gomez@correo.com y mi teléfono es +57 300 123 4567. "
    "Soy analista de datos en logística y uso Excel y SQL."
)


async def test_index_course_stores_fragments_and_topic_vectors(
    world: EvalWorld, embedder: FakeEmbeddingProvider
) -> None:
    result = await world.call("embeddings.index_course", {"course_id": 1}, REFS)
    assert result.result["topics_indexed"] == 3
    assert result.result["chunks_indexed"] >= 3
    assert result.result["embedding_model"] == "fake-embedding"
    calls_before = len(embedder.calls)
    again = await world.call("embeddings.index_course", {"course_id": 1}, REFS)
    assert again.result == result.result
    assert len(embedder.calls) == calls_before  # nothing re-embedded


async def test_explain_topic_returns_a_cited_explanation_with_faithfulness(
    world: EvalWorld,
) -> None:
    result = await world.call("content.explain_topic", {"topic_id": "2"}, REFS)
    assert result.contract == "topic_explanation.v1"
    explanation_ = TopicExplanation.model_validate(result.result)
    assert explanation_.kind == "main" and explanation_.audience == "all_learners"
    assert explanation_.faithfulness == 1.0
    assert 1 <= len(explanation_.sources) <= 4
    assert all(s.license for s in explanation_.sources)
    assert [s.n for s in explanation_.sources] == list(range(1, len(explanation_.sources) + 1))
    assert explanation_.meta.prompt_id == "topic_explanation"


async def test_the_explanation_prompt_carries_the_topic_and_numbered_fragments_only(
    world: EvalWorld, llm: FakeLlmProvider
) -> None:
    await world.call("content.explain_topic", {"topic_id": "3"}, REFS)
    (request,) = llm.calls("topic_explanation")
    assert request.temperature == 0.4
    assert "[1] " in request.user
    assert "regresion_logistica" not in request.user or "Regresión logística" in request.user
    assert "ana.gomez" not in request.user  # L-01: the shared explanation has no learner data


async def test_the_shared_explanation_is_cached_by_topic(
    world: EvalWorld, llm: FakeLlmProvider
) -> None:
    first = await world.call("content.explain_topic", {"topic_id": "2"}, REFS)
    second = await world.call("content.explain_topic", {"topic_id": "2"}, REFS)
    assert first.result["meta"]["from_cache"] is False
    assert second.result["meta"]["from_cache"] is True
    assert len(llm.calls("topic_explanation")) == 1
    assert len(llm.calls("rag_faithfulness")) == 1


async def test_a_citation_out_of_range_is_sent_back_to_the_model(
    world: EvalWorld, llm: FakeLlmProvider
) -> None:
    good = explanation("main")
    llm.script("topic_explanation", lambda request: good(request).replace("[1]", "[9]"))
    result = await world.call("content.explain_topic", {"topic_id": "2"}, REFS)
    calls = llm.calls("topic_explanation")
    assert len(calls) == 2
    assert "citations out of range" in calls[1].user
    assert "[9]" not in json.dumps(result.result)
    statuses = [r.status for r in world.logs.rows if r.prompt_id == "topic_explanation"]
    assert statuses == ["invalid_output", "success"]


async def test_three_invalid_answers_end_the_job_with_invalid_output(
    world: EvalWorld, llm: FakeLlmProvider
) -> None:
    bad = lambda request: explanation("main")(request).replace("[1]", "[9]")  # noqa: E731
    llm.script("topic_explanation", bad, bad, bad)
    with pytest.raises(TaskError) as raised:
        await world.call("content.explain_topic", {"topic_id": "2"}, REFS)
    assert raised.value.code == "INVALID_OUTPUT"
    assert raised.value.retryable is True


async def test_a_provider_that_keeps_failing_ends_the_job_with_provider_error(
    world: EvalWorld, llm: FakeLlmProvider
) -> None:
    llm.script("topic_explanation", *[LlmProviderError("503") for _ in range(3)])
    with pytest.raises(TaskError) as raised:
        await world.call("content.explain_topic", {"topic_id": "2"}, REFS)
    assert raised.value.code == "LLM_PROVIDER_ERROR"


async def test_unsupported_claims_lower_the_faithfulness(
    world: EvalWorld, llm: FakeLlmProvider
) -> None:
    claims = [
        {"text": "Afirmación uno", "citations": [1], "supported": True, "comment": "ok"},
        {"text": "Afirmación dos", "citations": [1], "supported": True, "comment": "ok"},
        {
            "text": "Afirmación inventada",
            "citations": [2],
            "supported": False,
            "comment": "no está",
        },
    ]
    llm.script("rag_faithfulness", json.dumps({"claims": claims}))
    result = await world.call("content.explain_topic", {"topic_id": "2"}, REFS)
    assert result.result["faithfulness"] == pytest.approx(0.667, abs=0.001)
    assert result.result["unsupported_claims"] == ["Afirmación inventada"]


async def test_faithfulness_citations_must_stay_in_range(
    world: EvalWorld, llm: FakeLlmProvider
) -> None:
    bad = json.dumps(
        {"claims": [{"text": "x", "citations": [99], "supported": True, "comment": "c"}]}
    )
    llm.script("rag_faithfulness", bad)
    await world.call("content.explain_topic", {"topic_id": "2"}, REFS)
    assert len(llm.calls("rag_faithfulness")) == 2


async def test_check_faithfulness_task_uses_the_given_fragments(world: EvalWorld) -> None:
    explained = await world.call("content.explain_topic", {"topic_id": "2"}, REFS)
    source_ids = [s["source_id"] for s in explained.result["sources"]][:2]
    result = await world.call(
        "content.check_faithfulness",
        {
            "topic_id": "2",
            "text": "El modelo lineal usa mínimos cuadrados [1]. Otra cosa [2].",
            "source_ids": source_ids,
        },
        REFS,
    )
    check = FaithfulnessCheck.model_validate(result.result)
    assert result.contract == "faithfulness_check.v1"
    assert check.faithfulness == 1.0
    assert len(check.claims) == 2


async def test_check_faithfulness_rejects_unknown_fragments(world: EvalWorld) -> None:
    await world.call("embeddings.index_course", {"course_id": 1}, REFS)
    with pytest.raises(InputReferenceNotFoundError):
        await world.call(
            "content.check_faithfulness",
            {"topic_id": "2", "text": "algo [1]", "source_ids": ["99999"]},
            REFS,
        )


async def test_an_unknown_topic_ends_the_job_with_input_reference_not_found(
    world: EvalWorld,
) -> None:
    with pytest.raises(InputReferenceNotFoundError):
        await world.call("content.explain_topic", {"topic_id": "404"}, REFS)


async def test_a_course_without_sources_has_no_fragments(
    runtime: EvalRuntime, tmp_path: Path
) -> None:
    empty = tmp_path / "no-sources"
    empty.mkdir()
    options = PipelineOptions(
        syllabus_text=DEFAULT_SYLLABUS.read_text(encoding="utf-8"),
        out_dir=tmp_path / "out",
        sources_dir=empty,
    )
    world = EvalWorld(options, runtime)
    await world.structure_syllabus()
    with pytest.raises(TaskError) as raised:
        await world.call("content.explain_topic", {"topic_id": "2"}, REFS)
    assert raised.value.code == "NO_SOURCE_FRAGMENTS"
    assert raised.value.retryable is False


# ---------- remedial and personal example ----------


async def test_remedial_explanation_is_personal_pseudonymised_and_never_cached(
    world: EvalWorld, llm: FakeLlmProvider
) -> None:
    payload = {
        "topic_id": "3",
        "level": 35.5,
        "profile_text": PROFILE,
        "failed_items": [
            {"stem": "¿Qué hace el umbral?", "learner_answer": "Escríbeme a pedro@correo.com"}
        ],
    }
    refs = JobRefs(course_id=1, enrollment_id=7)
    first = await world.call("content.remedial", payload, refs)
    second = await world.call("content.remedial", payload, refs)
    explanation_ = TopicExplanation.model_validate(first.result)
    assert explanation_.kind == "remedial" and explanation_.audience == "enrollment"
    assert second.result["meta"]["from_cache"] is False
    remedial_calls = llm.calls("remedial_explanation")
    assert len(remedial_calls) == 2
    assert len(llm.calls("rag_faithfulness")) == 2  # personal text: no cache either
    for request in remedial_calls:
        for secret in ("ana.gomez@correo.com", "300 123 4567", "Gómez", "pedro@correo.com"):
            assert secret not in request.user
        assert "[correo]" in request.user and "[nombre]" in request.user
        assert "35.5" in request.user
    for request in llm.calls("rag_faithfulness"):
        assert "ana.gomez" not in request.user


async def test_remedial_input_is_validated() -> None:
    from pydantic import ValidationError

    from app.application.content.explain import RemedialInput

    with pytest.raises(ValidationError):
        RemedialInput.model_validate({"topic_id": "1", "level": 140})


async def test_remedial_budget_is_charged_to_the_enrollment(world: EvalWorld) -> None:
    refs = JobRefs(course_id=1, enrollment_id=7)
    await world.call(
        "content.remedial",
        {"topic_id": "2", "level": 20, "profile_text": "", "failed_items": []},
        refs,
    )
    rows = [r for r in world.logs.rows if r.task == "content.remedial"]
    assert rows and all(r.enrollment_id == 7 and r.course_id == 1 for r in rows)


async def test_personal_example_is_pseudonymised_and_not_cached(
    world: EvalWorld, llm: FakeLlmProvider
) -> None:
    payload = {"topic_id": "2", "profile_text": PROFILE}
    first = await world.call("content.personal_example", payload, REFS)
    await world.call("content.personal_example", payload, REFS)
    example = PersonalizedExample.model_validate(first.result)
    assert example.topic_id == "2"
    calls = llm.calls("personalized_example")
    assert len(calls) == 2
    assert "ana.gomez@correo.com" not in calls[0].user
    assert "Gómez" not in calls[0].user


async def test_task_context_charges_the_course_when_refs_have_none() -> None:
    ctx = TaskContext(refs=JobRefs(enrollment_id=4))
    assert ctx.call("x", course_id=9).scope.course_id == 9
    assert ctx.call("x").scope.course_id is None
    assert isinstance(TaskResult("c", {}), TaskResult)
