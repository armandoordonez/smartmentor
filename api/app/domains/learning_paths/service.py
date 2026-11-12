"""Casos de uso de rutas: catálogo, inscripciones, pasos, intentos extra, tablero y alertas.

Las reglas de estado están en `states.py` (funciones puras). Este módulo las aplica sobre los
repositorios. Lo que pertenece a las evaluaciones (diagnóstico, intentos, badge) se lee a través de
los puertos `ProgressReader` y `AssessmentHistory`, que implementa el dominio `assessments`.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

from pydantic import ValidationError

from app.common.constants import ConsentType, CourseStatus, RoleCode
from app.common.entities import require_id
from app.common.exceptions import (
    BusinessRuleError,
    ConflictError,
    InvalidStateTransitionError,
    NotFoundError,
)
from app.common.unit_of_work import UnitOfWork
from app.domains.ai_gateway.exceptions import AiResultInvalidError
from app.domains.ai_gateway.repository import AiServicePort
from app.domains.courses.entities import Course
from app.domains.identity.authentication import CurrentUser
from app.domains.learning_paths import exceptions as errors
from app.domains.learning_paths.contracts import LearningPathV1
from app.domains.learning_paths.entities import (
    Alert,
    AttemptGrant,
    Enrollment,
    LearningPath,
    PathStep,
    TopicNode,
)
from app.domains.learning_paths.repository import (
    AlertRepository,
    AttemptGrantRepository,
    EnrollmentRepository,
    PathRepository,
    PathStepRepository,
    PlatformReader,
)
from app.domains.learning_paths.states import (
    DONE_STEPS,
    RESEQUENCEABLE_STEPS,
    AlertType,
    EnrollmentStatus,
    NextAction,
    ProgressFacts,
    StepState,
    StepStatus,
    all_steps_done,
    check_enrollment_transition,
    check_step_transition,
    is_closed,
    next_action,
    refresh_availability,
)

PATH_SEQUENCE_TASK = "path.sequence"


# --- puertos que implementa el dominio de evaluaciones ----------------------------------------


class ProgressReader(Protocol):
    async def facts(self, enrollment: Enrollment, steps: list[PathStep]) -> ProgressFacts:
        """Diagnóstico, intentos abiertos o calificándose, final y encuesta de la inscripción."""
        ...


@dataclass(frozen=True)
class AttemptSummary:
    id: int
    assessment_type: str
    path_step_id: int | None
    attempt_number: int
    status: str
    score: float | None
    passed: bool | None
    uses_extra_grant: bool
    submitted_at: datetime | None


@dataclass(frozen=True)
class LearnerHistory:
    level_by_topic: list[dict[str, Any]] = field(default_factory=list)
    attempts: list[AttemptSummary] = field(default_factory=list)


class AssessmentHistory(Protocol):
    async def history(self, enrollment_id: int) -> LearnerHistory: ...


# --- vistas ------------------------------------------------------------------------------------


@dataclass(frozen=True)
class EnrollmentView:
    enrollment: Enrollment
    path: LearningPath
    steps: list[PathStep]
    next_action: NextAction

    @property
    def progress(self) -> tuple[int, int, int]:
        """(pasos completados, total, porcentaje). Completado = `passed` o `skipped`."""
        total = len(self.steps)
        done = sum(1 for s in self.steps if s.status in DONE_STEPS)
        return done, total, round(100 * done / total) if total else 0


@dataclass(frozen=True)
class PathCard:
    path: LearningPath
    course: Course
    topics: list[TopicNode]
    enrolled: bool


@dataclass(frozen=True)
class StepView:
    step: PathStep
    topic: TopicNode | None


@dataclass(frozen=True)
class PathView:
    enrollment: Enrollment
    path: LearningPath
    steps: list[StepView]
    final_attempts_used: int
    final_attempts_max: int

    @property
    def final_locked(self) -> bool:
        return not self.steps or not all_steps_done(s.step.status for s in self.steps)

    @property
    def savings(self) -> tuple[int, int]:
        skipped = [s for s in self.steps if s.step.status == StepStatus.SKIPPED]
        minutes = sum((s.topic.estimated_minutes or 0) for s in skipped if s.topic is not None)
        return len(skipped), minutes


def _states(steps: list[PathStep]) -> list[StepState]:
    return [StepState(require_id(s), s.topic_id, s.step_order, s.status) for s in steps]


def is_staff_owner(user: CurrentUser, course: Course | None) -> bool:
    if course is None:
        return False
    if user.has_any_role(RoleCode.ADMIN):
        return True
    return user.has_any_role(RoleCode.INSTRUCTOR) and course.owner_user_id == user.id


# --- avance de la ruta -------------------------------------------------------------------------


class PathProgress:
    """Aplica la máquina de estados del paso y de la inscripción, y avisa al instructor."""

    def __init__(
        self,
        enrollments: EnrollmentRepository,
        steps: PathStepRepository,
        alerts: AlertRepository,
        reader: PlatformReader,
        ai: AiServicePort,
    ) -> None:
        self._enrollments = enrollments
        self._steps = steps
        self._alerts = alerts
        self._reader = reader
        self._ai = ai

    async def set_enrollment_status(
        self, enrollment: Enrollment, target: str, **changes: Any
    ) -> Enrollment:
        check_enrollment_transition(enrollment.status, target)
        updated = await self._enrollments.update(
            require_id(enrollment), {"status": target, **changes}
        )
        if updated is None:
            raise errors.enrollment_not_found(require_id(enrollment))
        return updated

    async def set_step_status(self, step: PathStep, target: str, **changes: Any) -> PathStep:
        check_step_transition(step.status, target)
        updated = await self._steps.update(require_id(step), {"status": target, **changes})
        if updated is None:
            raise errors.step_not_found(require_id(step))
        return updated

    async def refresh(self, enrollment: Enrollment, path: LearningPath) -> list[PathStep]:
        """Recalcula los pasos que esperan y, si todo está completo, habilita la final."""
        steps = await self._steps.list_for_enrollment(require_id(enrollment))
        nodes = await self._reader.topic_nodes(path.course_id)
        prerequisites = {n.id: n.prerequisites for n in nodes}
        by_id = {require_id(s): s for s in steps}
        for step_id, target in refresh_availability(_states(steps), prerequisites).items():
            await self.set_step_status(by_id[step_id], target)
        steps = await self._steps.list_for_enrollment(require_id(enrollment))
        if (
            enrollment.status == EnrollmentStatus.IN_PATH
            and steps
            and all_steps_done(s.status for s in steps)
        ):
            await self.set_enrollment_status(enrollment, EnrollmentStatus.FINAL_READY)
        return steps

    async def sequence(
        self,
        enrollment: Enrollment,
        path: LearningPath,
        levels: dict[int, float],
        focus_topic_ids: list[int],
    ) -> LearningPathV1:
        """`path.sequence` (síncrono, sin LLM): orden, estado y motivo de cada tema."""
        nodes = await self._reader.topic_nodes(path.course_id)
        if not nodes:
            raise BusinessRuleError("The learning path has no topics.")
        known = {n.id for n in nodes}
        payload = {
            "topics": [
                {
                    "topic_id": str(n.id),
                    "position": max(n.position, 0),
                    "prerequisites": [str(p) for p in n.prerequisites],
                    "is_mandatory": n.is_mandatory,
                }
                for n in nodes
            ],
            "level_by_topic": [
                {"topic_id": str(t), "level": round(min(max(level, 0.0), 100.0), 2)}
                for t, level in levels.items()
                if t in known
            ],
            "mastery_skip_threshold": path.mastery_skip_threshold,
            "focus_topic_ids": [str(t) for t in focus_topic_ids if t in known],
            "pilot_arm": enrollment.pilot_arm or "personalized",
        }
        raw = await self._ai.run_task(PATH_SEQUENCE_TASK, payload)
        try:
            result = LearningPathV1.model_validate(raw)
        except ValidationError as exc:
            raise AiResultInvalidError("path.sequence") from exc
        if {int(s.topic_id) for s in result.steps if s.topic_id.isdigit()} != known:
            raise AiResultInvalidError("path.sequence")
        return result

    async def create_steps(
        self, enrollment: Enrollment, path: LearningPath, sequenced: LearningPathV1
    ) -> list[PathStep]:
        for step in sequenced.steps:
            await self._steps.add(
                PathStep(
                    enrollment_id=require_id(enrollment),
                    topic_id=int(step.topic_id),
                    step_order=step.step_order,
                    status=step.status,
                    inclusion_reason=step.inclusion_reason,
                    diagnostic_level=step.diagnostic_level,
                )
            )
        return await self.refresh(enrollment, path)

    async def resequence(
        self, enrollment: Enrollment, path: LearningPath, sequenced: LearningPathV1
    ) -> list[PathStep]:
        """Recalcula los pasos aún no empezados (E15). Lo ya cursado no cambia."""
        by_topic = {
            s.topic_id: s for s in await self._steps.list_for_enrollment(require_id(enrollment))
        }
        for new in sequenced.steps:
            current = by_topic.get(int(new.topic_id))
            if current is None:
                await self._steps.add(
                    PathStep(
                        enrollment_id=require_id(enrollment),
                        topic_id=int(new.topic_id),
                        step_order=new.step_order,
                        status=new.status,
                        inclusion_reason=new.inclusion_reason,
                        diagnostic_level=new.diagnostic_level,
                    )
                )
                continue
            changes: dict[str, Any] = {"diagnostic_level": new.diagnostic_level}
            if current.status in RESEQUENCEABLE_STEPS and current.attempts_used == 0:
                changes |= {"status": new.status, "inclusion_reason": new.inclusion_reason}
            await self._steps.update(require_id(current), changes)
        return await self.refresh(enrollment, path)

    async def apply_topic_result(
        self,
        enrollment: Enrollment,
        path: LearningPath,
        step: PathStep,
        *,
        score: float,
        passed: bool,
    ) -> list[PathStep]:
        """Resultado de un quiz: aprueba, sigue o agota los intentos (con alerta)."""
        best = score if step.best_score is None else max(step.best_score, score)
        if passed:
            await self.set_step_status(step, StepStatus.PASSED, last_score=score, best_score=best)
        elif step.remaining_attempts(path.max_attempts) <= 0:
            exhausted = await self.set_step_status(
                step, StepStatus.ATTEMPTS_EXHAUSTED, last_score=score, best_score=best
            )
            await self.alert(
                path, AlertType.TOPIC_ATTEMPTS_EXHAUSTED, enrollment, require_id(exhausted)
            )
        else:
            await self.set_step_status(
                step, StepStatus.IN_PROGRESS, last_score=score, best_score=best
            )
        return await self.refresh(enrollment, path)

    async def alert(
        self,
        path: LearningPath,
        alert_type: str,
        enrollment: Enrollment,
        path_step_id: int | None = None,
    ) -> Alert | None:
        """Crea la alerta para el dueño del curso (o un administrador si está «Sin asignar»)."""
        course = await self._reader.course(path.course_id)
        recipient = course.owner_user_id if course is not None else None
        if recipient is None:
            recipient = await self._reader.first_admin_id()
        if recipient is None:
            return None
        return await self._alerts.add(
            Alert(
                recipient_user_id=recipient,
                alert_type=alert_type,
                enrollment_id=require_id(enrollment),
                path_step_id=path_step_id,
            )
        )


# --- catálogo e inscripciones -----------------------------------------------------------------


class EnrollmentService:
    def __init__(
        self,
        paths: PathRepository,
        enrollments: EnrollmentRepository,
        steps: PathStepRepository,
        reader: PlatformReader,
        progress: ProgressReader,
        uow: UnitOfWork,
    ) -> None:
        self._paths = paths
        self._enrollments = enrollments
        self._steps = steps
        self._reader = reader
        self._progress = progress
        self._uow = uow

    async def catalog(self, user_id: int, *, limit: int, offset: int) -> tuple[list[PathCard], int]:
        paths, total = await self._paths.list_published(limit=limit, offset=offset)
        cards: list[PathCard] = []
        for path in paths:
            course = await self._reader.course(path.course_id)
            if course is None:
                continue
            cards.append(
                PathCard(
                    path=path,
                    course=course,
                    topics=await self._reader.topic_nodes(path.course_id),
                    enrolled=await self._enrollments.find(user_id, require_id(path)) is not None,
                )
            )
        return cards, total

    async def enroll(
        self, user_id: int, learning_path_id: int, *, analysis: bool = True
    ) -> EnrollmentView:
        """Inscribe al aprendiz (CU-17: exige el consentimiento de datos vigente)."""
        if not await self._reader.consent_in_force(user_id, ConsentType.DATA_PROCESSING):
            raise errors.consent_required()
        path = await self._paths.get(learning_path_id)
        if path is None or not path.active or path.status != "published":
            raise errors.path_not_published()
        course = await self._reader.course(path.course_id)
        if course is None or not course.active or course.status == CourseStatus.ARCHIVED:
            raise errors.path_not_published()
        if await self._enrollments.find(user_id, learning_path_id) is not None:
            raise ConflictError(
                "The learner already has an enrollment in this learning path.",
                code="ENROLLMENT_ALREADY_EXISTS",
            )
        profile = await self._reader.profile(user_id)
        has_description = profile is not None and profile.has_description
        target = EnrollmentStatus.DIAGNOSING if has_description else EnrollmentStatus.PROFILING
        check_enrollment_transition(EnrollmentStatus.ENROLLED, target)
        pilot_consent = await self._reader.consent_in_force(user_id, ConsentType.PILOT_RESEARCH)
        # Después del sorteo, quien entra con consentimiento del piloto recibe brazo (y entra al
        # análisis); sin piloto sorteado, el análisis depende solo del consentimiento.
        arm = (
            await self._reader.pilot_arm_for_new_enrollment(learning_path_id)
            if analysis and pilot_consent
            else None
        )
        has_pilot = await self._reader.pilot_running(learning_path_id) or arm is not None
        created = await self._enrollments.add(
            Enrollment(
                user_id=user_id,
                learning_path_id=learning_path_id,
                status=target,
                profile_description=profile.description if profile is not None else None,
                pilot_arm=arm,
                analysis_included=analysis and pilot_consent and (arm is not None or not has_pilot),
            )
        )
        await self._uow.commit()
        return await self._view(created, path)

    async def get_own(self, user: CurrentUser, enrollment_id: int) -> Enrollment:
        enrollment = await self._enrollments.get(enrollment_id)
        if enrollment is None or enrollment.user_id != user.id or not enrollment.active:
            raise errors.enrollment_not_found(enrollment_id)
        return enrollment

    async def view(self, user: CurrentUser, enrollment_id: int) -> EnrollmentView:
        enrollment = await self.get_own(user, enrollment_id)
        return await self._view(enrollment)

    async def list_own(
        self, user: CurrentUser, *, limit: int, offset: int
    ) -> tuple[list[EnrollmentView], int]:
        items, total = await self._enrollments.list_for_user(user.id, limit=limit, offset=offset)
        return [await self._view(e) for e in items], total

    async def path_view(
        self, user: CurrentUser, enrollment_id: int, final_used: int, final_max: int
    ) -> PathView:
        enrollment = await self.get_own(user, enrollment_id)
        path = await self._path_of(enrollment)
        nodes = {n.id: n for n in await self._reader.topic_nodes(path.course_id)}
        steps = await self._steps.list_for_enrollment(enrollment_id)
        return PathView(
            enrollment=enrollment,
            path=path,
            steps=[StepView(s, nodes.get(s.topic_id)) for s in steps],
            final_attempts_used=final_used,
            final_attempts_max=final_max,
        )

    async def _path_of(self, enrollment: Enrollment) -> LearningPath:
        path = await self._paths.get(enrollment.learning_path_id)
        if path is None:
            raise errors.path_not_found(enrollment.learning_path_id)
        return path

    async def _view(
        self, enrollment: Enrollment, path: LearningPath | None = None
    ) -> EnrollmentView:
        path = path or await self._path_of(enrollment)
        steps = await self._steps.list_for_enrollment(require_id(enrollment))
        facts = await self._progress.facts(enrollment, steps)
        return EnrollmentView(enrollment, path, steps, next_action(facts))

    async def view_of(self, enrollment: Enrollment) -> EnrollmentView:
        return await self._view(enrollment)

    # --- administración (AD5) ---------------------------------------------------------------

    async def admin_search(
        self, *, learning_path_id: int | None, status: str | None, limit: int, offset: int
    ) -> tuple[list[EnrollmentView], int]:
        items, total = await self._enrollments.search(
            learning_path_id=learning_path_id, status=status, limit=limit, offset=offset
        )
        return [await self._view(e) for e in items], total

    async def admin_enroll(self, user_id: int, learning_path_id: int) -> EnrollmentView:
        if await self._reader.user(user_id) is None:
            raise NotFoundError("User", user_id, code="USER_NOT_FOUND")
        return await self.enroll(user_id, learning_path_id)

    async def withdraw(self, enrollment_id: int) -> EnrollmentView:
        """Retira la inscripción (no se borra) y la saca del análisis."""
        enrollment = await self._enrollments.get_for_update(enrollment_id)
        if enrollment is None or not enrollment.active:
            raise errors.enrollment_not_found(enrollment_id)
        if is_closed(enrollment.status):
            raise errors.enrollment_closed()
        check_enrollment_transition(enrollment.status, EnrollmentStatus.WITHDRAWN)
        updated = await self._enrollments.update(
            enrollment_id, {"status": EnrollmentStatus.WITHDRAWN, "analysis_included": False}
        )
        await self._uow.commit()
        assert updated is not None  # noqa: S101  (la fila está bloqueada)
        return await self._view(updated)

    async def move(self, enrollment_id: int, learning_path_id: int) -> EnrollmentView:
        """Mueve al aprendiz a otra ruta: retira la actual y crea otra, ambas fuera del análisis."""
        enrollment = await self._enrollments.get_for_update(enrollment_id)
        if enrollment is None or not enrollment.active:
            raise errors.enrollment_not_found(enrollment_id)
        if is_closed(enrollment.status):
            raise errors.enrollment_closed()
        if enrollment.learning_path_id == learning_path_id:
            raise ConflictError("The enrollment is already in that learning path.")
        target = await self._paths.get(learning_path_id)
        if target is None or not target.active or target.status != "published":
            raise errors.path_not_published()
        if await self._enrollments.find(enrollment.user_id, learning_path_id) is not None:
            raise ConflictError(
                "The learner already has an enrollment in the target learning path.",
                code="ENROLLMENT_ALREADY_EXISTS",
            )
        check_enrollment_transition(enrollment.status, EnrollmentStatus.WITHDRAWN)
        await self._enrollments.update(
            enrollment_id, {"status": EnrollmentStatus.WITHDRAWN, "analysis_included": False}
        )
        profile = await self._reader.profile(enrollment.user_id)
        has_description = profile is not None and profile.has_description
        moved = await self._enrollments.add(
            Enrollment(
                user_id=enrollment.user_id,
                learning_path_id=learning_path_id,
                status=(
                    EnrollmentStatus.DIAGNOSING if has_description else EnrollmentStatus.PROFILING
                ),
                profile_description=profile.description if profile is not None else None,
                pilot_arm=None,
                analysis_included=False,
            )
        )
        await self._uow.commit()
        return await self._view(moved, target)


# --- instructor: ajustes, tablero, detalle, intentos extra y alertas ---------------------------


@dataclass(frozen=True)
class DashboardRow:
    enrollment: Enrollment
    full_name: str
    steps: list[PathStep]


@dataclass(frozen=True)
class Dashboard:
    path: LearningPath
    topics: list[TopicNode]
    rows: list[DashboardRow]
    pilot_running: bool = False


@dataclass(frozen=True)
class LearnerDetail:
    enrollment: Enrollment
    path: LearningPath
    full_name: str
    profile: dict[str, Any]
    steps: list[StepView]
    history: LearnerHistory
    final_attempts_granted: int


SETTINGS_FIELDS = (
    "topic_pass_threshold",
    "final_pass_threshold",
    "mastery_skip_threshold",
    "max_attempts",
    "short_answer_min_ratio",
    "level_weights",
    "default_objective_bloom_verb",
    "default_objective_content",
    "default_objective_criterion",
)


class PathStaffService:
    def __init__(
        self,
        paths: PathRepository,
        enrollments: EnrollmentRepository,
        steps: PathStepRepository,
        grants: AttemptGrantRepository,
        alerts: AlertRepository,
        reader: PlatformReader,
        progress: PathProgress,
        history: AssessmentHistory,
        uow: UnitOfWork,
    ) -> None:
        self._paths = paths
        self._enrollments = enrollments
        self._steps = steps
        self._grants = grants
        self._alerts = alerts
        self._reader = reader
        self._progress = progress
        self._history = history
        self._uow = uow

    async def owned_path(self, user: CurrentUser, path_id: int) -> LearningPath:
        """La ruta si es de un curso del instructor (o el usuario es admin); si no, 404."""
        path = await self._paths.get(path_id)
        if path is None or not is_staff_owner(user, await self._reader.course(path.course_id)):
            raise errors.path_not_found(path_id)
        return path

    async def update_settings(
        self, user: CurrentUser, path_id: int, changes: dict[str, Any], *, confirm_pilot: bool
    ) -> LearningPath:
        """Umbrales y objetivo por defecto (D3b). Con el piloto en curso pide confirmación."""
        path = await self.owned_path(user, path_id)
        values = {k: v for k, v in changes.items() if k in SETTINGS_FIELDS}
        if not values:
            return path
        if "level_weights" in values:
            weights = values["level_weights"]
            if abs(sum(float(weights.get(k, 0)) for k in ("test", "profile", "resume")) - 1) > 0.01:
                raise BusinessRuleError("level_weights must add up to 1.", code="VALIDATION_ERROR")
        if not confirm_pilot and await self._reader.pilot_running(path_id):
            raise ConflictError(
                "A pilot is running: changing the settings breaks the comparison. "
                "Send confirm_pilot_change=true to apply it anyway.",
                code="PILOT_RUNNING",
            )
        updated = await self._paths.update(path_id, values)
        await self._uow.commit()
        assert updated is not None  # noqa: S101
        return updated

    async def dashboard(self, user: CurrentUser, path_id: int) -> Dashboard:
        path = await self.owned_path(user, path_id)
        enrollments = await self._enrollments.list_for_path(path_id)
        steps = await self._steps.list_for_enrollments([require_id(e) for e in enrollments])
        by_enrollment: dict[int, list[PathStep]] = defaultdict(list)
        for step in steps:
            by_enrollment[step.enrollment_id].append(step)
        rows: list[DashboardRow] = []
        for enrollment in enrollments:
            learner = await self._reader.user(enrollment.user_id)
            rows.append(
                DashboardRow(
                    enrollment,
                    learner.full_name if learner is not None else "",
                    by_enrollment.get(require_id(enrollment), []),
                )
            )
        return Dashboard(
            path,
            await self._reader.topic_nodes(path.course_id),
            rows,
            pilot_running=await self._reader.pilot_running(path_id),
        )

    async def _owned_enrollment(
        self, user: CurrentUser, path_id: int, enrollment_id: int
    ) -> tuple[LearningPath, Enrollment]:
        path = await self.owned_path(user, path_id)
        enrollment = await self._enrollments.get(enrollment_id)
        if enrollment is None or enrollment.learning_path_id != path_id:
            raise errors.enrollment_not_found(enrollment_id)
        return path, enrollment

    async def learner_detail(
        self, user: CurrentUser, path_id: int, enrollment_id: int
    ) -> LearnerDetail:
        """Perfil reducido (A3c: sin correo ni descripción libre), niveles e intentos (D4)."""
        path, enrollment = await self._owned_enrollment(user, path_id, enrollment_id)
        learner = await self._reader.user(enrollment.user_id)
        profile = await self._reader.profile(enrollment.user_id)
        nodes = {n.id: n for n in await self._reader.topic_nodes(path.course_id)}
        steps = await self._steps.list_for_enrollment(enrollment_id)
        return LearnerDetail(
            enrollment=enrollment,
            path=path,
            full_name=learner.full_name if learner is not None else "",
            profile={
                "education_level": profile.education_level if profile else None,
                "experience_band": profile.experience_band if profile else None,
                "job_title": profile.job_title if profile else None,
            },
            steps=[StepView(s, nodes.get(s.topic_id)) for s in steps],
            history=await self._history.history(enrollment_id),
            final_attempts_granted=await self._grants.final_attempts_granted(enrollment_id),
        )

    async def grant_step_attempts(
        self, user: CurrentUser, step_id: int, attempts: int, note: str | None
    ) -> AttemptGrant:
        """Intentos extra de un tema (CU-26): se reportan aparte de los de la regla."""
        step = await self._steps.get(step_id)
        enrollment = (
            await self._enrollments.get_for_update(step.enrollment_id) if step is not None else None
        )
        path = (
            await self._paths.get(enrollment.learning_path_id) if enrollment is not None else None
        )
        if (
            step is None
            or enrollment is None
            or path is None
            or not is_staff_owner(user, await self._reader.course(path.course_id))
        ):
            raise errors.step_not_found(step_id)
        if is_closed(enrollment.status):
            raise errors.enrollment_closed()
        if step.status in DONE_STEPS:
            raise InvalidStateTransitionError("The step is already passed or skipped.")
        grant = await self._grants.add(
            AttemptGrant(
                path_step_id=step_id,
                granted_by_user_id=user.id,
                attempts=attempts,
                note=note,
            )
        )
        changes = {"extra_attempts_granted": step.extra_attempts_granted + attempts}
        if step.status == StepStatus.ATTEMPTS_EXHAUSTED:
            await self._progress.set_step_status(step, StepStatus.IN_PROGRESS, **changes)
        else:
            await self._steps.update(step_id, changes)
        await self._progress.refresh(enrollment, path)
        await self._uow.commit()
        return grant

    async def grant_final_attempts(
        self, user: CurrentUser, enrollment_id: int, attempts: int, note: str | None
    ) -> AttemptGrant:
        enrollment = await self._enrollments.get(enrollment_id)
        path = (
            await self._paths.get(enrollment.learning_path_id) if enrollment is not None else None
        )
        if (
            enrollment is None
            or path is None
            or not is_staff_owner(user, await self._reader.course(path.course_id))
        ):
            raise errors.enrollment_not_found(enrollment_id)
        if is_closed(enrollment.status):
            raise errors.enrollment_closed()
        grant = await self._grants.add(
            AttemptGrant(
                enrollment_id=enrollment_id,
                granted_by_user_id=user.id,
                attempts=attempts,
                note=note,
            )
        )
        await self._uow.commit()
        return grant

    async def alerts(
        self, user: CurrentUser, *, unread: bool | None, limit: int, offset: int
    ) -> tuple[list[Alert], int]:
        return await self._alerts.list_for_recipient(
            user.id, unread=unread, limit=limit, offset=offset
        )

    async def mark_read(self, user: CurrentUser, alert_id: int) -> Alert:
        alert = await self._alerts.get(alert_id)
        if alert is None or alert.recipient_user_id != user.id or not alert.active:
            raise NotFoundError("Alert", alert_id)
        if alert.read_at is not None:
            return alert
        updated = await self._alerts.update(alert_id, {"read_at": datetime.now(UTC)})
        await self._uow.commit()
        assert updated is not None  # noqa: S101
        return updated
