"""Reglas del piloto sobre repositorios en memoria."""

from dataclasses import replace
from datetime import date
from typing import Any

import pytest

from app.common.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.domains.pilot.entities import ContentFacts, PathSummary, Pilot, PilotEnrollment
from app.domains.pilot.service import PilotConfig, PilotService, split_arms
from tests.unit.conftest import World
from tests.unit.fakes import InMemoryRepository


class InMemoryPilots(InMemoryRepository[Pilot]):
    async def get_for_update(self, pilot_id: int) -> Pilot | None:
        return await self.get(pilot_id)

    async def list_all(self, *, limit: int, offset: int) -> tuple[list[Pilot], int]:
        found = list(self.items.values())
        return found[offset : offset + limit], len(found)

    async def open_for_path(self, learning_path_id: int, *, excluding: int | None) -> Pilot | None:
        return next(
            (
                p
                for p in self.items.values()
                if p.learning_path_id == learning_path_id
                and p.status != "closed"
                and p.id != excluding
            ),
            None,
        )


class InMemoryPopulation:
    def __init__(self, enrollments: list[PilotEnrollment], facts: ContentFacts) -> None:
        self.rows = enrollments
        self.facts = facts
        self.arms: dict[int, str] = {}

    async def path_course(self, learning_path_id: int) -> tuple[int, float] | None:
        return (1, 80.0) if learning_path_id == 1 else None

    async def enrollments(self, learning_path_id: int) -> list[PilotEnrollment]:
        return self.rows

    async def assign_arms(self, learning_path_id: int, arms: dict[int, str]) -> None:
        self.arms = dict(arms)

    async def clear_arms(self, learning_path_id: int) -> None:
        self.arms = {}

    async def arm_counts(self, learning_path_id: int) -> dict[str, int]:
        counts: dict[str, int] = {}
        for arm in self.arms.values():
            counts[arm] = counts.get(arm, 0) + 1
        return counts

    async def content_facts(self, course_id: int) -> ContentFacts:
        return self.facts

    async def path_summary(self, learning_path_id: int) -> PathSummary | None:
        return PathSummary("Datos", "Piloto", 80.0) if learning_path_id == 1 else None


READY = ContentFacts(topic_ids=[1, 2], approved_diagnostic_items=3, approved_final_items=2)
CONFIG = PilotConfig(1, date(2026, 12, 1), date(2026, 12, 20), None, 5)


def build(
    world: World, enrollments: list[PilotEnrollment], facts: ContentFacts = READY
) -> tuple[PilotService, InMemoryPopulation, InMemoryPilots]:
    pilots, population = InMemoryPilots(), InMemoryPopulation(enrollments, facts)
    service = PilotService(
        pilots, population, world.topics, world.prerequisites, world.ai, world.uow
    )
    return service, population, pilots


def learners(consenting: int, other: int = 0) -> list[PilotEnrollment]:
    return [PilotEnrollment(n, n, n <= consenting) for n in range(1, consenting + other + 1)]


def test_the_split_is_reproducible_and_balanced() -> None:
    ids = list(range(1, 8))
    first = split_arms(ids, 7)
    assert split_arms(list(reversed(ids)), 7) == first
    values = list(first.values())
    assert (values.count("personalized"), values.count("fixed")) == (4, 3)
    assert any(split_arms(ids, seed) != first for seed in range(20))


async def test_creating_requires_the_path_and_a_single_open_pilot(world: World) -> None:
    service, _, _ = build(world, [])
    with pytest.raises(NotFoundError):
        await service.create(replace(CONFIG, learning_path_id=9))
    await service.create(CONFIG)
    with pytest.raises(ConflictError):
        await service.create(CONFIG)
    with pytest.raises(BusinessRuleError):
        await build(world, [])[0].create(replace(CONFIG, ends_on=date(2026, 11, 1)))
    with pytest.raises(BusinessRuleError):
        await build(world, [])[0].create(replace(CONFIG, delayed_posttest_on=date(2026, 12, 10)))


async def test_randomize_assigns_only_consenting_learners_and_generates_a_missing_seed(
    world: World,
) -> None:
    service, population, _ = build(world, learners(3, other=2))
    view = await service.create(replace(CONFIG, random_seed=None))
    pilot_id = view.pilot.id or 0
    result = await service.randomize(pilot_id)
    assert (result.personalized, result.fixed, result.skipped_without_consent) == (2, 1, 2)
    assert set(population.arms) == {1, 2, 3}
    assert (await service.get(pilot_id)).pilot.random_seed == result.random_seed
    again = await service.randomize(pilot_id)
    assert again.random_seed == result.random_seed


async def test_randomize_refuses_when_nobody_consented(world: World) -> None:
    service, _, _ = build(world, learners(0, other=2))
    pilot_id = (await service.create(CONFIG)).pilot.id or 0
    with pytest.raises(BusinessRuleError) as caught:
        await service.randomize(pilot_id)
    assert caught.value.code == "PILOT_CONSENT_REQUIRED"


async def test_readiness_names_what_is_missing_and_start_freezes_the_pilot(world: World) -> None:
    facts = ContentFacts(
        topic_ids=[1, 2],
        topics_without_explanation=[2],
        topics_without_items=[1],
        topics_without_video=[1],
        topics_without_equivalents=[1, 2],
    )
    service, _, pilots = build(world, learners(2), facts)
    pilot_id = (await service.create(CONFIG)).pilot.id or 0
    readiness = await service.readiness(pilot_id)
    # Lo que AD4 muestra junto a los pendientes: consentimientos y temas con ítems.
    assert (readiness.consents_accepted, readiness.consents_total) == (2, 2)
    assert (readiness.topics_with_items, readiness.topics_total) == (1, 2)
    # Ningún tema tiene versiones paralelas: no hay ítems equivalentes para Hake.
    assert readiness.topics_with_equivalent_items == 0
    missing = readiness.missing
    assert missing == [
        "randomization",
        "min_consents",
        "item_bank",
        "approved_explanations",
        "video_backups",
    ]
    with pytest.raises(BusinessRuleError) as not_ready:
        await service.start(pilot_id)
    assert not_ready.value.code == "PILOT_NOT_READY"
    assert not_ready.value.extra["missing"] == missing

    ready_service, _, ready_pilots = build(world, learners(2))
    ready_id = (await ready_service.create(CONFIG)).pilot.id or 0
    await ready_service.randomize(ready_id)
    assert (await ready_service.readiness(ready_id)).ready is True
    assert (await ready_service.start(ready_id)).pilot.status == "running"
    for call in (
        ready_service.start(ready_id),
        ready_service.randomize(ready_id),
        ready_service.update(ready_id, CONFIG),
    ):
        with pytest.raises(ConflictError) as frozen:
            await call
        assert frozen.value.code == "PILOT_ALREADY_STARTED"
    _ = (pilots, ready_pilots)


async def test_a_course_without_topics_is_not_ready(world: World) -> None:
    service, _, _ = build(world, learners(2), ContentFacts())
    pilot_id = (await service.create(CONFIG)).pilot.id or 0
    await service.randomize(pilot_id)
    assert (await service.readiness(pilot_id)).missing == ["topics"]


async def test_changing_the_path_or_seed_after_randomizing_clears_the_draw(world: World) -> None:
    service, population, _ = build(world, learners(2))
    pilot_id = (await service.create(CONFIG)).pilot.id or 0
    await service.randomize(pilot_id)
    assert population.arms
    same = await service.update(pilot_id, CONFIG)
    assert same.pilot.status == "randomized"
    assert population.arms
    changed = await service.update(pilot_id, replace(CONFIG, random_seed=99))
    assert changed.pilot.status == "draft"
    assert population.arms == {}


async def test_the_fixed_preview_sends_every_topic_with_the_fixed_arm(world: World) -> None:
    from app.common.entities import require_id
    from app.domains.courses.entities import Topic

    first = await world.topics.add(Topic(course_id=1, name="Uno", position=1))
    second = await world.topics.add(Topic(course_id=1, name="Dos", position=2, is_mandatory=True))
    await world.prerequisites.upsert(require_id(second), require_id(first), "llm")
    seen: dict[str, Any] = {}

    def sequence(input_: dict[str, Any]) -> dict[str, Any]:
        seen.update(input_)
        return {"steps": [{"step_order": 1, "topic_id": str(require_id(first))}]}

    world.ai.task_results["path.sequence"] = sequence
    service, _, _ = build(world, [])
    created = await service.create(CONFIG)
    pilot_id = created.pilot.id or 0
    assert created.path is not None and created.path.name == "Datos"
    preview = await service.fixed_path_preview(pilot_id)
    # Aditivo para AD4b: el nombre del tema y el umbral de la final.
    assert preview["steps"][0]["name"] == first.name
    assert preview["final_pass_threshold"] == 80.0
    assert seen["pilot_arm"] == "fixed"
    assert seen["topics"][1] == {
        "topic_id": str(require_id(second)),
        "position": 2,
        "prerequisites": [str(require_id(first))],
        "is_mandatory": True,
    }
    with pytest.raises(NotFoundError):
        await service.get(99)
