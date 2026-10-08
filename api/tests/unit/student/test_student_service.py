import pytest

from app.common.exceptions import ConflictError, NotFoundError
from app.domains.assessments.entities import AssessmentAttempt, Badge, Diagnostic
from app.domains.learning_paths.entities import Enrollment, LearningPath, PathStep
from app.domains.student.exceptions import EnrollmentClosedError
from app.domains.student.service import StudentService
from tests.unit.fakes import FakeUnitOfWork, InMemoryRepository

ME, OTHER = 10, 20


def make_service() -> tuple[StudentService, FakeUnitOfWork, dict[str, InMemoryRepository]]:  # type: ignore[type-arg]
    repos = {
        "enrollments": InMemoryRepository[Enrollment](
            [
                Enrollment(id=1, user_id=ME, learning_path_id=1),
                Enrollment(id=2, user_id=OTHER, learning_path_id=1),
                Enrollment(id=3, user_id=ME, learning_path_id=1, active=False),
            ]
        ),
        "paths": InMemoryRepository[LearningPath](
            [
                LearningPath(id=1, course_id=1, name="Ruta"),
                LearningPath(id=2, course_id=1, name="Ruta inactiva", active=False),
            ]
        ),
        "steps": InMemoryRepository[PathStep](
            [
                PathStep(id=1, enrollment_id=1, topic_id=2, step_order=2),
                PathStep(id=2, enrollment_id=1, topic_id=1, step_order=1),
                PathStep(id=3, enrollment_id=2, topic_id=1, step_order=1),
            ]
        ),
        "diagnostics": InMemoryRepository[Diagnostic]([Diagnostic(id=1, enrollment_id=1)]),
        "attempts": InMemoryRepository[AssessmentAttempt](
            [
                AssessmentAttempt(id=1, enrollment_id=1, assessment_type="final"),
                AssessmentAttempt(id=2, enrollment_id=2, assessment_type="final"),
            ]
        ),
        "badges": InMemoryRepository[Badge]([Badge(id=1, enrollment_id=2)]),
    }
    uow = FakeUnitOfWork()
    service = StudentService(
        repos["enrollments"],
        repos["paths"],
        repos["steps"],
        repos["diagnostics"],
        repos["attempts"],
        repos["badges"],
        uow,
    )
    return service, uow, repos


async def test_enrollment_belongs_to_the_authenticated_user() -> None:
    service, uow, _ = make_service()
    created = await service.enroll(ME, 1, "Ingeniero", "Aprender regresión")
    assert created.user_id == ME
    assert created.status == "enrolled"
    assert uow.commits == 1


async def test_cannot_enroll_in_a_missing_or_inactive_path() -> None:
    service, _, _ = make_service()
    for path_id in (99, 2):
        with pytest.raises(NotFoundError):
            await service.enroll(ME, path_id, None, None)


async def test_listing_returns_only_my_active_enrollments() -> None:
    service, _, _ = make_service()
    items, total = await service.list_enrollments(ME, limit=10, offset=0)
    assert [e.id for e in items] == [1]  # la 3 es mía pero está inactiva; la 2 es de otro
    assert total == 1


@pytest.mark.parametrize("enrollment_id", [2, 3, 99], ids=["ajena", "inactiva", "inexistente"])
async def test_someone_elses_or_unknown_enrollment_is_not_found(enrollment_id: int) -> None:
    service, _, _ = make_service()
    with pytest.raises(NotFoundError):
        await service.get_enrollment(ME, enrollment_id)
    with pytest.raises(NotFoundError):
        await service.list_steps(ME, enrollment_id, limit=10, offset=0)
    with pytest.raises(NotFoundError):
        await service.get_diagnostic(ME, enrollment_id)
    with pytest.raises(NotFoundError):
        await service.list_attempts(ME, enrollment_id, limit=10, offset=0)
    with pytest.raises(NotFoundError):
        await service.get_badge(ME, enrollment_id)


async def test_steps_come_in_path_order() -> None:
    service, _, _ = make_service()
    steps, total = await service.list_steps(ME, 1, limit=10, offset=0)
    assert [s.step_order for s in steps] == [1, 2]
    assert total == 2  # el paso de la inscripción ajena no aparece


async def test_profile_can_change_until_the_enrollment_closes() -> None:
    service, _, _ = make_service()
    updated = await service.update_profile(ME, 1, {"personal_objective": "Dominar clasificación"})
    assert updated.personal_objective == "Dominar clasificación"
    await service.abandon(ME, 1)
    with pytest.raises(EnrollmentClosedError):
        await service.update_profile(ME, 1, {"personal_objective": "otro"})


async def test_abandon_is_idempotent_and_blocked_when_completed() -> None:
    service, uow, repos = make_service()
    first = await service.abandon(ME, 1)
    commits = uow.commits
    again = await service.abandon(ME, 1)
    assert first.status == again.status == "abandoned"
    assert uow.commits == commits  # la segunda vez no escribe
    await repos["enrollments"].update(1, {"status": "completed"})
    with pytest.raises(EnrollmentClosedError):
        await service.abandon(ME, 1)


async def test_diagnostic_can_be_submitted_only_once() -> None:
    service, _, _ = make_service()
    done = await service.submit_diagnostic(ME, 1, {"1": "b"})
    assert done.answers == {"1": "b"}
    assert done.completed_at is not None
    with pytest.raises(ConflictError) as error:
        await service.submit_diagnostic(ME, 1, {"1": "c"})
    assert error.value.code == "ALREADY_SUBMITTED"


async def test_attempt_submission_sets_answers_but_never_a_score() -> None:
    service, _, _ = make_service()
    submitted = await service.submit_attempt(ME, 1, 1, ["a", "c"])
    assert submitted.answers == ["a", "c"]
    assert submitted.submitted_at is not None
    assert submitted.score is None
    assert submitted.passed is None
    with pytest.raises(ConflictError):
        await service.submit_attempt(ME, 1, 1, ["a", "c"])


async def test_cannot_submit_an_attempt_of_another_enrollment() -> None:
    service, _, _ = make_service()
    with pytest.raises(NotFoundError):
        await service.submit_attempt(ME, 1, 2, ["x"])  # el intento 2 es de la inscripción 2
    with pytest.raises(NotFoundError):
        await service.submit_attempt(ME, 2, 2, ["x"])  # y la inscripción 2 no es mía
