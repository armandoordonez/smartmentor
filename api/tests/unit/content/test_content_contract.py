"""Contrato: las salidas de contenido de `FakeAiService` cumplen `prompts/schemas/*.json` y los
modelos de ingesta de la API."""

from collections.abc import Callable
from typing import Any

import pytest
from pydantic import BaseModel

from app.domains.content import contracts, fake_results
from tests.unit.ai_gateway.test_ai_contract import validate

Case = tuple[str, Callable[[dict[str, Any]], dict[str, Any]], dict[str, Any], type[BaseModel]]

CASES: list[Case] = [
    (
        "topic_explanation.v1.json",
        fake_results.fake_explain_topic,
        {"topic_id": "12"},
        contracts.TopicExplanationV1,
    ),
    (
        "faithfulness_check.v1.json",
        fake_results.fake_check_faithfulness,
        {"text": "x"},
        contracts.FaithfulnessCheckV1,
    ),
    (
        "assessment_item_bank.v1.json",
        fake_results.fake_quiz_bank,
        {"topic_id": "12", "n_multiple_choice": 4, "n_short_answer": 1},
        contracts.AssessmentItemBankV1,
    ),
    (
        "assessment_item_bank.v1.json",
        fake_results.fake_final_bank,
        {"topic_ids": ["1", "2"], "n_short_answer": 2},
        contracts.AssessmentItemBankV1,
    ),
    (
        "assessment_item_bank.v1.json",
        fake_results.fake_diagnostic_bank,
        {"topic_ids": ["1", "2"]},
        contracts.AssessmentItemBankV1,
    ),
    (
        "item_review.v1.json",
        fake_results.fake_item_review,
        {"items": [{"item_id": "5"}]},
        contracts.ItemReviewResultV1,
    ),
    (
        "video_resource.v1.json",
        fake_results.fake_video_candidates,
        {"topic_id": "12"},
        contracts.VideoResourceV1,
    ),
]


@pytest.mark.parametrize(("schema", "factory", "input_", "model"), CASES)
def test_the_fake_output_complies_with_the_json_schema_and_the_api_model(
    schema: str,
    factory: Callable[[dict[str, Any]], dict[str, Any]],
    input_: dict[str, Any],
    model: type[BaseModel],
) -> None:
    output = factory(input_)
    validate(schema, output)
    model.model_validate(output)


def test_the_api_model_rejects_a_short_answer_without_rubric() -> None:
    bank = fake_results.fake_quiz_bank(
        {"topic_id": "1", "n_multiple_choice": 0, "n_short_answer": 1}
    )
    bank["items"][0]["rubric"] = []
    with pytest.raises(ValueError, match="rubric"):
        contracts.AssessmentItemBankV1.model_validate(bank)


def test_the_api_model_rejects_a_video_id_with_a_wrong_length() -> None:
    video = fake_results.fake_video_candidates({"topic_id": "1"})
    video["candidates"][0]["youtube_video_id"] = "short"
    with pytest.raises(ValueError, match="pattern"):
        contracts.VideoResourceV1.model_validate(video)


async def test_the_fake_registers_content_jobs_with_their_contract_names() -> None:
    from app.domains.ai_gateway.fake import FakeAiService

    ai = FakeAiService()
    ref = await ai.submit_job("video.collect_candidates", {"topic_id": "9"}, "k")
    job = await ai.get_job(ref.job_id)
    assert job.contract == "video_resource.v1"
    assert job.result is not None
    validate("video_resource.v1.json", job.result)
