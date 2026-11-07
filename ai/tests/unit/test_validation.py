"""Unit tests of the code checks on LLM outputs (``validation.py``) and the graph helpers."""

from __future__ import annotations

import copy
from typing import Any

import pytest

from app.domain.contracts import validation as v
from app.domain.contracts.assessment import (
    AssessmentItemsLLM,
    ItemReviewLLM,
    RubricCriterion,
    SimulatedAnswersLLM,
)
from app.domain.contracts.badge import BadgeTextLLM
from app.domain.contracts.common import ItemType
from app.domain.contracts.content import FaithfulnessCheckLLM, TopicExplanationLLM
from app.domain.contracts.diagnostic import ObjectiveLLM
from app.domain.contracts.grading import ShortAnswerGradingLLM
from app.domain.contracts.graph import find_cycle, topological_order
from app.domain.contracts.syllabus import SyllabusLLM
from tests.support import EXAMPLES_DIR, load_json

OUTCOMES = {
    "fundamentos_datos": ["lo_fundamentos_datos_1", "lo_fundamentos_datos_2"],
    "regresion_lineal": ["lo_regresion_lineal_1", "lo_regresion_lineal_2"],
    "regresion_logistica": [
        "lo_regresion_logistica_1",
        "lo_regresion_logistica_2",
        "lo_regresion_logistica_3",
    ],
}


def _llm_example(prompt_id: str) -> dict[str, Any]:
    data: dict[str, Any] = load_json(EXAMPLES_DIR / "llm" / f"{prompt_id}.json")
    return copy.deepcopy(data)


def _has(issues: list[str], fragment: str) -> bool:
    return any(fragment in issue for issue in issues)


# ---------- Graph ----------


def test_find_cycle_returns_a_closed_path() -> None:
    cycle = find_cycle({"a": ["c"], "b": ["a"], "c": ["b"]})
    assert cycle is not None
    assert cycle[0] == cycle[-1]
    assert set(cycle) == {"a", "b", "c"}


def test_find_cycle_none_for_a_dag_and_ignores_unknown_ids() -> None:
    assert find_cycle({"a": [], "b": ["a", "ghost"], "c": ["a", "b"]}) is None


def test_find_cycle_detects_self_loop() -> None:
    assert find_cycle({"a": ["a"]}) == ["a", "a"]


def test_topological_order_keeps_syllabus_order_when_possible() -> None:
    order = ["c", "a", "b"]
    assert topological_order(order, {"c": ["b"], "a": [], "b": ["a"]}) == ["a", "b", "c"]
    assert topological_order(["x", "y"], {"x": [], "y": []}) == ["x", "y"]


def test_topological_order_raises_on_cycle() -> None:
    with pytest.raises(ValueError, match="cycle"):
        topological_order(["a", "b"], {"a": ["b"], "b": ["a"]})


# ---------- Syllabus ----------


def test_valid_syllabus_has_no_issues() -> None:
    assert v.check_syllabus(SyllabusLLM.model_validate(_llm_example("syllabus_structuring"))) == []


def test_syllabus_cycle_unknown_prerequisite_and_duplicates() -> None:
    data = _llm_example("syllabus_structuring")
    data["topics"][0]["prerequisites"] = ["regresion_logistica"]
    data["topics"][1]["prerequisites"].append("inexistente")
    data["topics"][2]["id"] = "regresion_lineal"
    issues = v.check_syllabus(SyllabusLLM.model_validate(data))
    assert _has(issues, "prerequisite 'inexistente' does not exist")
    assert _has(issues, "duplicated topic id 'regresion_lineal'")


def test_syllabus_cycle_is_reported_with_its_path() -> None:
    data = _llm_example("syllabus_structuring")
    data["topics"][0]["prerequisites"] = ["regresion_logistica"]
    issues = v.check_syllabus(SyllabusLLM.model_validate(data))
    assert _has(issues, "prerequisite cycle: ")


def test_syllabus_outcome_ids_bloom_and_ids_format() -> None:
    data = _llm_example("syllabus_structuring")
    data["course_key"] = "Fundamentos ML"
    data["topics"][0]["learning_outcomes"][0]["id"] = "lo_x_9"
    data["topics"][1]["bloom_level"] = "create"
    data["topics"][2]["learning_outcomes"] = data["topics"][2]["learning_outcomes"][:1]
    data["topics"][2]["estimated_hours"] = -1
    issues = v.check_syllabus(SyllabusLLM.model_validate(data))
    assert _has(issues, "is not snake_case")
    assert _has(issues, "should be lo_fundamentos_datos_1")
    assert _has(issues, "regresion_lineal: bloom_level is not the highest")
    assert _has(issues, "1 learning outcomes")
    assert _has(issues, "estimated_hours cannot be negative")


def test_syllabus_self_prerequisite() -> None:
    data = _llm_example("syllabus_structuring")
    data["topics"][0]["prerequisites"] = ["fundamentos_datos"]
    assert _has(
        v.check_syllabus(SyllabusLLM.model_validate(data)), "cannot be its own prerequisite"
    )


# ---------- Items ----------


def test_quiz_items_valid() -> None:
    items = AssessmentItemsLLM.model_validate(_llm_example("topic_quiz"))
    assert v.check_assessment_items(items, OUTCOMES) == []


def test_multiple_choice_needs_four_distinct_options_and_one_index_in_range() -> None:
    data = _llm_example("topic_quiz")
    data["items"][0]["options"] = data["items"][0]["options"][:3]
    data["items"][1]["correct_option"] = 4
    data["items"][2]["options"][3] = data["items"][2]["options"][0]
    data["items"][2]["rubric"] = [{"criterion": "x", "points": 1}]
    issues = v.check_assessment_items(AssessmentItemsLLM.model_validate(data), OUTCOMES)
    assert _has(issues, "q1: 3 options (expected 4)")
    assert _has(issues, "q2: correct_option 4 out of range")
    assert _has(issues, "q3: repeated options")
    assert _has(issues, "q3: multiple choice must have an empty rubric")


def test_short_answer_shape_and_rubric_total() -> None:
    data = _llm_example("topic_quiz")
    short = data["items"][3]
    short["options"] = ["a"]
    short["correct_option"] = 0
    short["rubric"][0]["points"] = 0.9
    issues = v.check_assessment_items(AssessmentItemsLLM.model_validate(data), OUTCOMES)
    assert _has(issues, "q4: short answer must have no options")
    assert _has(issues, "q4: short answer must have correct_option -1")
    assert _has(issues, "q4: rubric points add up to")


def test_items_reference_existing_topic_and_outcome_of_that_topic() -> None:
    data = _llm_example("topic_quiz")
    data["items"][0]["topic_id"] = "inexistente"
    data["items"][1]["outcome_id"] = "lo_regresion_lineal_1"
    data["items"][2]["difficulty"] = 5
    data["items"][3]["id"] = "q1"
    issues = v.check_assessment_items(AssessmentItemsLLM.model_validate(data), OUTCOMES)
    assert _has(issues, "topic 'inexistente' does not exist")
    assert _has(issues, "is not of topic 'regresion_logistica'")
    assert _has(issues, "difficulty 5 out of 1..3")
    assert _has(issues, "duplicated item id 'q1'")


def test_empty_item_batch_is_an_issue() -> None:
    assert v.check_assessment_items(AssessmentItemsLLM(items=[]), OUTCOMES) == [
        "no items were generated"
    ]


def test_diagnostic_coverage() -> None:
    items = AssessmentItemsLLM.model_validate(_llm_example("diagnostic_generation"))
    assert v.check_diagnostic_coverage(items, list(OUTCOMES)) == []
    items.items = items.items[1:]
    assert _has(v.check_diagnostic_coverage(items, list(OUTCOMES)), "fundamentos_datos")


def test_final_coverage_groups_and_versions() -> None:
    data = _llm_example("final_assessment")
    path = ["regresion_lineal", "regresion_logistica"]
    items = AssessmentItemsLLM.model_validate(data)
    assert v.check_final_coverage(items, path, short_answers=1, versions=2) == []
    data["items"][1]["difficulty"] = 1
    data["items"][2]["equivalence_group"] = ""
    data["items"][3]["topic_id"] = "fundamentos_datos"
    issues = v.check_final_coverage(
        AssessmentItemsLLM.model_validate(data), path, short_answers=2, versions=2
    )
    assert _has(issues, "eg_1: parallel versions differ")
    assert _has(issues, "f2_v1: final items need equivalence_group")
    assert _has(issues, "eg_2: 1 versions (expected 2)")
    assert _has(issues, "not in the learning path")
    assert _has(issues, "short-answer items (expected 2)")


def test_item_reviews_cover_every_item_once() -> None:
    reviews = ItemReviewLLM.model_validate(_llm_example("item_review"))
    assert v.check_item_reviews(reviews, ["q1", "q2", "q3", "q4"]) == []
    assert v.discarded_item_ids(reviews) == ["q3"]
    issues = v.check_item_reviews(reviews, ["q1", "q2", "q3", "q5"])
    assert _has(issues, "review of unknown item 'q4'")
    assert _has(issues, "item 'q5' was not reviewed")
    reviews.reviews.append(reviews.reviews[0])
    assert _has(v.check_item_reviews(reviews, ["q1", "q2", "q3", "q4"]), "reviewed more than once")


def test_simulated_answers() -> None:
    types: dict[str, ItemType] = {
        "q1": "multiple_choice",
        "q2": "multiple_choice",
        "q3": "multiple_choice",
        "q4": "short_answer",
    }
    answers = SimulatedAnswersLLM.model_validate(_llm_example("simulated_learner"))
    assert v.check_simulated_answers(answers, types, allow_dont_know=False) == []
    answers.answers[0].dont_know = True
    answers.answers[1].selected_option = 7
    answers.answers[3].text_answer = ""
    issues = v.check_simulated_answers(answers, types, allow_dont_know=False)
    assert _has(issues, "q1: «No lo sé» is only allowed in the diagnostic")
    assert _has(issues, "q2: multiple choice needs an option 0..3")
    assert _has(issues, "q4: short answer needs selected_option -1 and a text")


# ---------- Objective, content, grading, badge ----------


def test_objective_needs_three_parts_and_known_focus_topics() -> None:
    objective = ObjectiveLLM.model_validate(_llm_example("learning_objective"))
    assert v.check_objective(objective, list(OUTCOMES)) == []
    objective.criterion = " "
    objective.focus_topics = ["inexistente"]
    issues = v.check_objective(objective, list(OUTCOMES))
    assert _has(issues, "objective criterion is empty")
    assert _has(issues, "focus topic 'inexistente' does not exist")


def test_explanation_citations_within_range() -> None:
    explanation = TopicExplanationLLM.model_validate(_llm_example("topic_explanation"))
    assert v.check_explanation(explanation, 2) == []
    issues = v.check_explanation(explanation, 1)
    assert _has(issues, "citations out of range 1..1: [2]")
    explanation.sections[0].body += " [0]"
    assert _has(v.check_explanation(explanation, 2), "[0]")


def test_explanation_structure_rules() -> None:
    explanation = TopicExplanationLLM.model_validate(_llm_example("remedial_explanation"))
    assert v.check_explanation(explanation, 2, kind="remedial") == []
    issues = v.check_explanation(explanation, 2, kind="main")
    assert _has(issues, "2 sections (expected 3 to 5)")
    explanation.reflection_questions = []
    for section in explanation.sections:
        section.body = "sin citas"
    explanation.worked_example = explanation.summary = ""
    issues = v.check_explanation(explanation, 2, kind="remedial")
    assert _has(issues, "0 reflection questions")
    assert _has(issues, "cites no fragment")
    assert v.uncited_sections(explanation) == [s.heading for s in explanation.sections]


def test_faithfulness_citations_and_claim_limit() -> None:
    check = FaithfulnessCheckLLM.model_validate(_llm_example("rag_faithfulness"))
    assert v.check_faithfulness(check, 2) == []
    assert _has(v.check_faithfulness(check, 1), "claim 4: citations out of range 1..1: [2]")
    check.claims = check.claims * 3
    assert _has(v.check_faithfulness(check, 2), "18 claims (at most 15)")


def test_short_answer_grading_follows_the_rubric() -> None:
    rubric = [
        RubricCriterion(criterion="Propone bajar el umbral por debajo de 0,5", points=0.4),
        RubricCriterion(
            criterion="Explica que disminuyen los falsos negativos y aumentan los falsos positivos",
            points=0.4,
        ),
        RubricCriterion(criterion="Justifica la decisión con la diferencia de costos", points=0.2),
    ]
    grading = ShortAnswerGradingLLM.model_validate(_llm_example("short_answer_grading"))
    assert v.check_short_answer_grading(grading, rubric) == []
    grading.criteria[0].points_awarded = 0.9
    grading.criteria[1].criterion = "Otro criterio"
    grading.feedback = ""
    issues = v.check_short_answer_grading(grading, rubric)
    assert _has(issues, "points_awarded 0.9 out of 0..0.4")
    assert _has(issues, "criterion 'Otro criterio' is not in the rubric")
    assert _has(issues, "was not graded")
    assert _has(issues, "feedback is empty")


def test_badge_text_competencies() -> None:
    badge = BadgeTextLLM.model_validate(_llm_example("badge_text"))
    assert v.check_badge_text(badge) == []
    badge.competencies = badge.competencies[:2]
    badge.name = ""
    issues = v.check_badge_text(badge)
    assert _has(issues, "2 competencies (expected 3 to 5)")
    assert _has(issues, "name is empty")


def test_ensure_valid_raises_with_the_issues() -> None:
    v.ensure_valid([])
    with pytest.raises(v.ContractCheckError) as error:
        v.ensure_valid(["a", "b"])
    assert error.value.issues == ["a", "b"]
    assert str(error.value) == "a; b"
