"""Reglas que simulan los datos de ejemplo (las mismas que aplica la API)."""

import pytest

from clients.base import ApiError
from clients.sample_data import SampleDataClient
from clients.sample_seed import build_seed

LAURA, ELENA, ADMIN, RICARDO = 1, 2, 3, 7
ML, STATS = 1, 2


def client(user_id: int) -> SampleDataClient:
    return SampleDataClient(build_seed(), user_id)


def test_student_cannot_use_teacher_or_admin_operations() -> None:
    laura = client(LAURA)
    with pytest.raises(ApiError) as teacher_error:
        laura.list_my_courses()
    with pytest.raises(ApiError) as admin_error:
        laura.list_users()
    assert (teacher_error.value.status, teacher_error.value.code) == (403, "INSUFFICIENT_ROLE")
    assert admin_error.value.status == 403


def test_teacher_only_sees_own_courses() -> None:
    elena = client(ELENA)
    assert {c.id for c in elena.list_my_courses()} == {1, 2, 3, 4}
    with pytest.raises(ApiError) as error:
        client(RICARDO).get_course(ML)
    assert error.value.status == 404


def test_catalog_lists_only_published_paths() -> None:
    assert [p.id for p in client(LAURA).list_learning_paths()] == [1, 2, 3]


def test_enroll_twice_is_a_conflict() -> None:
    with pytest.raises(ApiError) as error:
        client(LAURA).enroll(ML, "perfil")
    assert error.value.code == "ALREADY_ENROLLED"


def test_onboarding_skips_mastered_topics() -> None:
    laura = client(LAURA)
    enrollment = laura.enroll(STATS, "Analista de datos")
    diagnostic = laura.get_diagnostic(enrollment.id)
    # Acierta el primer tema y falla el resto.
    answers: dict[int, int | None] = {q.id: None for q in diagnostic.questions}
    answers[diagnostic.questions[0].id] = 1
    result = laura.submit_diagnostic(enrollment.id, answers)
    assert [level.status for level in result.levels] == ["mastered"] + ["learn"] * 4
    assert result.proposed_objective

    laura.confirm_objective(enrollment.id, "")
    progress = laura.get_path_progress(enrollment.id)
    assert [s.status for s in progress.steps] == [
        "skipped",
        "in_progress",
        "pending",
        "pending",
        "pending",
    ]
    assert progress.saved_minutes == 60


def test_passing_a_topic_quiz_moves_to_the_next_topic() -> None:
    store = build_seed()
    laura = SampleDataClient(store, LAURA)
    correct = {q.id: q.correct for q in store.quiz_questions if q.topic_id == 13}
    result = laura.submit_topic_quiz(1, 13, correct)
    assert result.passed and result.score == 1.0 and result.attempt_number == 2
    statuses = {s.topic_id: s.status for s in laura.get_path_progress(1).steps}
    assert statuses[13] == "approved"
    assert statuses[14] == "in_progress"


def test_final_assessment_demo_fails_and_correct_answers_pass() -> None:
    store = build_seed()
    laura = SampleDataClient(store, LAURA)
    for topic_id in (13, 14, 15):
        answers = {q.id: q.correct for q in store.quiz_questions if q.topic_id == topic_id}
        laura.submit_topic_quiz(1, topic_id, answers)
    assert laura.get_path_progress(1).final_available

    assessment = laura.get_final_assessment(1)
    failed = laura.submit_final_assessment(1, {q.id: 0 for q in assessment.questions})
    assert not failed.passed and failed.score == 0.7
    assert [t.topic_title for t in failed.weak_topics] == [
        "Regresión logística",
        "Evaluación de modelos",
    ]

    passed = laura.submit_final_assessment(1, {q.id: q.correct for q in store.final_questions})
    assert passed.passed and passed.attempt_number == 2
    assert [b.learning_path_id for b in laura.list_my_badges()] == [ML]
    assert not laura.get_path_progress(1).final_available


def test_admin_cannot_edit_own_account() -> None:
    admin = client(ADMIN)
    with pytest.raises(ApiError) as error:
        admin.set_user_role(ADMIN, "student")
    assert error.value.code == "SELF_EDIT_FORBIDDEN"
    assert admin.set_user_active(6, True).active
