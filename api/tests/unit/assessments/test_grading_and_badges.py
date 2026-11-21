"""Reglas puras de calificación, SUS, selección de ítems y badge Open Badges."""

import hashlib
import struct
import zlib
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.common.exceptions import BusinessRuleError
from app.domains.assessments import badges
from app.domains.assessments.entities import AssessmentItem, AttemptAnswer
from app.domains.assessments.grading import (
    attempt_score,
    grade_multiple_choice,
    pick_quiz_items,
    round_robin,
    short_answer_is_correct,
    sus_score,
)
from app.domains.learning_paths.entities import LearningPath, PathStep


def item(item_id: int, kind: str = "multiple_choice", topic: int = 1) -> AssessmentItem:
    return AssessmentItem(
        id=item_id,
        topic_id=topic,
        source="topic_quiz",
        item_type=kind,
        bloom_level="apply",
        difficulty=1,
        stem=f"Pregunta {item_id}",
        options=["A", "B", "C", "D"],
        correct_option="2",
    )


def answer(selected: str | None = None, *, dont_know: bool = False) -> AttemptAnswer:
    return AttemptAnswer(
        assessment_attempt_id=1, assessment_item_id=1, selected_option=selected, dont_know=dont_know
    )


def test_multiple_choice_is_graded_by_the_key() -> None:
    assert grade_multiple_choice(item(1), answer("2"))["score"] == 100.0
    assert grade_multiple_choice(item(1), answer("1"))["is_correct"] is False
    assert grade_multiple_choice(item(1), answer(None))["is_correct"] is False


def test_dont_know_is_a_miss_even_with_the_right_option() -> None:
    graded = grade_multiple_choice(item(1), answer("2", dont_know=True))
    assert graded["is_correct"] is False
    assert graded["grader"] == "rule"
    assert graded["approval_rule"] == "single_correct_option"


@pytest.mark.parametrize(
    ("met", "total", "ratio", "expected"),
    [
        (2, 3, 0.667, True),  # 2 de 3 (DEF-21), con la proporción redondeada de la base
        (2, 3, 2 / 3, True),
        (1, 3, 0.667, False),
        (3, 3, 1.0, True),
        (1, 2, 0.667, False),
        (0, 0, 0.5, False),
    ],
)
def test_short_answer_approval_by_criteria_ratio(
    met: int, total: int, ratio: float, expected: bool
) -> None:
    assert short_answer_is_correct(met, total, ratio) is expected


def test_attempt_score_is_the_mean_of_the_answers() -> None:
    assert attempt_score([100, 100, 100, 100, 70]) == 94.0
    assert attempt_score([None, 50]) == 25.0
    assert attempt_score([]) == 0.0


def test_sus_score_formula() -> None:
    assert sus_score([4, 2, 5, 1, 4, 2, 5, 1, 4, 2]) == 85.0
    assert sus_score([5, 1] * 5) == 100.0
    assert sus_score([1, 5] * 5) == 0.0
    with pytest.raises(BusinessRuleError):
        sus_score([3] * 9)
    with pytest.raises(BusinessRuleError):
        sus_score([0] * 10)


def test_quiz_picks_at_most_one_short_answer_and_fills_with_choices() -> None:
    bank = [item(n) for n in range(1, 8)] + [item(20, "short_answer"), item(21, "short_answer")]
    picked = pick_quiz_items(bank, 5)
    assert len(picked) == 5
    assert sum(1 for i in picked if i.item_type == "short_answer") == 1
    only_short = [item(30, "short_answer"), item(31, "short_answer")]
    assert len(pick_quiz_items(only_short, 5)) == 2


def test_final_items_are_spread_over_the_topics() -> None:
    bank = [item(n, topic=1) for n in range(1, 5)] + [item(n, topic=2) for n in range(5, 7)]
    picked = round_robin(bank, [2, 1], 4)
    assert [i.topic_id for i in picked] == [2, 1, 2, 1]


def test_remaining_attempts_include_the_extra_ones() -> None:
    step = PathStep(enrollment_id=1, topic_id=1, step_order=1, attempts_used=3)
    assert step.remaining_attempts(3) == 0
    step.extra_attempts_granted = 1
    assert step.remaining_attempts(3) == 1


def test_level_weights_are_normalised_from_percentages() -> None:
    path = LearningPath(
        course_id=1, name="x", level_weights={"test": 80, "profile": 10, "resume": 10}
    )
    assert path.weights == {"test": 0.8, "profile": 0.1, "resume": 0.1}
    assert LearningPath(course_id=1, name="x", level_weights={}).weights["test"] == 0.8


def test_default_objective_needs_the_three_parts() -> None:
    path = LearningPath(course_id=1, name="x", default_objective_bloom_verb="Aplicar")
    assert path.default_objective_parts is None
    path.default_objective_content, path.default_objective_criterion = "algo", "con 80 %"
    assert path.default_objective_parts == {
        "bloom_verb": "Aplicar",
        "content": "algo",
        "criterion": "con 80 %",
    }


def test_the_assertion_only_carries_a_salted_hash_of_the_email() -> None:
    public_id = uuid4()
    assertion = badges.build_assertion(
        public_id=public_id,
        base_url="",
        email="Laura@Example.org",
        issued_on=datetime(2026, 11, 7, tzinfo=UTC),
        course_name="ML",
        path_name="Ruta",
        objective=None,
        topic_names=["A"],
        final_score=90,
        final_pass_threshold=80,
        issuer_name="SmartMentor",
        issuer_url="https://smartmentor.example",
    )
    recipient = assertion["recipient"]
    digest = hashlib.sha256(("laura@example.org" + recipient["salt"]).encode()).hexdigest()
    assert recipient["identity"] == f"sha256${digest}"
    assert "laura" not in str(assertion).lower()
    absolute = badges.with_base_url(assertion, "https://api.example/")
    assert absolute["id"] == f"https://api.example/api/v1/badges/{public_id}/assertion.json"
    assert absolute["badge"]["image"].endswith(f"/badges/{public_id}/image.png")


def test_the_badge_image_is_a_valid_png() -> None:
    png = badges.badge_png("seed", size=16)
    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    length = struct.unpack(">I", png[8:12])[0]
    assert png[12:16] == b"IHDR"
    assert struct.unpack(">II", png[16:24]) == (16, 16)
    idat_start = 8 + 12 + length
    idat_length = struct.unpack(">I", png[idat_start : idat_start + 4])[0]
    raw = zlib.decompress(png[idat_start + 8 : idat_start + 8 + idat_length])
    assert len(raw) == 16 * (1 + 16 * 4)
