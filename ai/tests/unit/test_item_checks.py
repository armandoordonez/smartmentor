"""Code checks of the quiz and final banks (plan 5.4.4, ADR 0015)."""

from __future__ import annotations

from typing import Any

from app.application.items.checks import (
    check_final_bank,
    check_quiz_bank,
    final_source,
    stem_similarity,
)
from app.domain.contracts.assessment import AssessmentItemsLLM

OUTCOMES = {"lo_1", "lo_2"}


def mc(item_id: str, outcome: str, stem: str, group: str = "", **extra: Any) -> dict[str, Any]:
    return {
        "id": item_id,
        "topic_id": "t1",
        "outcome_id": outcome,
        "item_type": "multiple_choice",
        "bloom_level": "apply",
        "difficulty": 2,
        "stem": stem,
        "options": ["uno", "dos", "tres", "cuatro"],
        "correct_option": 0,
        "model_answer": "porque sí",
        "rubric": [],
        "equivalence_group": group,
        **extra,
    }


def sa(item_id: str, outcome: str, stem: str, group: str = "") -> dict[str, Any]:
    return mc(
        item_id,
        outcome,
        stem,
        group,
        item_type="short_answer",
        options=[],
        correct_option=-1,
        rubric=[{"criterion": "primero", "points": 0.5}, {"criterion": "segundo", "points": 0.5}],
    )


def batch(*items: dict[str, Any]) -> AssessmentItemsLLM:
    return AssessmentItemsLLM.model_validate({"items": list(items)})


def quiz_issues(items: AssessmentItemsLLM, previous: list[str] | None = None) -> list[str]:
    return check_quiz_bank(
        items,
        topic_id="t1",
        outcome_ids=OUTCOMES,
        n_multiple_choice=2,
        n_short_answer=1,
        previous_stems=previous or [],
    )


def good_quiz() -> AssessmentItemsLLM:
    return batch(
        mc("q1", "lo_1", "Pregunta sobre barcos antiguos y mareas"),
        mc("q2", "lo_2", "Otra cuestión acerca de volcanes dormidos"),
        sa("q3", "lo_1", "Explica la razón de usar escaleras en bibliotecas"),
    )


def test_a_good_quiz_bank_has_no_issues() -> None:
    assert quiz_issues(good_quiz()) == []


def test_counts_by_type_must_match() -> None:
    items = batch(mc("q1", "lo_1", "uno distinto"), mc("q2", "lo_2", "dos diferente otro"))
    assert any("short-answer items (expected 1)" in i for i in quiz_issues(items))


def test_every_outcome_needs_an_item() -> None:
    items = batch(
        mc("q1", "lo_1", "alfa beta gamma"),
        mc("q2", "lo_1", "delta épsilon zeta"),
        sa("q3", "lo_1", "eta theta iota"),
    )
    assert "outcome 'lo_2' has no item" in quiz_issues(items)


def test_ids_topic_and_group_are_checked() -> None:
    items = batch(
        mc("x1", "lo_1", "alfa beta gamma"),
        mc("q2", "lo_2", "delta épsilon zeta", topic_id="t9"),
        sa("q3", "lo_1", "eta theta iota", group="eg_1"),
    )
    text = "; ".join(quiz_issues(items))
    assert "x1: id must be q<n>" in text
    assert "topic_id must be 't1'" in text
    assert "no equivalence_group" in text


def test_a_stem_that_repeats_the_bank_is_rejected() -> None:
    previous = ["Pregunta sobre barcos antiguos y mareas"]
    assert any(
        "repeats an item that already exists" in i for i in quiz_issues(good_quiz(), previous)
    )


def test_a_stem_that_barely_changes_is_rejected() -> None:
    previous = ["Pregunta sobre barcos antiguos y mareas, ¿no?"]
    assert any("q1" in i for i in quiz_issues(good_quiz(), previous))


def test_repeated_stems_inside_the_batch_are_rejected() -> None:
    items = batch(
        mc("q1", "lo_1", "misma pregunta exacta"),
        mc("q2", "lo_2", "misma pregunta exacta"),
        sa("q3", "lo_1", "eta theta iota"),
    )
    assert any("repeats another item of the batch" in i for i in quiz_issues(items))


def test_stem_similarity_is_jaccard() -> None:
    assert stem_similarity("a b c d", "a b c d") == 1.0
    assert stem_similarity("a b", "c d") == 0.0
    assert stem_similarity("", "a") == 0.0


# ---------- final bank ----------


def final_batch(versions: int = 2) -> AssessmentItemsLLM:
    items: list[dict[str, Any]] = []
    n = 0
    for topic_slot in ("t1",):
        for outcome in ("lo_1", "lo_2"):
            n += 1
            for k in range(1, versions + 1):
                items.append(
                    mc(
                        f"f{n}_v{k}",
                        outcome,
                        f"enunciado {n} versión {k} único {topic_slot}",
                        f"eg_{n}",
                    )
                )
    n += 1
    for k in range(1, versions + 1):
        items.append(sa(f"f{n}_v{k}", "lo_2", f"integra todo {k} caso propio", f"eg_{n}"))
    return batch(*items)


def final_issues(items: AssessmentItemsLLM, versions: int = 2) -> list[str]:
    return check_final_bank(
        items,
        outcomes={"t1": OUTCOMES},
        path_topic_ids=["t1"],
        n_short_answer=1,
        n_versions=versions,
        previous_stems=[],
    )


def test_a_good_final_bank_has_no_issues() -> None:
    assert final_issues(final_batch()) == []


def test_a_missing_version_is_reported() -> None:
    items = final_batch()
    items = AssessmentItemsLLM(items=items.items[:-1])
    assert any("versions" in i for i in final_issues(items))


def test_the_group_must_follow_the_item_number() -> None:
    items = final_batch()
    items.items[0].equivalence_group = "otro"
    assert any("equivalence_group must be eg_1" in i for i in final_issues(items))


def test_parallel_versions_need_different_stems() -> None:
    items = final_batch()
    items.items[1].stem = items.items[0].stem
    assert any("different stems" in i for i in final_issues(items))


def test_ids_must_follow_the_pattern() -> None:
    items = final_batch()
    items.items[0].id = "pregunta1"
    assert any("id must be f<n>_v<k>" in i for i in final_issues(items))


def test_first_version_is_final_and_the_rest_retention() -> None:
    assert final_source("f3_v1") == "final"
    assert final_source("f3_v2") == "retention"
    assert final_source("f3_v3") == "retention"
