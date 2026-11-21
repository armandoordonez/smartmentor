"""Casos de uso del piloto (AD4, AD4b): configuración, sorteo con semilla, inicio y preparación.

Reglas (plan 5.3.4):

- La asignación al piloto solo incluye a quien tiene la autorización `pilot_research` vigente.
- El sorteo con semilla es reproducible (misma semilla, mismos brazos) y solo se puede repetir
  antes de iniciar el piloto.
- Iniciar exige que `readiness` no tenga pendientes.
"""

import random
import secrets
from dataclasses import dataclass
from datetime import date
from typing import Any

from app.common.entities import require_id
from app.common.exceptions import (
    BusinessRuleError,
    ConflictError,
    NotFoundError,
)
from app.common.unit_of_work import UnitOfWork
from app.domains.ai_gateway.repository import AiServicePort
from app.domains.courses.repository import PrerequisiteRepository, TopicRepository
from app.domains.pilot.constants import MIN_PARTICIPANTS, PilotArm, PilotStatus
from app.domains.pilot.entities import PathSummary, Pilot
from app.domains.pilot.repository import PilotPopulation, PilotRepository

_EDITABLE = frozenset({PilotStatus.DRAFT, PilotStatus.RANDOMIZED})


@dataclass(frozen=True)
class PilotConfig:
    learning_path_id: int
    starts_on: date
    ends_on: date
    delayed_posttest_on: date | None
    random_seed: int | None


@dataclass(frozen=True)
class PilotView:
    pilot: Pilot
    arms: dict[str, int]
    path: PathSummary | None = None


@dataclass(frozen=True)
class Readiness:
    ready: bool
    missing: list[str]
    # Lo que AD4 muestra junto a la lista de pendientes (aditivo, 2026-11-12).
    consents_accepted: int = 0
    consents_total: int = 0
    topics_total: int = 0
    topics_with_items: int = 0
    topics_with_equivalent_items: int = 0


@dataclass(frozen=True)
class Randomization:
    personalized: int
    fixed: int
    skipped_without_consent: int
    random_seed: int


def _check_dates(config: PilotConfig) -> None:
    if config.ends_on < config.starts_on:
        raise BusinessRuleError("ends_on must not be before starts_on.", code="VALIDATION_ERROR")
    if (
        config.delayed_posttest_on is not None
        and config.ends_on is not None
        and config.delayed_posttest_on < config.ends_on
    ):
        raise BusinessRuleError(
            "The delayed post-test must not be before the end of the pilot.",
            code="VALIDATION_ERROR",
        )


def split_arms(enrollment_ids: list[int], seed: int) -> dict[int, str]:
    """Reparto reproducible: se ordena, se baraja con la semilla y la mitad va a cada brazo."""
    ordered = sorted(enrollment_ids)
    random.Random(seed).shuffle(ordered)  # noqa: S311  (sorteo reproducible, no criptográfico)
    cut = (len(ordered) + 1) // 2
    return {
        enrollment_id: (PilotArm.PERSONALIZED if n < cut else PilotArm.FIXED).value
        for n, enrollment_id in enumerate(ordered)
    }


class PilotService:
    def __init__(
        self,
        pilots: PilotRepository,
        population: PilotPopulation,
        topics: TopicRepository,
        prerequisites: PrerequisiteRepository,
        ai: AiServicePort,
        uow: UnitOfWork,
    ) -> None:
        self._pilots = pilots
        self._population = population
        self._topics = topics
        self._prerequisites = prerequisites
        self._ai = ai
        self._uow = uow

    async def _load(self, pilot_id: int) -> Pilot:
        pilot = await self._pilots.get(pilot_id)
        if pilot is None or not pilot.active:
            raise NotFoundError("Pilot", pilot_id, code="PILOT_NOT_FOUND")
        return pilot

    async def _view(self, pilot: Pilot) -> PilotView:
        path_id = pilot.learning_path_id
        return PilotView(
            pilot,
            await self._population.arm_counts(path_id),
            await self._population.path_summary(path_id),
        )

    async def create(self, config: PilotConfig) -> PilotView:
        _check_dates(config)
        if await self._population.path_course(config.learning_path_id) is None:
            raise NotFoundError("Learning path", config.learning_path_id)
        if await self._pilots.open_for_path(config.learning_path_id, excluding=None) is not None:
            raise ConflictError("The learning path already has a pilot that is not closed.")
        created = await self._pilots.add(
            Pilot(
                learning_path_id=config.learning_path_id,
                starts_on=config.starts_on,
                ends_on=config.ends_on,
                delayed_posttest_on=config.delayed_posttest_on,
                random_seed=config.random_seed,
            )
        )
        await self._uow.commit()
        return await self._view(created)

    async def list_all(self, *, limit: int, offset: int) -> tuple[list[PilotView], int]:
        pilots, total = await self._pilots.list_all(limit=limit, offset=offset)
        return [await self._view(p) for p in pilots], total

    async def get(self, pilot_id: int) -> PilotView:
        return await self._view(await self._load(pilot_id))

    async def update(self, pilot_id: int, config: PilotConfig) -> PilotView:
        await self._load(pilot_id)
        pilot = await self._pilots.get_for_update(pilot_id) or await self._load(pilot_id)
        if pilot.status not in _EDITABLE:
            raise ConflictError(
                "The pilot already started; its configuration cannot change.",
                code="PILOT_ALREADY_STARTED",
            )
        _check_dates(config)
        if config.learning_path_id != pilot.learning_path_id:
            if await self._population.path_course(config.learning_path_id) is None:
                raise NotFoundError("Learning path", config.learning_path_id)
            if (
                await self._pilots.open_for_path(config.learning_path_id, excluding=pilot_id)
                is not None
            ):
                raise ConflictError("The learning path already has a pilot that is not closed.")
        changes: dict[str, Any] = {
            "learning_path_id": config.learning_path_id,
            "starts_on": config.starts_on,
            "ends_on": config.ends_on,
            "delayed_posttest_on": config.delayed_posttest_on,
            "random_seed": config.random_seed,
        }
        invalidates = pilot.status == PilotStatus.RANDOMIZED and (
            config.learning_path_id != pilot.learning_path_id
            or config.random_seed != pilot.random_seed
        )
        if invalidates:
            # Cambiar la ruta o la semilla anula el sorteo: hay que volver a sortear.
            await self._population.clear_arms(pilot.learning_path_id)
            changes["status"] = PilotStatus.DRAFT
        updated = await self._pilots.update(pilot_id, changes) or pilot
        await self._uow.commit()
        return await self._view(updated)

    async def randomize(self, pilot_id: int) -> Randomization:
        await self._load(pilot_id)
        pilot = await self._pilots.get_for_update(pilot_id) or await self._load(pilot_id)
        if pilot.status not in _EDITABLE:
            raise ConflictError(
                "The pilot already started; it cannot be randomized again.",
                code="PILOT_ALREADY_STARTED",
            )
        enrollments = await self._population.enrollments(pilot.learning_path_id)
        eligible = [e.enrollment_id for e in enrollments if e.consented]
        if enrollments and not eligible:
            raise BusinessRuleError(
                "No enrolled learner has the pilot research consent.",
                code="PILOT_CONSENT_REQUIRED",
            )
        seed = pilot.random_seed
        if seed is None:
            seed = secrets.randbelow(2**31)
        arms = split_arms(eligible, seed)
        await self._population.assign_arms(pilot.learning_path_id, arms)
        await self._pilots.update(pilot_id, {"status": PilotStatus.RANDOMIZED, "random_seed": seed})
        await self._uow.commit()
        counts = list(arms.values())
        return Randomization(
            personalized=counts.count(PilotArm.PERSONALIZED.value),
            fixed=counts.count(PilotArm.FIXED.value),
            skipped_without_consent=len(enrollments) - len(eligible),
            random_seed=seed,
        )

    async def readiness(self, pilot_id: int) -> Readiness:
        pilot = await self._load(pilot_id)
        return await self._readiness(pilot)

    async def _readiness(self, pilot: Pilot) -> Readiness:
        missing: list[str] = []
        if pilot.status == PilotStatus.DRAFT:
            missing.append("randomization")
        arms = await self._population.arm_counts(pilot.learning_path_id)
        if (
            arms.get(PilotArm.PERSONALIZED.value, 0) + arms.get(PilotArm.FIXED.value, 0)
            < MIN_PARTICIPANTS
            or not arms.get(PilotArm.PERSONALIZED.value)
            or not arms.get(PilotArm.FIXED.value)
        ):
            missing.append("min_consents")
        found = await self._population.path_course(pilot.learning_path_id)
        facts = await self._population.content_facts(found[0]) if found else None
        if facts is None or not facts.topic_ids:
            missing.append("topics")
        else:
            if (
                facts.topics_without_items
                or not facts.approved_diagnostic_items
                or not facts.approved_final_items
            ):
                missing.append("item_bank")
            if facts.topics_without_explanation:
                missing.append("approved_explanations")
            if facts.topics_without_video or facts.topics_without_backup:
                missing.append("video_backups")
        enrollments = await self._population.enrollments(pilot.learning_path_id)
        topics = set(facts.topic_ids) if facts is not None else set()
        without_items = set(facts.topics_without_items) if facts is not None else set()
        without_equivalents = set(facts.topics_without_equivalents) if facts is not None else set()
        return Readiness(
            ready=not missing,
            missing=missing,
            consents_accepted=sum(1 for e in enrollments if e.consented),
            consents_total=len(enrollments),
            topics_total=len(topics),
            topics_with_items=len(topics - without_items),
            topics_with_equivalent_items=len(topics - without_equivalents),
        )

    async def start(self, pilot_id: int) -> PilotView:
        await self._load(pilot_id)
        pilot = await self._pilots.get_for_update(pilot_id) or await self._load(pilot_id)
        if pilot.status in (PilotStatus.RUNNING, PilotStatus.CLOSED):
            raise ConflictError("The pilot already started.", code="PILOT_ALREADY_STARTED")
        readiness = await self._readiness(pilot)
        if not readiness.ready:
            raise BusinessRuleError(
                "The pilot is not ready to start.",
                code="PILOT_NOT_READY",
                extra={"missing": readiness.missing},
            )
        updated = await self._pilots.update(pilot_id, {"status": PilotStatus.RUNNING}) or pilot
        await self._uow.commit()
        return await self._view(updated)

    async def fixed_path_preview(self, pilot_id: int) -> dict[str, Any]:
        """La ruta fija (todos los temas en orden topológico) que verá el brazo de control."""
        pilot = await self._load(pilot_id)
        found = await self._population.path_course(pilot.learning_path_id)
        if found is None:
            raise NotFoundError("Learning path", pilot.learning_path_id)
        course_id, mastery_threshold = found
        topics = await self._topics.list_for_course(course_id)
        edges = await self._prerequisites.list_for_course(course_id)
        requires: dict[int, list[str]] = {}
        for edge in edges:
            requires.setdefault(edge.topic_id, []).append(str(edge.prerequisite_topic_id))
        result = await self._ai.run_task(
            "path.sequence",
            {
                "topics": [
                    {
                        "topic_id": str(require_id(t)),
                        "position": t.position,
                        "prerequisites": requires.get(require_id(t), []),
                        "is_mandatory": t.is_mandatory,
                    }
                    for t in topics
                ],
                "level_by_topic": [],
                "mastery_skip_threshold": mastery_threshold,
                "focus_topic_ids": [],
                "pilot_arm": PilotArm.FIXED.value,
            },
        )
        # Aditivo (2026-11-12): AD4b muestra el nombre de cada tema y el umbral de la final.
        names = {str(require_id(t)): t.name for t in topics}
        for step in result.get("steps") or []:
            step.setdefault("name", names.get(str(step.get("topic_id")), ""))
        summary = await self._population.path_summary(pilot.learning_path_id)
        if summary is not None:
            result.setdefault("final_pass_threshold", summary.final_pass_threshold)
        return result
