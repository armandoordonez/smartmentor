"""Casos de uso de cursos con repositorios en memoria y `FakeAiService`."""

import pytest

from app.common.exceptions import (
    BusinessRuleError,
    ConflictError,
    InvalidStateTransitionError,
    NotFoundError,
)
from app.domains.courses.service import OutcomeDraft, TopicDraft
from app.domains.courses.syllabus_text import extract_from_text
from tests.unit.conftest import INSTRUCTOR_ID, LEARNER_ID, World

SYLLABUS_TEXT = "Tema 1 fundamentos. Tema 2 regresión lineal. Tema 3 regresión logística."


async def new_course(world: World, name: str = "Machine Learning") -> int:
    view = await world.course_service.create(
        world.instructor,
        name=name,
        description="Curso base",
        path_name="Ruta base",
        group_label="Piloto 2026-2",
    )
    assert view.course.id is not None
    return view.course.id


async def course_in_review(world: World) -> int:
    course_id = await new_course(world)
    job = await world.syllabus_service.submit(
        world.instructor, course_id, extract_from_text(SYLLABUS_TEXT)
    )
    await world.job_service.get(job.job_id, world.instructor)
    return course_id


def draft(name: str, **kwargs: object) -> TopicDraft:
    outcomes = kwargs.pop("learning_outcomes", [OutcomeDraft("Explicar el tema", "understand")])
    return TopicDraft(name=name, learning_outcomes=outcomes, **kwargs)  # type: ignore[arg-type]


# --- cursos -----------------------------------------------------------------------------------


async def test_an_instructor_creates_a_course_and_owns_it_with_a_draft_path(world: World) -> None:
    view = await world.course_service.create(
        world.instructor, name="ML", description=None, path_name=None, group_label="Grupo A"
    )
    assert view.course.owner_user_id == INSTRUCTOR_ID
    assert view.course.status == "draft"
    assert view.learning_path is not None
    assert view.learning_path.name == "ML"  # por defecto, el nombre del curso
    assert view.learning_path.group_label == "Grupo A"
    assert view.learning_path.status == "draft"


async def test_a_course_created_by_a_pure_admin_is_unassigned(world: World) -> None:
    view = await world.course_service.create(
        world.admin, name="ML", description=None, path_name=None, group_label=None
    )
    assert view.course.owner_user_id is None


async def test_an_instructor_only_lists_their_own_courses(world: World) -> None:
    mine = await new_course(world, "Mío")
    await world.course_service.create(
        world.other_instructor, name="Ajeno", description=None, path_name=None, group_label=None
    )
    views, total = await world.course_service.list_courses(
        world.instructor, mine=False, status=None, limit=20, offset=0
    )
    assert total == 1
    assert views[0].course.id == mine


async def test_an_admin_lists_everything_or_only_the_ones_they_own(world: World) -> None:
    await new_course(world)
    await world.course_service.create(
        world.other_instructor, name="Ajeno", description=None, path_name=None, group_label=None
    )
    _, everything = await world.course_service.list_courses(
        world.admin, mine=False, status=None, limit=20, offset=0
    )
    _, owned = await world.course_service.list_courses(
        world.admin, mine=True, status=None, limit=20, offset=0
    )
    assert (everything, owned) == (2, 0)


async def test_another_instructors_course_is_a_404_not_a_403(world: World) -> None:
    course_id = await new_course(world)
    with pytest.raises(NotFoundError) as error:
        await world.course_service.get(world.other_instructor, course_id)
    assert error.value.code == "COURSE_NOT_FOUND"
    assert error.value.status_code == 404
    with pytest.raises(NotFoundError):
        await world.course_service.update(world.other_instructor, course_id, {"name": "Robado"})


async def test_the_admin_can_see_any_course(world: World) -> None:
    course_id = await new_course(world)
    assert (await world.course_service.get(world.admin, course_id)).course.id == course_id


async def test_assign_owner_requires_an_active_instructor(world: World) -> None:
    course_id = await new_course(world)
    updated = await world.course_service.assign_owner(world.admin, course_id, 3)
    assert updated.course.owner_user_id == 3
    for bad in (LEARNER_ID, 999):
        with pytest.raises(BusinessRuleError) as error:
            await world.course_service.assign_owner(world.admin, course_id, bad)
        assert error.value.code == "OWNER_NOT_FOUND"
    unassigned = await world.course_service.assign_owner(world.admin, course_id, None)
    assert unassigned.course.owner_user_id is None


# --- syllabus y extracción --------------------------------------------------------------------


async def test_uploading_a_syllabus_queues_a_job_and_marks_the_course_extracting(
    world: World,
) -> None:
    world.ai.auto_complete = False
    course_id = await new_course(world)
    job = await world.syllabus_service.submit(
        world.instructor, course_id, extract_from_text(SYLLABUS_TEXT)
    )
    course = (await world.course_service.get(world.instructor, course_id)).course
    assert course.status == "extracting"
    assert job.job_id in world.ai.jobs
    submitted = world.ai.submitted[0]
    assert submitted.job_type == "syllabus.structure"
    assert submitted.refs.course_id == course_id
    assert submitted.input == {"syllabus_document_id": 1}
    assert submitted.idempotency_key == "syllabus.structure:syllabus_document:1:v1"
    assert (
        await world.course_service.get(world.instructor, course_id)
    ).extraction_job_id == job.job_id


async def test_a_second_syllabus_while_extracting_is_a_conflict(world: World) -> None:
    world.ai.auto_complete = False
    course_id = await new_course(world)
    await world.syllabus_service.submit(
        world.instructor, course_id, extract_from_text(SYLLABUS_TEXT)
    )
    with pytest.raises(ConflictError) as error:
        await world.syllabus_service.submit(
            world.instructor, course_id, extract_from_text(SYLLABUS_TEXT + " otro")
        )
    assert error.value.code == "EXTRACTION_IN_PROGRESS"


async def test_nothing_is_queued_when_the_ai_service_is_down(world: World) -> None:
    world.ai.unavailable = True
    course_id = await new_course(world)
    with pytest.raises(Exception) as error:  # noqa: PT011  (AiServiceUnavailableError)
        await world.syllabus_service.submit(
            world.instructor, course_id, extract_from_text(SYLLABUS_TEXT)
        )
    assert getattr(error.value, "code", "") == "AI_SERVICE_UNAVAILABLE"
    assert world.ai.submitted == []
    assert (await world.course_service.get(world.instructor, course_id)).course.status == "draft"


async def test_re_extraction_asks_for_confirmation_when_there_is_a_review(world: World) -> None:
    course_id = await course_in_review(world)
    await world.topic_service.create(world.instructor, course_id, draft("Extra"))
    with pytest.raises(BusinessRuleError):
        await world.syllabus_service.re_extract(
            world.instructor, course_id, confirm_discard_review=False
        )
    job = await world.syllabus_service.re_extract(
        world.instructor, course_id, confirm_discard_review=True
    )
    assert world.ai.jobs[job.job_id].job_type == "syllabus.structure"
    # Nueva clave de idempotencia (otra versión), no el reintento de la anterior.
    keys = [s.idempotency_key for s in world.ai.submitted]
    assert keys == [
        "syllabus.structure:syllabus_document:1:v1",
        "syllabus.structure:syllabus_document:1:v2",
    ]


async def test_re_extraction_without_a_syllabus_is_a_state_error(world: World) -> None:
    course_id = await new_course(world)
    with pytest.raises(InvalidStateTransitionError):
        await world.syllabus_service.re_extract(
            world.instructor, course_id, confirm_discard_review=True
        )


async def test_re_extraction_replaces_the_topics_only_after_ingestion(world: World) -> None:
    course_id = await course_in_review(world)
    before = await world.topic_service.list_topics(world.instructor, course_id)
    assert [t.topic.name for t in before.topics] == [
        "Fundamentos",
        "Regresión lineal",
        "Regresión logística",
    ]
    world.ai.auto_complete = False
    job = await world.syllabus_service.re_extract(
        world.instructor, course_id, confirm_discard_review=True
    )
    # Mientras el trabajo corre, la revisión actual sigue intacta.
    assert len((await world.topic_service.list_topics(world.instructor, course_id)).topics) == 3
    world.ai.complete(job.job_id)
    await world.job_service.get(job.job_id, world.instructor)
    after = await world.topic_service.list_topics(world.instructor, course_id)
    assert len(after.topics) == 3
    assert {t.topic.id for t in after.topics}.isdisjoint({t.topic.id for t in before.topics})


# --- temas ------------------------------------------------------------------------------------


async def test_topics_from_the_extraction_have_outcomes_prerequisites_and_origin(
    world: World,
) -> None:
    course_id = await course_in_review(world)
    listing = await world.topic_service.list_topics(world.instructor, course_id)
    by_name = {t.topic.name: t for t in listing.topics}
    logistic = by_name["Regresión logística"]
    assert logistic.topic.origin == "llm"
    assert logistic.topic.review_status == "unchanged"
    assert logistic.topic.extraction_key == "logistic_regression"
    assert [o.code for o in logistic.learning_outcomes] == ["lo_logistic_regression_1"]
    assert sorted(logistic.prerequisite_topic_ids) == sorted(
        [by_name["Fundamentos"].topic.id or 0, by_name["Regresión lineal"].topic.id or 0]
    )
    assert listing.review_counts == {"unchanged": 3, "corrected": 0, "added": 0, "deleted": 0}


async def test_a_new_topic_is_marked_as_added_by_the_instructor(world: World) -> None:
    course_id = await course_in_review(world)
    first = (await world.topic_service.list_topics(world.instructor, course_id)).topics[0]
    created = await world.topic_service.create(
        world.instructor,
        course_id,
        draft("Árboles de decisión", prerequisite_topic_ids=[first.topic.id or 0]),
    )
    assert created.topic.origin == "instructor"
    assert created.topic.review_status == "added"
    assert created.topic.position == 4
    assert created.prerequisite_topic_ids == [first.topic.id]
    assert [o.code for o in created.learning_outcomes] == [f"lo_t{created.topic.id}_1"]


async def test_editing_an_llm_topic_marks_it_corrected_but_a_no_op_does_not(world: World) -> None:
    course_id = await course_in_review(world)
    first = (await world.topic_service.list_topics(world.instructor, course_id)).topics[0]
    same = TopicDraft(
        name=first.topic.name,
        description=first.topic.description,
        subtopics=[str(s) for s in first.topic.subtopics],
        estimated_minutes=first.topic.estimated_minutes,
        is_mandatory=first.topic.is_mandatory,
        bloom_level=first.topic.bloom_level,
        learning_outcomes=[
            OutcomeDraft(o.statement, o.bloom_level, o.id) for o in first.learning_outcomes
        ],
        prerequisite_topic_ids=first.prerequisite_topic_ids,
    )
    unchanged = await world.topic_service.update(world.instructor, first.topic.id or 0, same)
    assert unchanged.topic.review_status == "unchanged"
    renamed = await world.topic_service.update(
        world.instructor,
        first.topic.id or 0,
        TopicDraft(**{**same.__dict__, "name": "Fundamentos revisados"}),
    )
    assert renamed.topic.review_status == "corrected"
    assert renamed.topic.name == "Fundamentos revisados"


async def test_outcomes_are_created_updated_and_removed_in_one_operation(world: World) -> None:
    course_id = await course_in_review(world)
    first = (await world.topic_service.list_topics(world.instructor, course_id)).topics[0]
    kept = first.learning_outcomes[0]
    updated = await world.topic_service.update(
        world.instructor,
        first.topic.id or 0,
        draft(
            first.topic.name,
            learning_outcomes=[
                OutcomeDraft("Enunciado corregido", "apply", kept.id),
                OutcomeDraft("Un resultado nuevo", "analyze"),
            ],
        ),
    )
    statements = {o.statement for o in updated.learning_outcomes}
    assert statements == {"Enunciado corregido", "Un resultado nuevo"}
    only_new = await world.topic_service.update(
        world.instructor,
        first.topic.id or 0,
        draft(first.topic.name, learning_outcomes=[OutcomeDraft("Solo este", "apply")]),
    )
    assert [o.statement for o in only_new.learning_outcomes] == ["Solo este"]
    codes = [o.code for o in only_new.learning_outcomes]
    assert len(set(codes)) == len(codes)


async def test_an_outcome_of_another_topic_cannot_be_edited(world: World) -> None:
    course_id = await course_in_review(world)
    topics = (await world.topic_service.list_topics(world.instructor, course_id)).topics
    foreign = topics[1].learning_outcomes[0]
    with pytest.raises(BusinessRuleError) as error:
        await world.topic_service.update(
            world.instructor,
            topics[0].topic.id or 0,
            draft("x", learning_outcomes=[OutcomeDraft("robo", "apply", foreign.id)]),
        )
    assert error.value.code == "REFERENCE_NOT_FOUND"


async def test_a_prerequisite_cycle_is_rejected_with_the_cycle_in_the_detail(world: World) -> None:
    course_id = await course_in_review(world)
    topics = {
        t.topic.name: t
        for t in (await world.topic_service.list_topics(world.instructor, course_id)).topics
    }
    fundamentals = topics["Fundamentos"]
    linear = topics["Regresión lineal"]
    # Lineal ya requiere Fundamentos: que Fundamentos requiera Lineal cierra el ciclo.
    with pytest.raises(BusinessRuleError) as error:
        await world.topic_service.update(
            world.instructor,
            fundamentals.topic.id or 0,
            draft("Fundamentos", prerequisite_topic_ids=[linear.topic.id or 0]),
        )
    assert error.value.code == "PREREQUISITE_CYCLE"
    cycle = error.value.extra["cycle"]
    assert cycle[0] == cycle[-1] == fundamentals.topic.id
    assert linear.topic.id in cycle


async def test_a_topic_cannot_require_itself_or_a_topic_of_another_course(world: World) -> None:
    course_id = await course_in_review(world)
    other_course = await new_course(world, "Otro curso")
    foreign = await world.topic_service.create(world.instructor, other_course, draft("Ajeno"))
    first = (await world.topic_service.list_topics(world.instructor, course_id)).topics[0]
    with pytest.raises(BusinessRuleError) as self_error:
        await world.topic_service.update(
            world.instructor,
            first.topic.id or 0,
            draft("x", prerequisite_topic_ids=[first.topic.id or 0]),
        )
    assert self_error.value.code == "PREREQUISITE_SELF"
    with pytest.raises(BusinessRuleError) as other_error:
        await world.topic_service.update(
            world.instructor,
            first.topic.id or 0,
            draft("x", prerequisite_topic_ids=[foreign.topic.id or 0]),
        )
    assert other_error.value.code == "PREREQUISITE_TOPIC_NOT_FOUND"


async def test_removing_a_prerequisite_edge_works_and_frees_the_cycle(world: World) -> None:
    course_id = await course_in_review(world)
    topics = {
        t.topic.name: t
        for t in (await world.topic_service.list_topics(world.instructor, course_id)).topics
    }
    linear = topics["Regresión lineal"]
    updated = await world.topic_service.update(
        world.instructor, linear.topic.id or 0, draft("Regresión lineal", prerequisite_topic_ids=[])
    )
    assert updated.prerequisite_topic_ids == []
    fundamentals = topics["Fundamentos"]
    await world.topic_service.update(
        world.instructor,
        fundamentals.topic.id or 0,
        draft("Fundamentos", prerequisite_topic_ids=[linear.topic.id or 0]),
    )


async def test_deactivating_a_topic_marks_it_deleted_and_drops_its_edges(world: World) -> None:
    course_id = await course_in_review(world)
    topics = {
        t.topic.name: t
        for t in (await world.topic_service.list_topics(world.instructor, course_id)).topics
    }
    await world.topic_service.deactivate(world.instructor, topics["Fundamentos"].topic.id or 0)
    listing = await world.topic_service.list_topics(world.instructor, course_id)
    assert listing.review_counts["deleted"] == 1
    assert len(listing.topics) == 2
    assert all(
        topics["Fundamentos"].topic.id not in t.prerequisite_topic_ids for t in listing.topics
    )
    graph = await world.topic_service.graph(world.instructor, course_id)
    assert len(graph.nodes) == 2
    assert all(e.prerequisite_topic_id != topics["Fundamentos"].topic.id for e in graph.edges)
    with pytest.raises(NotFoundError):
        await world.topic_service.deactivate(world.instructor, topics["Fundamentos"].topic.id or 0)


async def test_topics_of_another_instructors_course_are_404(world: World) -> None:
    course_id = await course_in_review(world)
    topic = (await world.topic_service.list_topics(world.instructor, course_id)).topics[0]
    with pytest.raises(NotFoundError) as error:
        await world.topic_service.update(world.other_instructor, topic.topic.id or 0, draft("x"))
    assert error.value.code == "TOPIC_NOT_FOUND"
    with pytest.raises(NotFoundError):
        await world.topic_service.deactivate(world.other_instructor, topic.topic.id or 0)
    with pytest.raises(NotFoundError):
        await world.topic_service.list_topics(world.other_instructor, course_id)
    with pytest.raises(NotFoundError):
        await world.topic_service.create(world.other_instructor, course_id, draft("x"))


async def test_topics_cannot_be_edited_while_the_course_is_published_or_generating(
    world: World,
) -> None:
    course_id = await course_in_review(world)
    world.ai.auto_complete = False
    await world.publication_service.publish(world.instructor, course_id)
    with pytest.raises(InvalidStateTransitionError):
        await world.topic_service.create(world.instructor, course_id, draft("Tarde"))


# --- métricas de extracción -------------------------------------------------------------------


async def test_extraction_metrics_compare_the_llm_output_with_the_final_review(
    world: World,
) -> None:
    course_id = await course_in_review(world)
    perfect = await world.syllabus_service.metrics(world.instructor, course_id)
    assert perfect.topics is not None
    assert (perfect.topics.precision, perfect.topics.recall, perfect.topics.f1) == (1.0, 1.0, 1.0)
    assert perfect.prerequisites is not None
    assert perfect.prerequisites.f1 == 1.0
    assert perfect.corrections == 0

    topics = (await world.topic_service.list_topics(world.instructor, course_id)).topics
    await world.topic_service.deactivate(world.instructor, topics[2].topic.id or 0)
    await world.topic_service.create(world.instructor, course_id, draft("Tema nuevo"))
    after = await world.syllabus_service.metrics(world.instructor, course_id)
    assert after.topics is not None
    # LLM: 3 temas; final: 2 del LLM + 1 nuevo. Aciertos: 2.
    assert after.topics.precision == pytest.approx(2 / 3)
    assert after.topics.recall == pytest.approx(2 / 3)
    assert after.corrections == 2  # uno borrado y uno agregado


async def test_metrics_before_the_first_ingestion_are_empty(world: World) -> None:
    course_id = await new_course(world)
    metrics = await world.syllabus_service.metrics(world.instructor, course_id)
    assert metrics.topics is None
    assert metrics.corrections == 0


# --- publicación ------------------------------------------------------------------------------


async def test_publishing_validates_the_review_then_queues_the_generation(world: World) -> None:
    course_id = await course_in_review(world)
    world.ai.auto_complete = False
    job = await world.publication_service.publish(world.instructor, course_id)
    assert (await world.course_service.get(world.instructor, course_id)).course.status == (
        "generating_content"
    )
    submitted = world.ai.submitted[-1]
    assert submitted.job_type == "course.generate_content"
    assert submitted.input["course_id"] == course_id
    assert submitted.input["quiz_items_per_topic"] == 23
    assert submitted.input["final_versions"] == 2
    assert job.job_id in world.ai.jobs
    assert submitted.idempotency_key.startswith(f"course.generate_content:course:{course_id}:")


async def test_a_course_that_is_not_in_review_cannot_be_published(world: World) -> None:
    course_id = await new_course(world)
    with pytest.raises(InvalidStateTransitionError):
        await world.publication_service.publish(world.instructor, course_id)


async def test_publishing_requires_outcomes_in_every_topic(world: World) -> None:
    course_id = await course_in_review(world)
    bare = await world.topic_service.create(
        world.instructor, course_id, TopicDraft(name="Sin resultados")
    )
    with pytest.raises(BusinessRuleError) as error:
        await world.publication_service.publish(world.instructor, course_id)
    assert error.value.code == "COURSE_REVIEW_INCOMPLETE"
    assert error.value.extra["missing"] == [bare.topic.id]


async def test_publishing_with_no_topics_is_incomplete(world: World) -> None:
    course_id = await course_in_review(world)
    for view in (await world.topic_service.list_topics(world.instructor, course_id)).topics:
        await world.topic_service.deactivate(world.instructor, view.topic.id or 0)
    with pytest.raises(BusinessRuleError) as error:
        await world.publication_service.publish(world.instructor, course_id)
    assert error.value.code == "COURSE_REVIEW_INCOMPLETE"


async def test_the_publication_key_changes_when_the_content_changes(world: World) -> None:
    course_id = await course_in_review(world)
    world.ai.auto_complete = False
    await world.publication_service.publish(world.instructor, course_id)
    first_key = world.ai.submitted[-1].idempotency_key
    # Se abre de nuevo la edición y se cambia un tema.
    await world.courses.update(course_id, {"status": "in_review"})
    topic = (await world.topic_service.list_topics(world.instructor, course_id)).topics[0]
    await world.topic_service.update(
        world.instructor, topic.topic.id or 0, draft("Fundamentos 2", prerequisite_topic_ids=[])
    )
    await world.publication_service.publish(world.instructor, course_id)
    assert world.ai.submitted[-1].idempotency_key != first_key


async def test_publishing_twice_with_the_same_content_reuses_the_same_job(world: World) -> None:
    course_id = await course_in_review(world)
    world.ai.auto_complete = False
    first = await world.publication_service.publish(world.instructor, course_id)
    await world.courses.update(course_id, {"status": "in_review"})
    second = await world.publication_service.publish(world.instructor, course_id)
    assert first.job_id == second.job_id
    # la extracción, una sola generación y un solo banco del diagnóstico
    assert len(world.ai.jobs) == 3
