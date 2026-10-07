import pytest

from app.common.exceptions import NotFoundError
from app.domains.assessments.entities import AssessmentAttempt, Badge
from app.domains.assessments.exceptions import (
    FinalAssessmentNotPassedError,
    MaxAttemptsExceededError,
    StepEnrollmentMismatchError,
)
from app.domains.assessments.service import AssessmentAttemptService, BadgeService
from app.domains.learning_paths.entities import Enrollment, LearningPath, PathStep
from tests.unit.fakes import FakeUnitOfWork, InMemoryRepository


class InMemoryAttempts(InMemoryRepository[AssessmentAttempt]):
    async def count_attempts(
        self, enrollment_id: int, path_step_id: int | None, assessment_type: str
    ) -> int:
        return sum(
            1
            for a in self.items.values()
            if a.enrollment_id == enrollment_id
            and a.path_step_id == path_step_id
            and a.assessment_type == assessment_type
        )

    async def has_passed_final(self, enrollment_id: int) -> bool:
        return any(
            a.enrollment_id == enrollment_id
            and a.assessment_type == "final"
            and a.passed is True
            and a.active
            for a in self.items.values()
        )


def make_services(
    max_attempts: int = 3,
) -> tuple[AssessmentAttemptService, BadgeService, InMemoryAttempts]:
    enrollments = InMemoryRepository[Enrollment](
        [
            Enrollment(id=1, user_id=1, learning_path_id=1),
            Enrollment(id=2, user_id=2, learning_path_id=1),
        ]
    )
    learning_paths = InMemoryRepository[LearningPath](
        [
            LearningPath(
                id=1,
                course_id=1,
                name="Ruta",
                topic_pass_threshold=70,
                final_pass_threshold=80,
                max_attempts=max_attempts,
            )
        ]
    )
    steps = InMemoryRepository[PathStep](
        [PathStep(id=1, enrollment_id=1, topic_id=1, step_order=1)]
    )
    attempts = InMemoryAttempts()
    uow = FakeUnitOfWork()
    attempt_service = AssessmentAttemptService(attempts, enrollments, learning_paths, steps, uow)
    badge_service = BadgeService(InMemoryRepository[Badge](), attempts, enrollments, uow)
    return attempt_service, badge_service, attempts


def topic_attempt(score: float | None = None, enrollment_id: int = 1) -> AssessmentAttempt:
    return AssessmentAttempt(
        enrollment_id=enrollment_id, assessment_type="topic", path_step_id=1, score=score
    )


async def test_attempts_are_numbered_consecutively() -> None:
    service, _, _ = make_services()
    first = await service.create(topic_attempt())
    second = await service.create(topic_attempt())
    assert (first.attempt_number, second.attempt_number) == (1, 2)


async def test_stops_at_the_max_attempts_of_the_path() -> None:
    service, _, _ = make_services(max_attempts=2)
    await service.create(topic_attempt())
    await service.create(topic_attempt())
    with pytest.raises(MaxAttemptsExceededError):
        await service.create(topic_attempt())


@pytest.mark.parametrize(("score", "expected"), [(69.99, False), (70, True), (95, True)])
async def test_topic_passes_at_the_topic_threshold(score: float, expected: bool) -> None:
    service, _, _ = make_services()
    attempt = await service.create(topic_attempt(score=score))
    assert attempt.passed is expected


@pytest.mark.parametrize(("score", "expected"), [(79, False), (80, True)])
async def test_final_passes_at_the_final_threshold(score: float, expected: bool) -> None:
    service, _, _ = make_services()
    attempt = await service.create(
        AssessmentAttempt(enrollment_id=1, assessment_type="final", score=score)
    )
    assert attempt.passed is expected


async def test_updating_the_score_recomputes_passed() -> None:
    service, _, _ = make_services()
    attempt = await service.create(topic_attempt(score=50))
    assert attempt.passed is False
    updated = await service.update(attempt.id or 0, {"score": 90})
    assert updated.passed is True


async def test_step_must_belong_to_the_enrollment() -> None:
    service, _, _ = make_services()
    with pytest.raises(StepEnrollmentMismatchError):
        await service.create(topic_attempt(enrollment_id=2))  # el paso 1 es de la inscripción 1


async def test_unknown_enrollment_is_not_found() -> None:
    service, _, _ = make_services()
    with pytest.raises(NotFoundError):
        await service.create(topic_attempt(enrollment_id=99))


async def test_badge_requires_a_passed_final_assessment() -> None:
    attempts, badges, _ = make_services()
    with pytest.raises(FinalAssessmentNotPassedError):
        await badges.create(Badge(enrollment_id=1))

    await attempts.create(AssessmentAttempt(enrollment_id=1, assessment_type="final", score=60))
    with pytest.raises(FinalAssessmentNotPassedError):
        await badges.create(Badge(enrollment_id=1))

    await attempts.create(AssessmentAttempt(enrollment_id=1, assessment_type="final", score=85))
    badge = await badges.create(Badge(enrollment_id=1))
    assert badge.id is not None
