"""Unit tests of the intrinsic invariants enforced by the contract models."""

from __future__ import annotations

import copy
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from app.domain.contracts.assessment import (
    AssessmentItemLLM,
    LearnerAnswer,
    LearnerAnswerLLM,
    answer_from_llm,
    item_from_llm,
)
from app.domain.contracts.badge import BadgeAssertion
from app.domain.contracts.common import Meta
from app.domain.contracts.registry import CONTRACTS
from app.domain.contracts.syllabus import SyllabusLLM, syllabus_from_llm
from tests.support import EXAMPLES_DIR, load_json


def _example(name: str) -> dict[str, Any]:
    data: dict[str, Any] = load_json(EXAMPLES_DIR / f"{name}.json")
    return copy.deepcopy(data)


def _rejects(name: str, data: dict[str, Any], fragment: str) -> None:
    model: type[BaseModel] = CONTRACTS[name]
    with pytest.raises(ValidationError, match=fragment):
        model.model_validate(data)


# ---------- Syllabus ----------


def test_syllabus_rejects_cycles_unknown_prerequisites_and_bad_bloom() -> None:
    data = _example("syllabus")
    data["topics"][0]["prerequisites"] = ["regresion_logistica"]
    _rejects("syllabus", data, "prerequisite cycle")
    data = _example("syllabus")
    data["topics"][0]["prerequisites"] = ["inexistente"]
    _rejects("syllabus", data, "unknown prerequisites")
    data = _example("syllabus")
    data["topics"][0]["bloom_level"] = "create"
    _rejects("syllabus", data, "highest of its outcomes")
    data = _example("syllabus")
    data["topics"][1]["id"] = "fundamentos_datos"
    _rejects("syllabus", data, "duplicated topic ids")


def test_syllabus_is_strict_about_unknown_fields() -> None:
    data = _example("syllabus")
    data["approved_by_instructor"] = True
    _rejects("syllabus", data, "Extra inputs are not permitted")


def test_syllabus_from_llm_converts_hours_to_minutes() -> None:
    llm = SyllabusLLM.model_validate(load_json(EXAMPLES_DIR / "llm" / "syllabus_structuring.json"))
    llm.topics[0].estimated_hours = 3
    meta = Meta.model_validate(_example("syllabus")["meta"])
    syllabus = syllabus_from_llm(llm, meta)
    assert syllabus.topics[0].estimated_minutes == 180
    assert syllabus.topics[1].estimated_minutes is None
    assert not any(t.is_mandatory for t in syllabus.topics)


# ---------- Items ----------


def test_item_shapes() -> None:
    data = _example("assessment_item")
    data["rubric"][0]["points"] = 0.1
    _rejects("assessment_item", data, "add up to 1")
    data = _example("assessment_item")
    data["options"] = ["a", "b", "c", "d"]
    _rejects("assessment_item", data, "no options")
    data = _example("assessment_item")
    data["source"] = "final"
    _rejects("assessment_item", data, "equivalence_group")


def test_multiple_choice_item_rules() -> None:
    bank = _example("assessment_item_bank")
    item = bank["items"][0]
    item["options"] = item["options"][:3]
    _rejects("assessment_item", item, "exactly 4 options")
    item = _example("assessment_item_bank")["items"][0]
    item["correct_option"] = 4
    _rejects("assessment_item", item, "less than or equal to 3")
    item = _example("assessment_item_bank")["items"][0]
    item["options"][1] = item["options"][0].upper()
    _rejects("assessment_item", item, "options must be different")


def test_item_from_llm_maps_sentinels_to_null() -> None:
    llm = AssessmentItemLLM.model_validate(
        load_json(EXAMPLES_DIR / "llm" / "final_assessment.json")["items"][4]
    )
    item = item_from_llm(llm, "retention")
    assert item.correct_option is None
    assert item.equivalence_group == "eg_3"
    assert item.source == "retention"


def test_bank_references() -> None:
    data = _example("assessment_item_bank")
    data["discarded_item_ids"] = ["q1"]
    _rejects("assessment_item_bank", data, "only reviewed items without a single answer")
    data = _example("assessment_item_bank")
    data["item_reviews"][0]["item_id"] = "q9"
    _rejects("assessment_item_bank", data, "reviews of unknown items")
    data = _example("assessment_item_bank")
    data["items"][1]["id"] = "q1"
    _rejects("assessment_item_bank", data, "duplicated item ids")
    data = _example("assessment_item_bank")
    data["topic_id"] = "regresion_lineal"
    _rejects("assessment_item_bank", data, "belongs to that topic")


def test_item_review_discarded_must_match_reviews() -> None:
    data = _example("item_review")
    data["discarded_item_ids"] = []
    _rejects("item_review", data, "discarded_item_ids")


def test_learner_answer_is_option_text_or_dont_know() -> None:
    with pytest.raises(ValidationError, match="No lo sé"):
        LearnerAnswer(item_id="d1", selected_option=1, dont_know=True)
    with pytest.raises(ValidationError, match="either an option or a text"):
        LearnerAnswer(item_id="q1", selected_option=1, text_answer="texto")
    llm = LearnerAnswerLLM(item_id="d1", selected_option=-1, dont_know=True, text_answer="")
    assert answer_from_llm(llm) == LearnerAnswer(item_id="d1", dont_know=True)


# ---------- Diagnostic and objective ----------


def test_diagnostic_classification_and_weights() -> None:
    data = _example("diagnostic_result")
    data["level_by_topic"][1]["classification"] = "mastered"
    _rejects("diagnostic_result", data, "classification must be to_reinforce")
    data = _example("diagnostic_result")
    data["level_by_topic"][0]["weights"]["resume"] = 0.3
    _rejects("diagnostic_result", data, "add up to 1")
    data = _example("diagnostic_result")
    data["level_by_topic"][2]["weights"] = {"test": 0.8, "profile": 0.1, "resume": 0.1}
    _rejects("diagnostic_result", data, "missing signals")
    data = _example("diagnostic_result")
    data["thresholds"]["reinforce_cutoff"] = 90
    _rejects("diagnostic_result", data, "cannot exceed")


def test_objective_meta_and_measurable_criterion() -> None:
    data = _example("objective")
    data["origin"] = "path_default"
    _rejects("objective", data, "meta is present only")
    data = _example("objective")
    data["criterion"] = ""
    _rejects("objective", data, "at least 1 character")


def test_finalization_focus_topics_exist() -> None:
    data = _example("diagnostic_finalization")
    data["objective"]["focus_topics"] = ["inexistente"]
    _rejects("diagnostic_finalization", data, "not in the diagnostic")


# ---------- Path, content, video ----------


def test_learning_path_order_and_reasons() -> None:
    data = _example("learning_path")
    data["steps"][1]["step_order"] = 5
    _rejects("learning_path", data, "1..n")
    data = _example("learning_path")
    data["steps"][0]["status"] = "pending"
    _rejects("learning_path", data, "skipped <=> inclusion_reason")
    data = _example("learning_path")
    data["pilot_arm"] = "fixed"
    _rejects("learning_path", data, "fixed arm")


def test_explanation_audience_sources_and_citations() -> None:
    data = _example("topic_explanation")
    data["audience"] = "enrollment"
    _rejects("topic_explanation", data, "audience all_learners")
    data = _example("topic_explanation")
    data["sources"] = data["sources"][:1]
    _rejects("topic_explanation", data, r"citations out of range 1\.\.1: \[2\]")
    data = _example("topic_explanation")
    data["sources"][1]["n"] = 3
    _rejects("topic_explanation", data, "numbered 1..k")


def test_faithfulness_ratio_and_unsupported_list() -> None:
    data = _example("faithfulness_check")
    data["faithfulness"] = 1.0
    _rejects("faithfulness_check", data, "faithfulness must be 0.833")
    data = _example("faithfulness_check")
    data["unsupported_claims"] = []
    _rejects("faithfulness_check", data, "unsupported_claims")


def test_video_ranking_rules() -> None:
    data = _example("video_resource")
    data["candidates"][1]["rank"] = 1
    _rejects("video_resource", data, "ranks must be 1..n")
    data = _example("video_resource")
    data["selected_video_id"] = "EXAMPLE0009"
    _rejects("video_resource", data, "one of the candidates")
    data = _example("video_resource")
    data["origin"] = "none"
    _rejects("video_resource", data, "origin none")
    data = _example("video_resource")
    data["backup_video_ids"] = ["EXAMPLE0001"]
    _rejects("video_resource", data, "backups")


# ---------- Grading and badge ----------


def test_grading_rules() -> None:
    data = _example("grading")
    data["is_correct"] = False
    _rejects("grading", data, "is_correct must follow")
    data = _example("grading")
    data["criteria_met"] = 3
    _rejects("grading", data, "criteria_met")
    data = _example("grading")
    data["rubric_detail"][0]["points_awarded"] = 0.5
    _rejects("grading", data, "exceeds the criterion points")
    data = _example("grading")
    data["meta"] = None
    _rejects("grading", data, "only for llm_judge")


def test_multiple_choice_grading_by_rule() -> None:
    model = CONTRACTS["grading"]
    valid = {
        "item_id": "q1",
        "item_type": "multiple_choice",
        "grader": "rule",
        "approval_rule": "single_correct_option",
        "score": 100,
        "is_correct": True,
        "criteria_met": 0,
        "criteria_total": 0,
        "rubric_detail": [],
        "feedback": "Correcto.",
    }
    model.model_validate(valid)
    with pytest.raises(ValidationError, match="scores 0 or 100"):
        model.model_validate({**valid, "score": 50})
    with pytest.raises(ValidationError, match="graded by rule"):
        model.model_validate({**valid, "approval_rule": "min_criteria_ratio"})


def test_badge_text_and_assertion() -> None:
    data = _example("badge_text")
    data["competencies"] = data["competencies"][:2]
    _rejects("badge_text", data, "at least 3 items")
    assertion = BadgeAssertion.model_validate(_example("badge"))
    dumped = assertion.model_dump(by_alias=True, mode="json")
    assert dumped["@context"] == "https://w3id.org/openbadges/v2"
    assert dumped["issuedOn"] == "2026-11-07T15:30:00Z"
    data = _example("badge")
    data["recipient"]["identity"] = "laura@example.org"
    _rejects("badge", data, "String should match pattern")
