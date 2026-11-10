"""Contrato: las salidas de `FakeAiService` para la ruta cumplen `prompts/schemas/*.json`.

También se validan contra los modelos que usa la API para ingerirlas y contra los ejemplos
publicados en `prompts/examples/`, de modo que si `ai/` cambia un contrato la prueba falla.
"""

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from pydantic import BaseModel

from app.domains.ai_gateway.fake import FakeAiService
from app.domains.ai_gateway.fake_learning import (
    fake_diagnostic_finalize,
    fake_grade_short_answer,
    fake_levels_estimate,
    fake_path_sequence,
    fake_quiz_bank,
)
from app.domains.assessments.contracts import (
    AssessmentItemBankV1,
    DiagnosticFinalizationV1,
    DiagnosticResultV1,
    GradingV1,
)
from app.domains.learning_paths.contracts import LearningPathV1

ROOT = Path(__file__).resolve().parents[4] / "prompts"

LEVELS_INPUT: dict[str, Any] = {
    "topic_ids": ["10", "11", "12"],
    "items": [
        {
            "item_id": "1",
            "topic_id": "10",
            "item_type": "multiple_choice",
            "difficulty": 1,
            "correct_option": 1,
        },
        {
            "item_id": "2",
            "topic_id": "11",
            "item_type": "multiple_choice",
            "difficulty": 2,
            "correct_option": 0,
        },
        {
            "item_id": "3",
            "topic_id": "12",
            "item_type": "multiple_choice",
            "difficulty": 3,
            "correct_option": 3,
        },
    ],
    "answers": [
        {"item_id": "1", "selected_option": 1, "dont_know": False, "text_answer": None},
        {"item_id": "2", "selected_option": 0, "dont_know": True, "text_answer": None},
    ],
    "profile_text": "Analista",
    "resume_text": None,
    "weights": {"test": 0.8, "profile": 0.1, "resume": 0.1},
    "thresholds": {"mastery_skip_threshold": 80, "reinforce_cutoff": 50},
}
SEQUENCE_INPUT: dict[str, Any] = {
    "topics": [
        {"topic_id": "10", "position": 1, "prerequisites": [], "is_mandatory": False},
        {"topic_id": "11", "position": 2, "prerequisites": ["10"], "is_mandatory": True},
        {"topic_id": "12", "position": 3, "prerequisites": ["10", "11"], "is_mandatory": False},
    ],
    "level_by_topic": [
        {"topic_id": "10", "level": 95.5},
        {"topic_id": "11", "level": 90},
        {"topic_id": "12", "level": 4.4},
    ],
    "mastery_skip_threshold": 80,
    "focus_topic_ids": ["12"],
    "pilot_arm": "personalized",
}
GRADING_INPUT: dict[str, Any] = {
    "item_id": "7",
    "stem": "Explica",
    "model_answer": "concepto, ejemplo y conclusión",
    "rubric": [
        {"criterion": "concepto clave", "points": 0.4},
        {"criterion": "ejemplo aplicado", "points": 0.3},
        {"criterion": "conclusión clara", "points": 0.3},
    ],
    "answer_text": "el concepto y un ejemplo",
    "min_criteria_ratio": 0.6667,
}


def validate(schema_name: str, instance: Any) -> None:
    schema = json.loads((ROOT / "schemas" / schema_name).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(instance)


CASES: list[tuple[str, Any, type[BaseModel]]] = [
    ("diagnostic_result.v1.json", fake_levels_estimate(LEVELS_INPUT), DiagnosticResultV1),
    (
        "diagnostic_finalization.v1.json",
        fake_diagnostic_finalize({**LEVELS_INPUT, "objective_mode": "llm", "path_objective": "x"}),
        DiagnosticFinalizationV1,
    ),
    (
        "diagnostic_finalization.v1.json",
        fake_diagnostic_finalize(
            {
                **LEVELS_INPUT,
                "objective_mode": "path_default",
                "path_objective": "Aplicar x con 80 %",
                "path_objective_parts": {
                    "bloom_verb": "Aplicar",
                    "content": "x",
                    "criterion": "con 80 %",
                },
            }
        ),
        DiagnosticFinalizationV1,
    ),
    ("learning_path.v1.json", fake_path_sequence(SEQUENCE_INPUT), LearningPathV1),
    (
        "learning_path.v1.json",
        fake_path_sequence({**SEQUENCE_INPUT, "pilot_arm": "fixed"}),
        LearningPathV1,
    ),
    ("grading.v1.json", fake_grade_short_answer(GRADING_INPUT), GradingV1),
    (
        "assessment_item_bank.v1.json",
        fake_quiz_bank({"topic_id": "12", "n_multiple_choice": 4, "n_short_answer": 1}),
        AssessmentItemBankV1,
    ),
]


@pytest.mark.parametrize(("schema", "output", "model"), CASES)
def test_the_fake_output_complies_with_the_schema_and_the_api_model(
    schema: str, output: Any, model: type[BaseModel]
) -> None:
    validate(schema, output)
    model.model_validate(output)


@pytest.mark.parametrize(
    ("example", "model"),
    [
        ("diagnostic_finalization.json", DiagnosticFinalizationV1),
        ("diagnostic_result.json", DiagnosticResultV1),
        ("learning_path.json", LearningPathV1),
        ("grading.json", GradingV1),
        ("assessment_item_bank.json", AssessmentItemBankV1),
    ],
)
def test_the_published_examples_are_accepted_by_the_api_models(
    example: str, model: type[BaseModel]
) -> None:
    model.model_validate(json.loads((ROOT / "examples" / example).read_text(encoding="utf-8")))


def test_the_fake_levels_follow_the_rules() -> None:
    result = fake_levels_estimate(LEVELS_INPUT)
    by_topic = {t["topic_id"]: t for t in result["level_by_topic"]}
    assert by_topic["10"]["classification"] == "mastered"
    assert by_topic["11"]["level"] == 0  # «No lo sé» cuenta como no acierto
    assert by_topic["12"]["test_score"] == 0


def test_the_fake_sequence_skips_mastered_but_never_mandatory_topics() -> None:
    steps = {s["topic_id"]: s for s in fake_path_sequence(SEQUENCE_INPUT)["steps"]}
    assert steps["10"]["status"] == "skipped"
    assert steps["11"]["inclusion_reason"] == "mandatory"
    assert steps["11"]["status"] == "pending"
    assert steps["12"]["status"] == "blocked"
    assert steps["12"]["inclusion_reason"] == "objective_focus"
    fixed = fake_path_sequence({**SEQUENCE_INPUT, "pilot_arm": "fixed"})["steps"]
    assert {s["inclusion_reason"] for s in fixed} == {"fixed_path"}


def test_the_fake_grading_applies_two_of_three_criteria() -> None:
    graded = fake_grade_short_answer(GRADING_INPUT)
    assert graded["criteria_met"] == 2
    assert graded["is_correct"] is True
    assert graded["score"] == 70.0


async def test_every_learning_job_and_task_of_the_fake_is_contract_valid() -> None:
    ai = FakeAiService()
    jobs = {
        "diagnostic.finalize": (
            {**LEVELS_INPUT, "objective_mode": "llm", "path_objective": "x"},
            "diagnostic_finalization.v1",
        ),
        "grading.short_answer": (GRADING_INPUT, "grading.v1"),
        "items.generate_quiz_bank": (
            {"topic_id": "12", "n_multiple_choice": 2, "n_short_answer": 1},
            "assessment_item_bank.v1",
        ),
    }
    for job_type, (payload, contract) in jobs.items():
        ref = await ai.submit_job(job_type, payload, f"{job_type}:k:1")
        job = await ai.get_job(ref.job_id)
        assert job.contract == contract
        validate(f"{contract}.json", job.result)
    validate("learning_path.v1.json", await ai.run_task("path.sequence", SEQUENCE_INPUT))
    validate("diagnostic_result.v1.json", await ai.run_task("levels.estimate", LEVELS_INPUT))
