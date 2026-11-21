"""Servicios de rutas sobre repositorios en memoria y `FakeAiService` (sin base de datos)."""

from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime

import pytest

from app.common.exceptions import ConflictError, DomainError, ForbiddenError
from app.domains.ai_gateway.fake import FakeAiService
from app.domains.courses.entities import Course, Topic
from app.domains.identity.entities import User, UserProfile
from app.domains.learning_paths.controller import _admin_page
from app.domains.learning_paths.entities import (
    Alert,
    AttemptGrant,
    Enrollment,
    LearningPath,
    PathStep,
    TopicNode,
)
from app.domains.learning_paths.service import (
    EnrollmentService,
    LearnerHistory,
    PathProgress,
    PathStaffService,
)
from app.domains.learning_paths.states import NextAction, ProgressFacts, next_action
from tests.unit.conftest import current
from tests.unit.fakes import FakeUnitOfWork, InMemoryRepository

OWNER, STRANGER, LEARNER = 2, 3, 4


class Paths(InMemoryRepository[LearningPath]):
    async def get_many(self, path_ids: list[int]) -> dict[int, LearningPath]:
        return {i: self.items[i] for i in path_ids if i in self.items}

    async def list_published(self, *, limit: int, offset: int) -> tuple[list[LearningPath], int]:
        found = [p for p in self.items.values() if p.status == "published"]
        return found[offset : offset + limit], len(found)


class Enrollments(InMemoryRepository[Enrollment]):
    async def get_for_update(self, enrollment_id: int) -> Enrollment | None:
        return await self.get(enrollment_id)

    async def find(self, user_id: int, learning_path_id: int) -> Enrollment | None:
        return next(
            (
                e
                for e in self.items.values()
                if e.user_id == user_id and e.learning_path_id == learning_path_id
            ),
            None,
        )

    async def list_for_user(
        self, user_id: int, *, limit: int, offset: int
    ) -> tuple[list[Enrollment], int]:
        found = [e for e in self.items.values() if e.user_id == user_id]
        return found[offset : offset + limit], len(found)

    async def list_for_path(self, learning_path_id: int) -> list[Enrollment]:
        return [e for e in self.items.values() if e.learning_path_id == learning_path_id]

    async def search(  # type: ignore[override]
        self, *, learning_path_id: int | None, status: str | None, limit: int, offset: int
    ) -> tuple[list[Enrollment], int]:
        found = [
            e
            for e in self.items.values()
            if learning_path_id in (None, e.learning_path_id) and status in (None, e.status)
        ]
        return found[offset : offset + limit], len(found)


class Steps(InMemoryRepository[PathStep]):
    async def list_for_enrollment(self, enrollment_id: int) -> list[PathStep]:
        return sorted(
            (s for s in self.items.values() if s.enrollment_id == enrollment_id),
            key=lambda s: s.step_order,
        )

    async def list_for_enrollments(self, enrollment_ids: list[int]) -> list[PathStep]:
        return [s for s in self.items.values() if s.enrollment_id in enrollment_ids]


class Grants(InMemoryRepository[AttemptGrant]):
    async def final_attempts_granted(self, enrollment_id: int) -> int:
        return sum(g.attempts for g in self.items.values() if g.enrollment_id == enrollment_id)

    async def final_attempts_granted_for(self, enrollment_ids: list[int]) -> dict[int, int]:
        return {i: await self.final_attempts_granted(i) for i in enrollment_ids}


class Alerts(InMemoryRepository[Alert]):
    async def list_for_recipient(
        self, user_id: int, *, unread: bool | None, limit: int, offset: int
    ) -> tuple[list[Alert], int]:
        found = [
            a
            for a in self.items.values()
            if a.recipient_user_id == user_id and (unread is not True or a.read_at is None)
        ]
        return found[offset : offset + limit], len(found)


@dataclass
class Reader:
    courses: dict[int, Course] = field(default_factory=dict)
    nodes: list[TopicNode] = field(default_factory=list)
    profiles: dict[int, UserProfile] = field(default_factory=dict)
    consents: set[tuple[int, str]] = field(default_factory=set)
    running_pilot: bool = False
    arm: str | None = None
    unknown_users: set[int] = field(default_factory=set)  # sin fila en `users`
    fact_reads: list[list[int]] = field(default_factory=list)  # una entrada por lectura en lote

    async def course(self, course_id: int) -> Course | None:
        return self.courses.get(course_id)

    async def topic(self, topic_id: int) -> Topic | None:
        return None

    async def topic_nodes(self, course_id: int) -> list[TopicNode]:
        return list(self.nodes)

    async def user(self, user_id: int) -> User | None:
        if user_id in self.unknown_users:
            return None
        return User(id=user_id, full_name=f"Usuario {user_id}", email=f"u{user_id}@example.org")

    async def profile(self, user_id: int) -> UserProfile | None:
        return self.profiles.get(user_id)

    async def consent_in_force(self, user_id: int, consent_type: str) -> bool:
        return (user_id, consent_type) in self.consents

    async def learner_facts(
        self, user_ids: Sequence[int], consent_type: str
    ) -> dict[int, tuple[str, bool]]:
        self.fact_reads.append(list(user_ids))
        found = {i: await self.user(i) for i in user_ids}
        return {
            i: (user.full_name, await self.consent_in_force(i, consent_type))
            for i, user in found.items()
            if user is not None
        }

    async def pilot_running(self, learning_path_id: int) -> bool:
        return self.running_pilot

    async def pilot_arm_for_new_enrollment(self, learning_path_id: int) -> str | None:
        return self.arm

    async def topic_names_for_enrollment(self, enrollment_id: int) -> dict[int, str]:
        return {n.id: n.name for n in self.nodes}

    async def first_admin_id(self) -> int | None:
        return 1


class Progress:
    async def facts(
        self, enrollment: Enrollment, steps: list[PathStep], path: LearningPath | None = None
    ) -> ProgressFacts:
        return ProgressFacts(status=enrollment.status)

    async def facts_many(
        self,
        enrollments: list[Enrollment],
        steps: dict[int, list[PathStep]],
        paths: dict[int, LearningPath],
    ) -> dict[int, ProgressFacts]:
        return {e.id: ProgressFacts(status=e.status) for e in enrollments if e.id is not None}

    async def history(self, enrollment_id: int) -> LearnerHistory:
        return LearnerHistory()


@dataclass
class World:
    paths: Paths
    enrollments: Enrollments
    steps: Steps
    grants: Grants
    alerts: Alerts
    reader: Reader
    ai: FakeAiService
    uow: FakeUnitOfWork
    progress: PathProgress
    enrollment_service: EnrollmentService
    staff: PathStaffService


@pytest.fixture
def world() -> World:
    paths = Paths([LearningPath(id=1, course_id=10, name="Ruta", status="published")])
    enrollments, steps, grants, alerts = Enrollments(), Steps(), Grants(), Alerts()
    reader = Reader(
        courses={10: Course(id=10, name="ML", owner_user_id=OWNER)},
        nodes=[
            TopicNode(1, "Fundamentos", 1, 60, True, ()),
            TopicNode(2, "Lineal", 2, 90, False, (1,)),
            TopicNode(3, "Logística", 3, 120, False, (1, 2)),
        ],
        consents={(LEARNER, "data_processing")},
    )
    ai, uow = FakeAiService(), FakeUnitOfWork()
    progress = PathProgress(enrollments, steps, alerts, reader, ai)
    return World(
        paths,
        enrollments,
        steps,
        grants,
        alerts,
        reader,
        ai,
        uow,
        progress,
        EnrollmentService(paths, enrollments, steps, reader, Progress(), uow),
        PathStaffService(
            paths, enrollments, steps, grants, alerts, reader, progress, Progress(), uow
        ),
    )


async def in_path(world: World, levels: dict[int, float]) -> Enrollment:
    enrollment = await world.enrollments.add(
        Enrollment(user_id=LEARNER, learning_path_id=1, status="in_path")
    )
    path = await world.paths.get(1)
    assert path is not None
    sequenced = await world.progress.sequence(enrollment, path, levels, [])
    await world.progress.create_steps(enrollment, path, sequenced)
    return enrollment


async def test_enrolling_needs_consent_and_a_published_path(world: World) -> None:
    with pytest.raises(ForbiddenError) as refused:
        await world.enrollment_service.enroll(STRANGER, 1)
    assert refused.value.code == "CONSENT_REQUIRED"
    view = await world.enrollment_service.enroll(LEARNER, 1)
    assert view.enrollment.status == "profiling"
    assert view.next_action == NextAction("complete_profile", "E2")
    with pytest.raises(ConflictError):
        await world.enrollment_service.enroll(LEARNER, 1)
    world.paths.items[1] = replace(world.paths.items[1], status="draft")
    world.reader.consents.add((OWNER, "data_processing"))
    with pytest.raises(DomainError) as draft:
        await world.enrollment_service.enroll(OWNER, 1)
    assert draft.value.code == "LEARNING_PATH_NOT_PUBLISHED"


async def test_a_complete_profile_goes_straight_to_the_diagnostic(world: World) -> None:
    world.reader.profiles[LEARNER] = UserProfile(user_id=LEARNER, description="Analista")
    world.reader.consents.add((LEARNER, "pilot_research"))
    view = await world.enrollment_service.enroll(LEARNER, 1)
    assert view.enrollment.status == "diagnosing"
    assert view.enrollment.analysis_included is True


async def test_an_enrollment_after_the_draw_gets_an_arm_only_with_pilot_consent(
    world: World,
) -> None:
    world.reader.arm = "fixed"
    world.reader.consents |= {(LEARNER, "pilot_research"), (OWNER, "data_processing")}
    with_consent = await world.enrollment_service.enroll(LEARNER, 1)
    assert with_consent.enrollment.pilot_arm == "fixed"
    assert with_consent.enrollment.analysis_included is True
    without = await world.enrollment_service.enroll(OWNER, 1)
    assert without.enrollment.pilot_arm is None
    assert without.enrollment.analysis_included is False


async def test_sequencing_creates_the_steps_and_the_dependents_wait(world: World) -> None:
    enrollment = await in_path(world, {1: 95.0, 2: 85.0, 3: 10.0})
    steps = {s.topic_id: s for s in await world.steps.list_for_enrollment(enrollment.id or 0)}
    assert steps[1].status == "pending"  # obligatorio: nunca se omite
    assert steps[2].status == "skipped"
    assert steps[3].status == "blocked"


async def test_exhausting_a_topic_alerts_the_owner_and_holds_its_dependents(world: World) -> None:
    enrollment = await in_path(world, {})
    path = await world.paths.get(1)
    assert path is not None
    steps = {s.topic_id: s for s in await world.steps.list_for_enrollment(enrollment.id or 0)}
    first = await world.progress.set_step_status(steps[1], "in_progress", attempts_used=3)
    await world.progress.apply_topic_result(enrollment, path, first, score=40, passed=False)
    after = {
        s.topic_id: s.status for s in await world.steps.list_for_enrollment(enrollment.id or 0)
    }
    assert after == {1: "attempts_exhausted", 2: "on_hold", 3: "on_hold"}
    alert = next(iter(world.alerts.items.values()))
    assert alert.recipient_user_id == OWNER
    assert alert.alert_type == "topic_attempts_exhausted"

    instructor = current(OWNER, "instructor")
    await world.staff.grant_step_attempts(instructor, first.id or 0, 1, "Uno más")
    regranted = {s.topic_id: s for s in await world.steps.list_for_enrollment(enrollment.id or 0)}
    assert regranted[1].status == "in_progress"
    assert regranted[1].extra_attempts_granted == 1
    assert regranted[2].status == "blocked"
    await world.progress.apply_topic_result(enrollment, path, regranted[1], score=90, passed=True)
    final = {
        s.topic_id: s.status for s in await world.steps.list_for_enrollment(enrollment.id or 0)
    }
    assert final == {1: "passed", 2: "pending", 3: "blocked"}


async def test_all_steps_done_enables_the_final(world: World) -> None:
    enrollment = await in_path(world, {1: 99.0, 2: 99.0, 3: 99.0})
    path = await world.paths.get(1)
    assert path is not None
    step = (await world.steps.list_for_enrollment(enrollment.id or 0))[0]
    step = await world.progress.set_step_status(step, "in_progress")
    await world.progress.apply_topic_result(enrollment, path, step, score=100, passed=True)
    updated = await world.enrollments.get(enrollment.id or 0)
    assert updated is not None
    assert updated.status == "final_ready"
    assert next_action(ProgressFacts(status=updated.status, final_attempts_remaining=3)).type == (
        "take_final"
    )


async def test_settings_need_ownership_valid_weights_and_respect_the_pilot(world: World) -> None:
    owner = current(OWNER, "instructor")
    with pytest.raises(DomainError) as foreign:
        await world.staff.update_settings(
            current(STRANGER, "instructor"), 1, {"max_attempts": 4}, confirm_pilot=False
        )
    assert foreign.value.code == "NOT_FOUND"
    with pytest.raises(DomainError):
        await world.staff.update_settings(
            owner, 1, {"level_weights": {"test": 1, "profile": 1, "resume": 0}}, confirm_pilot=False
        )
    world.reader.running_pilot = True
    with pytest.raises(ConflictError) as pilot:
        await world.staff.update_settings(owner, 1, {"max_attempts": 4}, confirm_pilot=False)
    assert pilot.value.code == "PILOT_RUNNING"
    updated = await world.staff.update_settings(owner, 1, {"max_attempts": 4}, confirm_pilot=True)
    assert updated.max_attempts == 4


async def test_withdraw_and_move_take_the_learner_out_of_the_analysis(world: World) -> None:
    world.paths.items[2] = LearningPath(id=2, course_id=10, name="Otra", status="published")
    created = await world.enrollment_service.enroll(LEARNER, 1)
    moved = await world.enrollment_service.move(created.enrollment.id or 0, 2)
    assert moved.enrollment.learning_path_id == 2
    assert moved.enrollment.analysis_included is False
    old = await world.enrollments.get(created.enrollment.id or 0)
    assert old is not None
    assert old.status == "withdrawn"
    with pytest.raises(ConflictError) as closed:
        await world.enrollment_service.withdraw(created.enrollment.id or 0)
    assert closed.value.code == "ENROLLMENT_CLOSED"
    withdrawn = await world.enrollment_service.withdraw(moved.enrollment.id or 0)
    assert withdrawn.next_action.type == "none"


async def test_the_admin_list_reads_names_and_consents_once_for_the_whole_page(
    world: World,
) -> None:
    """B-056: antes eran dos consultas por inscripción; ahora una lectura por página."""
    with_consent, without_consent, unknown = 5, 6, 7
    world.reader.consents |= {
        (u, "data_processing") for u in (with_consent, without_consent, unknown)
    }
    world.reader.consents.add((with_consent, "pilot_research"))
    world.reader.consents.add((7, "data_processing"))  # el tipo equivocado no cuenta
    world.reader.unknown_users.add(unknown)
    for user_id in (with_consent, without_consent, unknown):
        await world.enrollment_service.enroll(user_id, 1)
    for enrollment in world.enrollments.items.values():
        enrollment.created_at = datetime(2026, 1, 1, tzinfo=UTC)  # la base la pone al insertar

    views, total = await world.enrollment_service.admin_search(
        learning_path_id=None, status=None, limit=20, offset=0
    )
    page = await _admin_page(views, world.enrollment_service)

    assert total == 3
    assert world.reader.fact_reads == [[with_consent, without_consent, unknown]]
    # Igual que la lectura fila a fila: (nombre, consentimiento), o ("", False) sin dato.
    assert [(r.user_id, r.full_name, r.pilot_consent) for r in page] == [
        (with_consent, f"Usuario {with_consent}", True),
        (without_consent, f"Usuario {without_consent}", False),
        (unknown, "", False),
    ]
    for response, view in zip(page, views, strict=True):
        assert response.id == view.enrollment.id
        assert response.learning_path.id == 1


async def test_learner_facts_ignores_repeated_ids_and_skips_the_read_when_empty(
    world: World,
) -> None:
    world.reader.consents.add((LEARNER, "pilot_research"))
    assert await world.enrollment_service.learner_facts([LEARNER, LEARNER]) == {
        LEARNER: (f"Usuario {LEARNER}", True)
    }
    assert world.reader.fact_reads == [[LEARNER]]
    assert await world.enrollment_service.learner_facts([]) == {}
