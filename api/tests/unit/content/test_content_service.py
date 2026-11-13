"""Reglas de contenido sobre repositorios en memoria y `FakeAiService`."""

from dataclasses import dataclass

import pytest

from app.common.entities import require_id
from app.common.exceptions import (
    BusinessRuleError,
    ConflictError,
    InvalidStateTransitionError,
    NotFoundError,
)
from app.domains.ai_gateway.entities import JobRefs
from app.domains.ai_gateway.fake import FakeAiService
from app.domains.ai_gateway.service import IngestorRegistry, JobService
from app.domains.content.constants import ContentJobType
from app.domains.content.contracts import TopicExplanationBody
from app.domains.content.entities import Resource
from app.domains.content.ingestion import (
    ExplanationIngestor,
    FaithfulnessIngestor,
    ItemBankIngestor,
    ItemReviewIngestor,
    VideoIngestor,
)
from app.domains.content.service import (
    ItemChanges,
    ItemService,
    ResourceService,
    VideoFeedbackService,
    VideoService,
    bayesian_quality,
    quality_status,
    version_label,
)
from app.domains.courses.entities import Course, Topic
from app.domains.identity.authentication import CurrentUser
from tests.unit.conftest import World
from tests.unit.fakes_content import (
    InMemoryEnrollments,
    InMemoryFeedback,
    InMemoryItems,
    InMemoryResources,
    InMemoryVideos,
)


@dataclass
class ContentWorld:
    base: World
    course_id: int
    topic_id: int
    resources: InMemoryResources
    items: InMemoryItems
    videos: InMemoryVideos
    feedback: InMemoryFeedback
    enrollments: InMemoryEnrollments
    resource_service: ResourceService
    item_service: ItemService
    video_service: VideoService
    feedback_service: VideoFeedbackService
    jobs: JobService

    @property
    def ai(self) -> FakeAiService:
        return self.base.ai

    @property
    def refs(self) -> JobRefs:
        return JobRefs(course_id=self.course_id, topic_id=self.topic_id)


@pytest.fixture
async def cw(world: World) -> ContentWorld:
    course = await world.courses.add(Course(owner_user_id=2, name="Curso", status="published"))
    course_id = require_id(course)
    topic = await world.topics.add(Topic(course_id=course_id, name="Tema", origin="llm"))
    resources, items, videos = InMemoryResources(), InMemoryItems(), InMemoryVideos()
    feedback = InMemoryFeedback()
    enrollments = InMemoryEnrollments({7: (4, course_id)})
    ai, uow = world.ai, world.uow
    ingestors = [
        ExplanationIngestor(world.courses, world.topics, resources, ai, uow),
        FaithfulnessIngestor(world.courses, world.topics, resources, ai, uow),
        ItemReviewIngestor(world.courses, world.topics, items, ai, uow),
        VideoIngestor(world.courses, world.topics, videos, resources, ai, uow),
        ItemBankIngestor(
            ContentJobType.QUIZ_BANK, "banco", world.courses, world.topics, items, ai, uow
        ),
    ]
    return ContentWorld(
        base=world,
        course_id=course_id,
        topic_id=require_id(topic),
        resources=resources,
        items=items,
        videos=videos,
        feedback=feedback,
        enrollments=enrollments,
        resource_service=ResourceService(resources, world.topics, world.courses, ai, uow),
        item_service=ItemService(items, world.topics, world.courses, ai, uow),
        video_service=VideoService(
            videos, resources, world.topics, world.courses, world.paths, feedback, uow
        ),
        feedback_service=VideoFeedbackService(videos, feedback, world.topics, enrollments, uow),
        jobs=JobService(ai, IngestorRegistry([*world.job_service._registry.all(), *ingestors])),
    )


async def run(cw: ContentWorld, job_type: str, input_: dict[str, object], tag: str = "1") -> None:
    ref = await cw.ai.submit_job(job_type, input_, f"{job_type}:{tag}", cw.refs)
    await cw.jobs.get(ref.job_id, cw.base.instructor)


BODY = TopicExplanationBody.model_validate(
    {
        "title": "t",
        "sections": [{"heading": "h", "body": "b"}],
        "worked_example": "e",
        "summary": "s",
        "sources": [{"n": 1, "source_id": "c1", "title": "T", "url": "https://example.org"}],
    }
)


def test_version_labels_show_the_integer_as_one_dot_n() -> None:
    assert [version_label(v) for v in (1, 2, 5)] == ["1.0", "1.1", "1.4"]


def test_the_bayesian_index_moves_toward_the_prior_with_few_ratings() -> None:
    assert bayesian_quality(0, 0) == 0.5
    assert bayesian_quality(2, 2) < bayesian_quality(20, 20) < 1
    assert bayesian_quality(0, 10) < 0.5


async def test_an_explanation_job_is_ingested_once(cw: ContentWorld) -> None:
    await run(cw, "content.explain_topic", {"topic_id": str(cw.topic_id)})
    ref = next(iter(cw.ai.jobs))
    await cw.jobs.get(ref, cw.base.instructor)
    await cw.jobs.get(ref, cw.base.admin)
    listed = await cw.resource_service.list_for_topic(cw.base.instructor, cw.topic_id)
    assert len(listed) == 1
    assert listed[0].review_status == "pending_review"


async def test_a_job_of_another_instructors_course_is_not_visible(cw: ContentWorld) -> None:
    ref = await cw.ai.submit_job("content.explain_topic", {"topic_id": "1"}, "k", cw.refs)
    with pytest.raises(NotFoundError):
        await cw.jobs.get(ref.job_id, cw.base.other_instructor)


async def test_approving_retires_the_previous_approved_version(cw: ContentWorld) -> None:
    await run(cw, "content.explain_topic", {"topic_id": str(cw.topic_id)}, "a")
    first = (await cw.resource_service.list_for_topic(cw.base.instructor, cw.topic_id))[0]
    await cw.resource_service.review(cw.base.instructor, require_id(first), "approved")
    await run(cw, "content.explain_topic", {"topic_id": str(cw.topic_id)}, "b")
    second = (await cw.resource_service.list_for_topic(cw.base.instructor, cw.topic_id))[1]
    await cw.resource_service.review(cw.base.instructor, require_id(second), "approved")
    states = [
        r.review_status
        for r in await cw.resource_service.list_for_topic(cw.base.instructor, cw.topic_id)
    ]
    assert states == ["retired", "approved"]


async def test_resource_transitions_are_validated(cw: ContentWorld) -> None:
    resource = await cw.resources.add(Resource(topic_id=cw.topic_id, content="{}"))
    user = cw.base.instructor
    await cw.resource_service.review(user, require_id(resource), "retired")
    with pytest.raises(InvalidStateTransitionError):
        await cw.resource_service.review(user, require_id(resource), "approved")


async def test_only_the_main_text_can_be_edited_or_regenerated(cw: ContentWorld) -> None:
    video = await cw.resources.add(
        Resource(topic_id=cw.topic_id, resource_type="video", url="https://example.org")
    )
    for call in (
        cw.resource_service.edit_content(cw.base.instructor, require_id(video), BODY),
        cw.resource_service.regenerate(cw.base.instructor, require_id(video)),
    ):
        with pytest.raises(BusinessRuleError):
            await call


async def test_editing_asks_for_a_faithfulness_check_with_the_new_text(cw: ContentWorld) -> None:
    await run(cw, "content.explain_topic", {"topic_id": str(cw.topic_id)})
    first = (await cw.resource_service.list_for_topic(cw.base.instructor, cw.topic_id))[0]
    edit = await cw.resource_service.edit_content(cw.base.instructor, require_id(first), BODY)
    assert edit.resource.version == 2
    assert edit.resource.edited_by_user_id == cw.base.instructor.id
    submitted = cw.ai.submitted[-1]
    assert submitted.job_type == "content.check_faithfulness"
    assert submitted.input["source_ids"] == ["c1"]
    assert "h\nb" in str(submitted.input["text"])
    await cw.jobs.get(edit.faithfulness_job_id, cw.base.instructor)
    updated = await cw.resources.get(require_id(edit.resource))
    assert updated is not None
    assert updated.faithfulness == 0.5


async def test_a_stale_faithfulness_result_is_not_applied_to_a_newer_edit(cw: ContentWorld) -> None:
    cw.ai.auto_complete = False
    await run_pending_explanation(cw)
    first = (await cw.resource_service.list_for_topic(cw.base.instructor, cw.topic_id))[0]
    one = await cw.resource_service.edit_content(cw.base.instructor, require_id(first), BODY)
    two = await cw.resource_service.edit_content(cw.base.instructor, require_id(one.resource), BODY)
    for job_id in (one.faithfulness_job_id, two.faithfulness_job_id):
        cw.ai.complete(job_id)
    await cw.jobs.get(one.faithfulness_job_id, cw.base.instructor)
    stale = await cw.resources.get(require_id(one.resource))
    assert stale is not None
    assert stale.faithfulness is None  # la versión 2 es la que espera la medida


async def run_pending_explanation(cw: ContentWorld) -> None:
    cw.ai.auto_complete = True
    await run(cw, "content.explain_topic", {"topic_id": str(cw.topic_id)})
    cw.ai.auto_complete = False


async def test_regenerating_uses_a_new_key_per_version(cw: ContentWorld) -> None:
    await run(cw, "content.explain_topic", {"topic_id": str(cw.topic_id)})
    first = (await cw.resource_service.list_for_topic(cw.base.instructor, cw.topic_id))[0]
    job = await cw.resource_service.regenerate(cw.base.instructor, require_id(first))
    assert cw.ai.submitted[-1].idempotency_key.endswith(":v2")
    assert job.job_id


async def test_item_edits_validate_the_shape_and_ask_for_review(cw: ContentWorld) -> None:
    await run(
        cw,
        "items.generate_quiz_bank",
        {"topic_id": str(cw.topic_id), "n_multiple_choice": 2, "n_short_answer": 1},
    )
    items, total = await cw.item_service.list_for_topic(
        cw.base.instructor, cw.topic_id, source=None, review_status=None, limit=10, offset=0
    )
    assert total == 3
    mc = next(i for i in items if i.item_type == "multiple_choice")
    sa = next(i for i in items if i.item_type == "short_answer")
    user = cw.base.instructor
    with pytest.raises(BusinessRuleError):
        await cw.item_service.update(
            user, require_id(sa), ItemChanges(options=["a", "b", "c", "d"])
        )
    with pytest.raises(BusinessRuleError):
        await cw.item_service.update(
            user,
            require_id(sa),
            ItemChanges(
                rubric=[{"criterion": "x", "points": 0.3}, {"criterion": "y", "points": 0.3}]
            ),
        )
    with pytest.raises(BusinessRuleError):
        await cw.item_service.update(
            user, require_id(mc), ItemChanges(stem="x", review_status="approved")
        )
    edited = await cw.item_service.update(user, require_id(mc), ItemChanges(stem="Nuevo"))
    assert edited.review_status == "pending_review"
    assert cw.ai.submitted[-1].job_type == "items.review"
    again = await cw.item_service.update(
        user, require_id(mc), ItemChanges(review_status="approved")
    )
    assert again.review_status == "approved"
    with pytest.raises(InvalidStateTransitionError):
        await cw.item_service.update(user, require_id(mc), ItemChanges(review_status="approved"))


async def test_an_item_of_another_instructor_is_404(cw: ContentWorld) -> None:
    await run(
        cw,
        "items.generate_quiz_bank",
        {"topic_id": str(cw.topic_id), "n_multiple_choice": 1, "n_short_answer": 0},
    )
    item = next(iter(cw.items.items.values()))
    with pytest.raises(NotFoundError) as caught:
        await cw.item_service.update(
            cw.base.other_instructor, require_id(item), ItemChanges(review_status="approved")
        )
    assert caught.value.code == "ITEM_NOT_FOUND"


async def test_a_bank_with_a_topic_of_another_course_is_invalid(cw: ContentWorld) -> None:
    from app.domains.ai_gateway.exceptions import AiResultInvalidError

    other = await cw.base.courses.add(Course(owner_user_id=2, name="Otro", status="published"))
    foreign = await cw.base.topics.add(Topic(course_id=require_id(other), name="Ajeno"))
    ref = await cw.ai.submit_job(
        "items.generate_quiz_bank",
        {"topic_id": str(require_id(foreign)), "n_multiple_choice": 1, "n_short_answer": 0},
        "foreign",
        JobRefs(course_id=cw.course_id, topic_id=None),
    )
    with pytest.raises(AiResultInvalidError):
        await cw.jobs.get(ref.job_id, cw.base.admin)


async def test_only_one_video_is_in_use_and_judgments_are_per_judge(cw: ContentWorld) -> None:
    await run(cw, "video.collect_candidates", {"topic_id": str(cw.topic_id)})
    views = await cw.video_service.list_for_topic(cw.base.instructor, cw.topic_id)
    assert [v.video.status for v in views] == ["in_use", "backup", "backup"]
    second = require_id(views[1].video)
    changed = await cw.video_service.update(
        cw.base.instructor, second, status="in_use", is_relevant=True
    )
    assert changed.relevance_judgment is True
    statuses = [
        v.video.status for v in await cw.video_service.list_for_topic(cw.base.admin, cw.topic_id)
    ]
    assert statuses == ["backup", "in_use", "backup"]
    admin_view = await cw.video_service.list_for_topic(cw.base.admin, cw.topic_id)
    assert admin_view[1].relevance_judgment is None  # el juicio es del instructor
    with pytest.raises(BusinessRuleError):
        await cw.video_service.update(cw.base.instructor, second, status=None, is_relevant=None)


async def test_a_manual_video_is_unique_per_topic(cw: ContentWorld) -> None:
    kwargs = {
        "youtube_video_id": "EXAMPLE0004",
        "title": "t",
        "channel": None,
        "duration_seconds": None,
        "language": None,
    }
    added = await cw.video_service.add_manual(cw.base.instructor, cw.topic_id, **kwargs)
    assert added.video.status == "backup"
    assert added.video.origin == "instructor"
    with pytest.raises(ConflictError):
        await cw.video_service.add_manual(cw.base.instructor, cw.topic_id, **kwargs)


async def test_video_feedback_belongs_to_the_enrolled_learner_and_replaces_itself(
    cw: ContentWorld,
) -> None:
    await run(cw, "video.collect_candidates", {"topic_id": str(cw.topic_id)})
    video_id = require_id(next(iter(cw.videos.items.values())))
    learner: CurrentUser = cw.base.learner
    args = {
        "video_candidate_id": video_id,
        "enrollment_id": 7,
        "comment": None,
        "watched_fully": True,
    }
    _, created = await cw.feedback_service.submit(learner, rating="useful", **args)  # type: ignore[arg-type]
    replaced, created_again = await cw.feedback_service.submit(learner, rating="outdated", **args)  # type: ignore[arg-type]
    assert (created, created_again) == (True, False)
    assert replaced.rating == "outdated"
    with pytest.raises(NotFoundError):
        await cw.feedback_service.submit(cw.base.other_instructor, rating="useful", **args)  # type: ignore[arg-type]
    with pytest.raises(NotFoundError):
        await cw.feedback_service.submit(
            learner, rating="useful", **{**args, "video_candidate_id": 999}
        )  # type: ignore[arg-type]


async def test_video_quality_shows_measuring_until_enough_ratings(cw: ContentWorld) -> None:
    from app.domains.learning_paths.entities import LearningPath

    path = await cw.base.paths.add(LearningPath(course_id=cw.course_id, name="Ruta"))
    await run(cw, "video.collect_candidates", {"topic_id": str(cw.topic_id)})
    video_id = require_id(next(iter(cw.videos.items.values())))
    for enrollment in range(1, 7):
        cw.enrollments.rows[enrollment] = (cw.base.learner.id, cw.course_id)
        await cw.feedback_service.submit(
            cw.base.learner,
            video_candidate_id=video_id,
            enrollment_id=enrollment,
            rating="useful",
            comment=None,
            watched_fully=None,
        )
    rows = await cw.video_service.quality(cw.base.instructor, require_id(path))
    top = next(r for r in rows if require_id(r.video) == video_id)
    assert (top.ratings, top.measuring) == (6, False)
    assert top.useful_rate == 1.0
    assert top.quality_index is not None
    # 6 «útil» de 6: (5 · 0,5 + 6) / 11 = 0,77, desde 0,75 se recomienda.
    assert top.status == "recommended"
    other = next(r for r in rows if require_id(r.video) != video_id)
    assert other.measuring is True
    assert other.status == "measuring"


def test_the_video_status_follows_the_d5f_thresholds() -> None:
    assert quality_status(None) == "measuring"
    assert quality_status(0.75) == "recommended"
    assert quality_status(0.749) == "observation"
    assert quality_status(0.60) == "observation"
    assert quality_status(0.599) == "under_review"
