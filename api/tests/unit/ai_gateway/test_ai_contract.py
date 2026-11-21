"""Prueba de contrato: lo que devuelve `FakeAiService` cumple `prompts/schemas/*.json`.

Si `ai/` cambia un contrato (o el fake se desvía), esta prueba falla antes de que la API ingiera
algo inválido. Valida contra el JSON Schema real y contra el modelo Pydantic que usa la API.
"""

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from app.domains.ai_gateway.contracts import CourseGenerateContentResult, SyllabusV1
from app.domains.ai_gateway.fake import FakeAiService, fake_generate_content, fake_syllabus

SCHEMAS = Path(__file__).resolve().parents[4] / "prompts" / "schemas"
EXAMPLES = Path(__file__).resolve().parents[4] / "prompts" / "examples"


def validate(schema_name: str, instance: Any) -> None:
    schema = json.loads((SCHEMAS / schema_name).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(instance)


def test_the_schemas_folder_is_where_the_tests_expect_it() -> None:
    assert (SCHEMAS / "syllabus.v1.json").is_file()


def test_the_fake_syllabus_complies_with_the_json_schema() -> None:
    validate("syllabus.v1.json", fake_syllabus({"syllabus_document_id": 1}))


def test_the_fake_syllabus_complies_with_the_api_model() -> None:
    parsed = SyllabusV1.model_validate(fake_syllabus({"syllabus_document_id": 1}))
    assert [t.id for t in parsed.topics] == [
        "fundamentals",
        "linear_regression",
        "logistic_regression",
    ]


def test_the_published_example_is_accepted_by_the_api_model() -> None:
    example = json.loads((EXAMPLES / "syllabus.json").read_text(encoding="utf-8"))
    validate("syllabus.v1.json", example)
    assert SyllabusV1.model_validate(example).topics


def test_the_api_model_rejects_what_the_schema_rejects() -> None:
    broken = fake_syllabus({"syllabus_document_id": 1})
    broken["topics"][0]["id"] = "NoEsSnakeCase"
    with pytest.raises(Exception):  # noqa: B017, PT011  (jsonschema y pydantic lanzan tipos distintos)
        validate("syllabus.v1.json", broken)
    with pytest.raises(ValueError, match="pattern"):
        SyllabusV1.model_validate(broken)


def test_the_generate_content_result_has_its_model() -> None:
    CourseGenerateContentResult.model_validate(fake_generate_content({}))


async def test_every_job_the_fake_completes_returns_a_contract_valid_result() -> None:
    ai = FakeAiService()
    ref = await ai.submit_job("syllabus.structure", {"syllabus_document_id": 1}, "k:1")
    job = await ai.get_job(ref.job_id)
    assert job.status == "succeeded"
    assert job.contract == "syllabus.v1"
    assert job.result is not None
    validate("syllabus.v1.json", job.result)


async def test_the_fake_returns_the_same_job_for_the_same_key() -> None:
    ai = FakeAiService()
    first = await ai.submit_job("syllabus.structure", {"syllabus_document_id": 1}, "k:1")
    again = await ai.submit_job("syllabus.structure", {"syllabus_document_id": 1}, "k:1")
    other = await ai.submit_job("syllabus.structure", {"syllabus_document_id": 1}, "k:2")
    assert first.job_id == again.job_id
    assert other.job_id != first.job_id
    assert len(ai.submitted) == 2


async def test_the_fake_can_leave_a_job_running_and_finish_it_later() -> None:
    ai = FakeAiService(auto_complete=False)
    ref = await ai.submit_job("syllabus.structure", {"syllabus_document_id": 1}, "k:1")
    assert (await ai.get_job(ref.job_id)).status == "running"
    ai.complete(ref.job_id)
    assert (await ai.get_job(ref.job_id)).status == "succeeded"
