"""Ingesta de resultados por consulta: idempotencia, errores traducidos, propiedad y barrido."""

from copy import deepcopy
from typing import Any

import pytest

from app.common.exceptions import BadGatewayError, ServiceUnavailableError
from app.domains.ai_gateway.exceptions import AiJobNotFoundError
from app.domains.ai_gateway.fake import fake_syllabus
from app.domains.courses.syllabus_text import extract_from_text
from tests.unit.conftest import World

TEXT = "Tema 1 fundamentos. Tema 2 regresión lineal."


async def start(world: World, *, auto_complete: bool = True) -> tuple[int, str]:
    world.ai.auto_complete = auto_complete
    created = await world.course_service.create(
        world.instructor, name="ML", description=None, path_name=None, group_label=None
    )
    course_id = created.course.id or 0
    job = await world.syllabus_service.submit(world.instructor, course_id, extract_from_text(TEXT))
    return course_id, job.job_id


async def status_of(world: World, course_id: int) -> str:
    return (await world.course_service.get(world.instructor, course_id)).course.status


async def test_a_running_job_is_reported_without_touching_the_course(world: World) -> None:
    course_id, job_id = await start(world, auto_complete=False)
    view = await world.job_service.get(job_id, world.instructor)
    assert (view.status, view.ingested) == ("running", False)
    assert view.progress_label
    assert await status_of(world, course_id) == "extracting"


async def test_a_finished_job_is_ingested_in_the_same_request(world: World) -> None:
    course_id, job_id = await start(world)
    view = await world.job_service.get(job_id, world.instructor)
    assert (view.status, view.ingested) == ("succeeded", True)
    assert await status_of(world, course_id) == "in_review"
    extraction = await world.syllabus.current_extraction(course_id)
    assert extraction is not None
    assert extraction.raw_output is not None
    assert extraction.prompt_version == "syllabus_structuring v1"
    assert len(await world.topics.list_for_course(course_id)) == 3


async def test_ingestion_is_idempotent_when_the_job_is_polled_again(world: World) -> None:
    course_id, job_id = await start(world)
    first = await world.job_service.get(job_id, world.instructor)
    topics_after_first = {t.id for t in await world.topics.list_for_course(course_id)}
    second = await world.job_service.get(job_id, world.instructor)
    third = await world.job_service.get(job_id, world.admin)
    assert first.ingested and second.ingested and third.ingested
    assert {t.id for t in await world.topics.list_for_course(course_id)} == topics_after_first
    assert len(world.outcomes.items) == 3  # un resultado por tema, sin duplicados
    assert len(world.prerequisites.items) == 3  # (lineal→fund), (log→fund), (log→lineal)


async def test_the_sweep_ingests_what_nobody_asked_for_and_then_finds_nothing(
    world: World,
) -> None:
    course_id, _ = await start(world)
    pending = await world.job_service.pending()
    assert len(pending) == 1
    await world.job_service.sweep_one(pending[0])
    assert await status_of(world, course_id) == "in_review"
    assert await world.job_service.pending() == []


async def test_the_sweep_ingests_a_finished_publication(world: World) -> None:
    course_id, job_id = await start(world)
    await world.job_service.get(job_id, world.instructor)
    job = await world.publication_service.publish(world.instructor, course_id)
    # El fake terminó al instante, pero nadie lo consultó: el curso sigue generando.
    assert await status_of(world, course_id) == "generating_content"
    pending = await world.job_service.pending()
    assert [p.job_id for p in pending] == [job.job_id]
    await world.job_service.sweep_one(pending[0])
    assert await status_of(world, course_id) == "published"
    path = await world.paths.get_by_course(course_id)
    assert path is not None
    assert path.status == "published"
    assert await world.job_service.pending() == []


async def test_a_failed_job_becomes_502_and_leaves_the_course_recoverable(world: World) -> None:
    world.ai.fail_next("syllabus.structure", code="INVALID_OUTPUT", retryable=True)
    course_id, job_id = await start(world)
    with pytest.raises(BadGatewayError) as error:
        await world.job_service.get(job_id, world.instructor)
    assert error.value.code == "AI_TASK_FAILED"
    assert error.value.status_code == 502
    assert error.value.extra == {"job_id": job_id, "retryable": True}
    course = (await world.course_service.get(world.instructor, course_id)).course
    assert course.status == "extraction_failed"
    assert course.extraction_error_code == "INVALID_OUTPUT"
    # Se puede subir otro syllabus desde extraction_failed.
    again = await world.syllabus_service.submit(
        world.instructor, course_id, extract_from_text(TEXT + " nuevo")
    )
    assert (await world.job_service.get(again.job_id, world.instructor)).ingested


async def test_a_non_retryable_failure_says_so(world: World) -> None:
    world.ai.fail_next("syllabus.structure", code="SYLLABUS_NO_TOPICS", retryable=False)
    _, job_id = await start(world)
    with pytest.raises(BadGatewayError) as error:
        await world.job_service.get(job_id, world.instructor)
    assert error.value.extra["retryable"] is False


async def test_budget_exceeded_is_a_503(world: World) -> None:
    world.ai.fail_next("syllabus.structure", code="BUDGET_EXCEEDED", retryable=False)
    _, job_id = await start(world)
    with pytest.raises(ServiceUnavailableError) as error:
        await world.job_service.get(job_id, world.instructor)
    assert error.value.code == "AI_BUDGET_EXCEEDED"
    assert error.value.status_code == 503


async def test_a_result_that_breaks_its_contract_is_502_and_nothing_is_written(
    world: World,
) -> None:
    def broken(input_: dict[str, Any]) -> dict[str, Any]:
        result = fake_syllabus(input_)
        del result["topics"][0]["learning_outcomes"]  # el contrato exige al menos uno
        return result

    world.ai.set_result("syllabus.structure", broken)
    course_id, job_id = await start(world)
    with pytest.raises(BadGatewayError) as error:
        await world.job_service.get(job_id, world.instructor)
    assert error.value.code == "AI_RESULT_INVALID"
    assert await world.topics.list_for_course(course_id) == []
    assert await status_of(world, course_id) == "extraction_failed"


@pytest.mark.parametrize(
    "mutation",
    [
        lambda s: s["topics"][1].__setitem__("prerequisites", ["no_existe"]),
        lambda s: s["topics"][0].__setitem__("prerequisites", ["fundamentals"]),
        lambda s: s["topics"][0].__setitem__("prerequisites", ["logistic_regression"]),
        lambda s: s["topics"][1].__setitem__("id", "fundamentals"),
    ],
    ids=["prerrequisito-desconocido", "autoprerrequisito", "ciclo", "clave-duplicada"],
)
async def test_a_syllabus_with_a_broken_graph_is_rejected_before_writing(
    world: World, mutation: Any
) -> None:
    def broken(input_: dict[str, Any]) -> dict[str, Any]:
        result = deepcopy(fake_syllabus(input_))
        mutation(result)
        return result

    world.ai.set_result("syllabus.structure", broken)
    course_id, job_id = await start(world)
    with pytest.raises(BadGatewayError) as error:
        await world.job_service.get(job_id, world.instructor)
    assert error.value.code == "AI_RESULT_INVALID"
    assert await world.topics.list_for_course(course_id) == []
    assert await status_of(world, course_id) == "extraction_failed"


async def test_a_publication_failure_returns_the_course_to_review(world: World) -> None:
    course_id, job_id = await start(world)
    await world.job_service.get(job_id, world.instructor)
    world.ai.auto_complete = False
    job = await world.publication_service.publish(world.instructor, course_id)
    world.ai.fail_next("course.generate_content", code="LLM_PROVIDER_ERROR")
    world.ai.complete(job.job_id)
    with pytest.raises(BadGatewayError):
        await world.job_service.get(job.job_id, world.instructor)
    assert await status_of(world, course_id) == "in_review"


async def test_a_job_of_someone_else_is_a_404_and_the_admin_sees_everything(world: World) -> None:
    _, job_id = await start(world, auto_complete=False)
    with pytest.raises(AiJobNotFoundError):
        await world.job_service.get(job_id, world.other_instructor)
    with pytest.raises(AiJobNotFoundError):
        await world.job_service.get(job_id, world.learner)
    assert (await world.job_service.get(job_id, world.admin)).job_id == job_id


async def test_an_unknown_job_is_a_404(world: World) -> None:
    with pytest.raises(AiJobNotFoundError) as error:
        await world.job_service.get("00000000-0000-4000-8000-000000000000", world.admin)
    assert error.value.code == "JOB_NOT_FOUND"


async def test_a_job_type_nobody_ingests_yet_is_visible_only_to_the_admin(world: World) -> None:
    ref = await world.ai.submit_job("items.review", {"items": []}, "items.review:test:1")
    view = await world.job_service.get(ref.job_id, world.admin)
    assert view.ingested is False
    with pytest.raises(AiJobNotFoundError):
        await world.job_service.get(ref.job_id, world.instructor)


async def test_the_sweep_survives_a_failed_job(world: World) -> None:
    world.ai.fail_next("syllabus.structure")
    course_id, _ = await start(world)
    for pending in await world.job_service.pending():
        await world.job_service.sweep_one(pending)  # no lanza
    assert await status_of(world, course_id) == "extraction_failed"
