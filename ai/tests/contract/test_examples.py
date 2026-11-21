"""Every example output validates against its versioned JSON Schema, its Pydantic model and,
for LLM outputs, the code checks of ``validation.py`` (what ``FakeLlmProvider`` will return)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from app.domain.contracts import validation as v
from app.domain.contracts.assessment import (
    AssessmentItemsLLM,
    ItemReviewLLM,
    RubricCriterion,
    SimulatedAnswersLLM,
    item_from_llm,
)
from app.domain.contracts.badge import BadgeTextLLM
from app.domain.contracts.content import (
    FaithfulnessCheckLLM,
    PersonalizedExampleLLM,
    TopicExplanationLLM,
)
from app.domain.contracts.diagnostic import ObjectiveLLM
from app.domain.contracts.grading import ShortAnswerGradingLLM
from app.domain.contracts.registry import CONTRACTS, LLM_SCHEMAS, schema_relative_path
from app.domain.contracts.syllabus import Syllabus, SyllabusLLM
from tests.support import EXAMPLES_DIR, PROMPTS_DIR, SCHEMAS_DIR, load_catalog, load_json

CATALOG = {p["id"]: p for p in load_catalog()["prompts"]}
FRAGMENTS_IN_EXAMPLES = 2


def _validator(relative: str) -> Draft202012Validator:
    return Draft202012Validator(
        load_json(SCHEMAS_DIR / relative), format_checker=Draft202012Validator.FORMAT_CHECKER
    )


# ---------- Contract examples ----------


@pytest.mark.parametrize("name", sorted(CONTRACTS))
def test_contract_example_matches_schema_and_model(name: str) -> None:
    data = load_json(EXAMPLES_DIR / f"{name}.json")
    errors = [
        e.message for e in _validator(schema_relative_path(name, "contract")).iter_errors(data)
    ]
    assert errors == []
    CONTRACTS[name].model_validate(data)


def test_every_example_file_is_registered() -> None:
    contracts = {p.stem for p in EXAMPLES_DIR.glob("*.json")}
    llm = {p.stem for p in (EXAMPLES_DIR / "llm").glob("*.json")}
    assert contracts == set(CONTRACTS)
    assert llm == set(CATALOG)


# ---------- LLM examples (one per prompt) ----------

SYLLABUS = Syllabus.model_validate(load_json(EXAMPLES_DIR / "syllabus.json"))
OUTCOMES = {t.id: [o.id for o in t.learning_outcomes] for t in SYLLABUS.topics}
TOPIC_IDS = [t.id for t in SYLLABUS.topics]
QUIZ = AssessmentItemsLLM.model_validate(load_json(EXAMPLES_DIR / "llm" / "topic_quiz.json"))
SHORT_ANSWER = next(i for i in QUIZ.items if i.item_type == "short_answer")


def _rubric() -> list[RubricCriterion]:
    return item_from_llm(SHORT_ANSWER, "topic_quiz").rubric


CHECKS: dict[str, Callable[[dict[str, Any]], list[str]]] = {
    "syllabus_structuring": lambda d: v.check_syllabus(SyllabusLLM.model_validate(d)),
    "diagnostic_generation": lambda d: (
        v.check_assessment_items(AssessmentItemsLLM.model_validate(d), OUTCOMES)
        + v.check_diagnostic_coverage(AssessmentItemsLLM.model_validate(d), TOPIC_IDS)
    ),
    "topic_quiz": lambda d: v.check_assessment_items(
        AssessmentItemsLLM.model_validate(d), OUTCOMES
    ),
    "final_assessment": lambda d: (
        v.check_assessment_items(AssessmentItemsLLM.model_validate(d), OUTCOMES)
        + v.check_final_coverage(
            AssessmentItemsLLM.model_validate(d),
            ["regresion_lineal", "regresion_logistica"],
            short_answers=1,
            versions=2,
        )
    ),
    "item_review": lambda d: v.check_item_reviews(
        ItemReviewLLM.model_validate(d), [i.id for i in QUIZ.items]
    ),
    "simulated_learner": lambda d: v.check_simulated_answers(
        SimulatedAnswersLLM.model_validate(d),
        {i.id: i.item_type for i in QUIZ.items},
        allow_dont_know=False,
    ),
    "learning_objective": lambda d: v.check_objective(ObjectiveLLM.model_validate(d), TOPIC_IDS),
    "topic_explanation": lambda d: v.check_explanation(
        TopicExplanationLLM.model_validate(d), FRAGMENTS_IN_EXAMPLES, kind="main"
    ),
    "remedial_explanation": lambda d: v.check_explanation(
        TopicExplanationLLM.model_validate(d), FRAGMENTS_IN_EXAMPLES, kind="remedial"
    ),
    "personalized_example": lambda d: v.check_personalized_example(
        PersonalizedExampleLLM.model_validate(d)
    ),
    "rag_faithfulness": lambda d: v.check_faithfulness(
        FaithfulnessCheckLLM.model_validate(d), FRAGMENTS_IN_EXAMPLES
    ),
    "short_answer_grading": lambda d: v.check_short_answer_grading(
        ShortAnswerGradingLLM.model_validate(d), _rubric()
    ),
    "badge_text": lambda d: v.check_badge_text(BadgeTextLLM.model_validate(d)),
}


def test_every_prompt_has_a_check() -> None:
    assert set(CHECKS) == set(CATALOG)


@pytest.mark.parametrize("prompt_id", sorted(CATALOG))
def test_llm_example_matches_output_schema_and_checks(prompt_id: str) -> None:
    entry = CATALOG[prompt_id]
    data = load_json(EXAMPLES_DIR / "llm" / f"{prompt_id}.json")
    errors = [e.message for e in _validator(entry["output_schema"]).iter_errors(data)]
    assert errors == []
    schema_name = entry["output_schema"].removeprefix("llm/").removesuffix(".v1.json")
    LLM_SCHEMAS[schema_name].model_validate(data)
    assert CHECKS[prompt_id](data) == []


def test_prompt_directories_have_examples() -> None:
    dirs = {p.parent.name for p in PROMPTS_DIR.glob("*/v*.md")}
    assert dirs == set(CATALOG)
