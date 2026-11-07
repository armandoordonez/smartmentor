"""Registry of the versioned schemas exported to ``prompts/schemas/``.

* Contracts -> ``prompts/schemas/<name>.v1.json`` (what ``ai/`` returns and the API ingests).
* LLM output schemas -> ``prompts/schemas/llm/<name>.v1.json`` (what each prompt asks the
  provider for; referenced by ``output_schema`` in the prompt front matter).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

from app.domain.contracts.assessment import (
    AssessmentItem,
    AssessmentItemBank,
    AssessmentItemsLLM,
    ItemReviewLLM,
    ItemReviewResult,
    SimulatedAnswers,
    SimulatedAnswersLLM,
)
from app.domain.contracts.badge import BadgeAssertion, BadgeText, BadgeTextLLM
from app.domain.contracts.content import (
    FaithfulnessCheck,
    FaithfulnessCheckLLM,
    PersonalizedExample,
    PersonalizedExampleLLM,
    TopicExplanation,
    TopicExplanationLLM,
)
from app.domain.contracts.diagnostic import (
    DiagnosticFinalization,
    DiagnosticResult,
    Objective,
    ObjectiveLLM,
)
from app.domain.contracts.grading import AnswerGrading, ShortAnswerGradingLLM
from app.domain.contracts.learning_path import LearningPath
from app.domain.contracts.syllabus import Syllabus, SyllabusLLM
from app.domain.contracts.video import VideoResource

SCHEMA_VERSION = "v1"
SCHEMA_BASE_URI = "https://smartmentor/schemas"
NOTEBOOK = "design/04-prueba-mago-de-oz/smartmentor_mago_de_oz_gemini_v2.ipynb"

SchemaKind = Literal["contract", "llm"]

CONTRACTS: dict[str, type[BaseModel]] = {
    "syllabus": Syllabus,
    "assessment_item": AssessmentItem,
    "assessment_item_bank": AssessmentItemBank,
    "item_review": ItemReviewResult,
    "diagnostic_result": DiagnosticResult,
    "diagnostic_finalization": DiagnosticFinalization,
    "objective": Objective,
    "learning_path": LearningPath,
    "topic_explanation": TopicExplanation,
    "faithfulness_check": FaithfulnessCheck,
    "personalized_example": PersonalizedExample,
    "video_resource": VideoResource,
    "grading": AnswerGrading,
    "badge_text": BadgeText,
    "badge": BadgeAssertion,
    "simulated_answers": SimulatedAnswers,
}

LLM_SCHEMAS: dict[str, type[BaseModel]] = {
    "syllabus_llm": SyllabusLLM,
    "assessment_items_llm": AssessmentItemsLLM,
    "item_review_llm": ItemReviewLLM,
    "simulated_answers_llm": SimulatedAnswersLLM,
    "objective_llm": ObjectiveLLM,
    "topic_explanation_llm": TopicExplanationLLM,
    "faithfulness_check_llm": FaithfulnessCheckLLM,
    "personalized_example_llm": PersonalizedExampleLLM,
    "short_answer_grading_llm": ShortAnswerGradingLLM,
    "badge_text_llm": BadgeTextLLM,
}

# Notebook v2 model each schema derives from (kept in "$comment").
ORIGIN: dict[str, str] = {
    "syllabus": "Syllabus",
    "assessment_item": "DiagnosticQuestion + QuizQuestion (unified)",
    "assessment_item_bank": "DiagnosticLLM + Quiz + FinalAssessment (unified)",
    "item_review": "ItemReviewLLM",
    "diagnostic_result": "Diagnostic.level_by_topic (TopicLevel)",
    "diagnostic_finalization": "Diagnostic.level_by_topic + Objective",
    "objective": "Objective",
    "learning_path": "PersonalizedPath (PathStep)",
    "topic_explanation": "TopicExplanation",
    "faithfulness_check": "FaithfulnessCheck",
    "personalized_example": "PersonalizedExample",
    "video_resource": "VideoResource (VideoCandidate)",
    "grading": "Grading.results (QuestionResult)",
    "badge_text": "BadgeTextLLM",
    "badge": "BadgeAssertion",
    "simulated_answers": "SimulatedAnswers",
    "syllabus_llm": "SyllabusLLM",
    "assessment_items_llm": "DiagnosticLLM + QuizLLM (unified)",
    "item_review_llm": "ItemReviewLLM",
    "simulated_answers_llm": "SimulatedAnswers",
    "objective_llm": "ObjectiveLLM",
    "topic_explanation_llm": "TopicExplanationLLM",
    "faithfulness_check_llm": "FaithfulnessCheck",
    "personalized_example_llm": "PersonalizedExampleLLM",
    "short_answer_grading_llm": "ShortAnswerGradingLLM",
    "badge_text_llm": "BadgeTextLLM",
}


def schema_relative_path(name: str, kind: SchemaKind) -> str:
    """Path relative to ``prompts/schemas/``."""
    prefix = "llm/" if kind == "llm" else ""
    return f"{prefix}{name}.{SCHEMA_VERSION}.json"


def all_schemas() -> list[tuple[str, SchemaKind, type[BaseModel]]]:
    contracts: list[tuple[str, SchemaKind, type[BaseModel]]] = [
        (name, "contract", model) for name, model in CONTRACTS.items()
    ]
    llm: list[tuple[str, SchemaKind, type[BaseModel]]] = [
        (name, "llm", model) for name, model in LLM_SCHEMAS.items()
    ]
    return contracts + llm


def build_schema(name: str, kind: SchemaKind, model: type[BaseModel]) -> dict[str, Any]:
    """JSON Schema (draft 2020-12) of a model, with stable metadata first."""
    body = model.model_json_schema(by_alias=True, mode="validation")
    header: dict[str, Any] = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"{SCHEMA_BASE_URI}/{schema_relative_path(name, kind)}",
        "$comment": (
            f"Generated by ai/scripts/export_schemas.py from {model.__module__}."
            f"{model.__name__}; do not edit by hand. Origin: {NOTEBOOK} ({ORIGIN[name]}, v2)."
        ),
    }
    return {**header, **body}
