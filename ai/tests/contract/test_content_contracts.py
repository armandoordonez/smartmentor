"""Every output of the content pipeline validates against its JSON Schema (plan 5.4.14).

Two layers, as in the notebook: what the (fake) provider returns against the ``…LLM`` schema it
was asked for, and what each task hands to the API against the contract in ``prompts/schemas``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from app.adapters.fake_llm import FakeLlmProvider
from app.ports.llm import LlmRequest, LlmResponse
from eval.pipeline import DEFAULT_SYLLABUS, PipelineOptions, run_pipeline
from eval.runtime import EvalRuntime, build_fake_runtime
from tests.support import SCHEMAS_DIR


class RecordingProvider:
    """Wraps the fake provider and keeps every (request, answer) pair."""

    def __init__(self, inner: FakeLlmProvider) -> None:
        self._inner = inner
        self.pairs: list[tuple[LlmRequest, str]] = []

    @property
    def name(self) -> str:
        return self._inner.name

    async def generate_structured(self, request: LlmRequest) -> LlmResponse:
        response = await self._inner.generate_structured(request)
        self.pairs.append((request, response.text))
        return response


def validate(schema_file: str, instance: Any) -> list[str]:
    schema = json.loads((SCHEMAS_DIR / schema_file).read_text(encoding="utf-8"))
    return [e.message for e in Draft202012Validator(schema).iter_errors(instance)]


@pytest.fixture
async def package(tmp_path: Path) -> tuple[Path, RecordingProvider]:
    runtime: EvalRuntime = build_fake_runtime()
    assert runtime.fake_llm is not None
    recorder = RecordingProvider(runtime.fake_llm)
    runtime.provider = recorder
    out = tmp_path
    options = PipelineOptions(
        syllabus_text=DEFAULT_SYLLABUS.read_text(encoding="utf-8"), out_dir=out
    )
    report = await run_pipeline(options, runtime)
    assert report.issues == []
    return out, recorder


def test_every_provider_answer_matches_the_schema_it_was_asked_for(
    package: tuple[Path, RecordingProvider],
) -> None:
    _, recorder = package
    prompts = {request.prompt_id for request, _ in recorder.pairs}
    assert {
        "topic_explanation",
        "remedial_explanation",
        "rag_faithfulness",
        "topic_quiz",
        "final_assessment",
        "item_review",
        "short_answer_grading",
        "personalized_example",
        "badge_text",
    } <= prompts
    for request, text in recorder.pairs:
        errors = list(Draft202012Validator(request.schema).iter_errors(json.loads(text)))
        assert errors == [], (request.prompt_id, [e.message for e in errors][:3])


@pytest.mark.parametrize(
    ("pattern", "schema"),
    [
        ("syllabus.json", "syllabus.v1.json"),
        ("explanations/*.json", "topic_explanation.v1.json"),
        ("quiz_banks/*.json", "assessment_item_bank.v1.json"),
        ("final_bank.json", "assessment_item_bank.v1.json"),
        ("videos/*.json", "video_resource.v1.json"),
        ("badge.json", "badge_text.v1.json"),
        ("learners/*/personal_example.json", "personalized_example.v1.json"),
        ("learners/*/remedial.json", "topic_explanation.v1.json"),
    ],
)
def test_every_saved_result_matches_its_contract(
    package: tuple[Path, RecordingProvider], pattern: str, schema: str
) -> None:
    out, _ = package
    files = sorted(out.glob(pattern))
    assert files, pattern
    for file in files:
        assert validate(schema, json.loads(file.read_text(encoding="utf-8"))) == [], file.name


def test_gradings_match_the_grading_contract(package: tuple[Path, RecordingProvider]) -> None:
    out, _ = package
    files = sorted(out.glob("learners/*/gradings.json"))
    assert files
    for file in files:
        for grading in json.loads(file.read_text(encoding="utf-8")):
            assert validate("grading.v1.json", grading) == []
