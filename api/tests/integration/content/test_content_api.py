"""Contenido contra el esquema real: recursos, ítems, videos y su ingesta idempotente."""

import uuid
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from app.domains.ai_gateway.fake import FakeAiService
from tests.integration.conftest import ClientFactory
from tests.integration.world_content import (
    API,
    Course,
    ingest_explanation,
    ingest_quiz_bank,
    ingest_videos,
    insert_enrollment,
    make_course,
    make_instructor,
    make_learner,
    run_job,
)

pytestmark = pytest.mark.integration


@pytest.fixture
async def course(engine: AsyncEngine, client_for: ClientFactory) -> Course:
    owner, owner_id = await make_instructor(engine, client_for, "duena")
    return await make_course(owner, owner_id)


async def resources(course: Course, topic_id: int) -> list[dict[str, Any]]:
    response = await course.owner.get(f"{API}/topics/{topic_id}/resources")
    assert response.status_code == 200, response.text
    body: list[dict[str, Any]] = response.json()
    return body


# --- explicaciones ----------------------------------------------------------------------------


async def test_the_explanation_arrives_in_review_and_approving_a_new_version_retires_the_old(
    course: Course, ai: FakeAiService
) -> None:
    topic = course.topic_ids[0]
    await ingest_explanation(ai, course, topic)
    first = (await resources(course, topic))[0]
    assert first["review_status"] == "pending_review"
    assert first["version"] == 1
    assert first["version_label"] == "1.0"
    assert first["content"]["sections"][0]["heading"] == "Idea central"
    assert first["faithfulness"] == 0.95

    approved = await course.owner.patch(
        f"{API}/resources/{first['id']}/review", json={"review_status": "approved"}
    )
    assert approved.status_code == 200
    assert approved.json()["review_status"] == "approved"


async def test_a_regenerated_explanation_is_a_new_version_and_ingesting_twice_does_not_duplicate(
    course: Course, ai: FakeAiService
) -> None:
    topic = course.topic_ids[0]
    await ingest_explanation(ai, course, topic)
    first = (await resources(course, topic))[0]
    await course.owner.patch(
        f"{API}/resources/{first['id']}/review", json={"review_status": "approved"}
    )

    response = await course.owner.post(
        f"{API}/resources/{first['id']}/regenerate", headers={"Idempotency-Key": str(uuid.uuid4())}
    )
    assert response.status_code == 202, response.text
    job_id = response.json()["job_id"]
    for _ in range(3):  # consulta repetida: la ingesta es idempotente
        assert (await course.owner.get(f"{API}/jobs/{job_id}")).json()["ingested"] is True
    listed = await resources(course, topic)
    assert [r["version"] for r in listed] == [1, 2]
    assert listed[1]["review_status"] == "pending_review"

    await course.owner.patch(
        f"{API}/resources/{listed[1]['id']}/review", json={"review_status": "approved"}
    )
    after = await resources(course, topic)
    assert [r["review_status"] for r in after] == ["retired", "approved"]


async def test_editing_creates_a_new_version_and_the_faithfulness_job_fills_its_measure(
    course: Course, ai: FakeAiService
) -> None:
    topic = course.topic_ids[0]
    await ingest_explanation(ai, course, topic)
    first = (await resources(course, topic))[0]
    body = {
        "title": "Título editado",
        "sections": [{"heading": "Nueva", "body": "Texto editado [1]."}],
        "worked_example": "Ejemplo",
        "summary": "Resumen",
        "reflection_questions": [],
        "gaps_detected": [],
        "sources": first["content"]["sources"],
    }
    edited = await course.owner.put(f"{API}/resources/{first['id']}/content", json=body)
    assert edited.status_code == 200, edited.text
    version = edited.json()
    assert version["version"] == 2
    assert version["review_status"] == "pending_review"
    assert version["edited_by_user_id"] == course.owner_id
    assert version["faithfulness"] is None

    polled = await course.owner.get(f"{API}/jobs/{version['faithfulness_job_id']}")
    assert polled.json()["ingested"] is True
    refreshed = (await resources(course, topic))[1]
    assert refreshed["faithfulness"] == 0.5
    assert refreshed["unsupported_claims"] == ["Afirmación sin respaldo."]
    assert ai.submitted[-1].job_type == "content.check_faithfulness"


async def test_an_invalid_explanation_body_is_rejected(course: Course, ai: FakeAiService) -> None:
    topic = course.topic_ids[0]
    await ingest_explanation(ai, course, topic)
    first = (await resources(course, topic))[0]
    response = await course.owner.put(
        f"{API}/resources/{first['id']}/content", json={"title": "Sin secciones"}
    )
    assert response.status_code == 422


async def test_a_resource_cannot_go_back_from_retired(course: Course, ai: FakeAiService) -> None:
    topic = course.topic_ids[0]
    await ingest_explanation(ai, course, topic)
    first = (await resources(course, topic))[0]
    await course.owner.patch(
        f"{API}/resources/{first['id']}/review", json={"review_status": "retired"}
    )
    again = await course.owner.patch(
        f"{API}/resources/{first['id']}/review", json={"review_status": "approved"}
    )
    assert again.status_code == 409
    assert again.json()["code"] == "INVALID_STATE_TRANSITION"


# --- ítems ------------------------------------------------------------------------------------


async def test_the_quiz_bank_is_ingested_once_and_reviewed_item_by_item(
    course: Course, ai: FakeAiService
) -> None:
    topic = course.topic_ids[0]
    job_id = await ingest_quiz_bank(ai, course, topic)
    await course.owner.get(f"{API}/jobs/{job_id}")  # segunda consulta: no duplica
    listing = await course.owner.get(f"{API}/topics/{topic}/items")
    assert listing.status_code == 200
    body = listing.json()
    assert body["total"] == 5
    item = body["items"][0]
    assert item["review_status"] == "pending_review"
    assert item["auto_review"]["single_correct_answer"] is True

    approved = await course.owner.patch(
        f"{API}/items/{item['id']}", json={"review_status": "approved"}
    )
    assert approved.json()["review_status"] == "approved"
    only = await course.owner.get(
        f"{API}/topics/{topic}/items", params={"review_status": "approved"}
    )
    assert only.json()["total"] == 1
    shorts = await course.owner.get(f"{API}/topics/{topic}/items", params={"source": "final"})
    assert shorts.json()["total"] == 0


async def test_discarded_items_are_stored_as_auto_rejected(
    course: Course, ai: FakeAiService
) -> None:
    topic = course.topic_ids[0]

    def with_discard(input_: dict[str, Any]) -> dict[str, Any]:
        from app.domains.content.fake_results import fake_quiz_bank

        bank = fake_quiz_bank(input_)
        bank["discarded_item_ids"] = [bank["items"][0]["id"]]
        return bank

    ai.set_result("items.generate_quiz_bank", with_discard, contract="assessment_item_bank.v1")
    await ingest_quiz_bank(ai, course, topic)
    rejected = await course.owner.get(
        f"{API}/topics/{topic}/items", params={"review_status": "auto_rejected"}
    )
    assert rejected.json()["total"] == 1


async def test_editing_an_item_sends_it_back_to_review_and_asks_for_items_review(
    course: Course, ai: FakeAiService
) -> None:
    topic = course.topic_ids[0]
    await ingest_quiz_bank(ai, course, topic)
    items = (await course.owner.get(f"{API}/topics/{topic}/items")).json()["items"]
    mc = next(i for i in items if i["item_type"] == "multiple_choice")
    await course.owner.patch(f"{API}/items/{mc['id']}", json={"review_status": "approved"})

    edited = await course.owner.patch(f"{API}/items/{mc['id']}", json={"stem": "Enunciado nuevo"})
    assert edited.status_code == 200, edited.text
    assert edited.json()["review_status"] == "pending_review"
    assert edited.json()["auto_review"] is None
    submitted = ai.submitted[-1]
    assert submitted.job_type == "items.review"
    assert submitted.input["items"][0]["item_id"] == str(mc["id"])

    review_job = next(j for j in ai.jobs.values() if j.job_type == "items.review")
    assert (await course.owner.get(f"{API}/jobs/{review_job.job_id}")).json()["ingested"] is True
    refreshed = (await course.owner.get(f"{API}/topics/{topic}/items")).json()["items"]
    again = next(i for i in refreshed if i["id"] == mc["id"])
    assert again["auto_review"]["clear_stem"] is True


@pytest.mark.parametrize(
    "body",
    [
        {"options": ["A", "A", "B", "C"]},
        {"correct_option": 9},
        {"stem": "x", "review_status": "approved"},
        {},
        {"rubric": [{"criterion": "x", "points": 1}]},
    ],
)
async def test_invalid_item_changes_are_rejected(
    course: Course, ai: FakeAiService, body: dict[str, Any]
) -> None:
    topic = course.topic_ids[0]
    await ingest_quiz_bank(ai, course, topic)
    items = (await course.owner.get(f"{API}/topics/{topic}/items")).json()["items"]
    mc = next(i for i in items if i["item_type"] == "multiple_choice")
    response = await course.owner.patch(f"{API}/items/{mc['id']}", json=body)
    assert response.status_code == 422, response.text


async def test_a_retired_item_cannot_be_edited_or_approved(
    course: Course, ai: FakeAiService
) -> None:
    topic = course.topic_ids[0]
    await ingest_quiz_bank(ai, course, topic)
    item = (await course.owner.get(f"{API}/topics/{topic}/items")).json()["items"][0]
    await course.owner.patch(f"{API}/items/{item['id']}", json={"review_status": "retired"})
    for body in ({"stem": "x"}, {"review_status": "approved"}):
        response = await course.owner.patch(f"{API}/items/{item['id']}", json=body)
        assert response.status_code == 409


# --- videos -----------------------------------------------------------------------------------


async def test_video_candidates_are_curated_by_the_instructor(
    course: Course, ai: FakeAiService
) -> None:
    topic = course.topic_ids[0]
    await ingest_videos(ai, course, topic)
    listed = (await course.owner.get(f"{API}/topics/{topic}/video-candidates")).json()
    assert listed["has_backup"] is True
    assert listed["topic_name"]
    statuses = [c["status"] for c in listed["candidates"]]
    assert statuses == ["in_use", "backup", "backup"]
    first, second = listed["candidates"][0], listed["candidates"][1]

    judged = await course.owner.patch(
        f"{API}/video-candidates/{first['id']}", json={"is_relevant": False}
    )
    assert judged.json()["relevance_judgment"] is False
    changed = await course.owner.patch(
        f"{API}/video-candidates/{second['id']}", json={"status": "in_use"}
    )
    assert changed.json()["status"] == "in_use"
    relisted = (await course.owner.get(f"{API}/topics/{topic}/video-candidates")).json()
    assert [c["status"] for c in relisted["candidates"]] == ["backup", "in_use", "backup"]
    assert relisted["candidates"][0]["relevance_judgment"] is False
    shared = await resources(course, topic)
    approved_videos = [
        r for r in shared if r["resource_type"] == "video" and r["review_status"] == "approved"
    ]
    assert [r["video_candidate_id"] for r in approved_videos] == [second["id"]]


async def test_video_ingestion_keeps_the_curation_when_it_runs_again(
    course: Course, ai: FakeAiService
) -> None:
    topic = course.topic_ids[0]
    await ingest_videos(ai, course, topic)
    first = (await course.owner.get(f"{API}/topics/{topic}/video-candidates")).json()["candidates"][
        0
    ]
    await course.owner.patch(f"{API}/video-candidates/{first['id']}", json={"status": "rejected"})
    await run_job(
        ai,
        course.owner,
        course,
        "video.collect_candidates",
        {"topic_id": str(topic)},
        topic_id=topic,
        tag="2",
    )
    after = (await course.owner.get(f"{API}/topics/{topic}/video-candidates")).json()["candidates"]
    assert len(after) == 3
    assert after[0]["status"] == "rejected"


async def test_a_manual_video_is_a_backup_and_cannot_be_repeated(course: Course) -> None:
    topic = course.topic_ids[0]
    body = {"youtube_video_id": "EXAMPLE0004", "title": "Mi video"}
    created = await course.owner.post(f"{API}/topics/{topic}/video-candidates", json=body)
    assert created.status_code == 201, created.text
    assert created.json()["origin"] == "instructor"
    assert created.json()["status"] == "backup"
    again = await course.owner.post(f"{API}/topics/{topic}/video-candidates", json=body)
    assert again.status_code == 409
    bad = await course.owner.post(
        f"{API}/topics/{topic}/video-candidates", json={"youtube_video_id": "x", "title": "t"}
    )
    assert bad.status_code == 422


async def test_the_learner_rates_the_video_and_the_quality_view_aggregates_it(
    course: Course,
    ai: FakeAiService,
    engine: AsyncEngine,
    client_for: ClientFactory,
) -> None:
    topic = course.topic_ids[0]
    await ingest_videos(ai, course, topic)
    video = (await course.owner.get(f"{API}/topics/{topic}/video-candidates")).json()["candidates"][
        0
    ]
    learner, learner_id = await make_learner(engine, client_for, "aprendiz")
    enrollment = await insert_enrollment(engine, learner_id, course.path_id)

    body = {
        "video_candidate_id": video["id"],
        "enrollment_id": enrollment,
        "rating": "useful",
        "watched_fully": True,
    }
    created = await learner.post(f"{API}/me/video-feedback", json=body)
    assert created.status_code == 201, created.text
    replaced = await learner.post(f"{API}/me/video-feedback", json={**body, "rating": "too_long"})
    assert replaced.status_code == 200
    assert replaced.json()["created"] is False

    quality = (
        await course.owner.get(f"{API}/learning-paths/{course.path_id}/video-quality")
    ).json()
    row = next(i for i in quality["items"] if i["video"]["id"] == video["id"])
    assert row["ratings"] == 1
    assert row["by_rating"] == {"too_long": 1}
    assert row["measuring"] is True
    assert row["quality_index"] is None
    assert row["status"] == "measuring"
    assert quality["min_ratings"] == 5

    _, stranger_id = await make_learner(engine, client_for, "intruso")
    other = await insert_enrollment(engine, stranger_id, course.path_id)
    # La inscripción de otro aprendiz responde 404; un video de otro curso también.
    assert (
        await learner.post(f"{API}/me/video-feedback", json={**body, "enrollment_id": other})
    ).status_code == 404
    assert (
        await learner.post(f"{API}/me/video-feedback", json={**body, "video_candidate_id": 999})
    ).status_code == 404


# --- propiedad y roles ------------------------------------------------------------------------


@pytest.fixture
async def stranger(engine: AsyncEngine, client_for: ClientFactory) -> httpx.AsyncClient:
    http, _ = await make_instructor(engine, client_for, "intruso-doc")
    return http


async def test_another_instructor_gets_404_on_every_content_route(
    course: Course, ai: FakeAiService, stranger: httpx.AsyncClient
) -> None:
    topic = course.topic_ids[0]
    await ingest_explanation(ai, course, topic)
    await ingest_quiz_bank(ai, course, topic)
    await ingest_videos(ai, course, topic)
    resource = (await resources(course, topic))[0]
    item = (await course.owner.get(f"{API}/topics/{topic}/items")).json()["items"][0]
    video = (await course.owner.get(f"{API}/topics/{topic}/video-candidates")).json()["candidates"][
        0
    ]
    explanation = {
        "title": "t",
        "sections": [{"heading": "h", "body": "b"}],
        "worked_example": "e",
        "summary": "s",
        "sources": resource["content"]["sources"],
    }
    routes: list[tuple[str, str, Any, str]] = [
        ("GET", f"/topics/{topic}/resources", None, "TOPIC_NOT_FOUND"),
        (
            "PATCH",
            f"/resources/{resource['id']}/review",
            {"review_status": "approved"},
            "RESOURCE_NOT_FOUND",
        ),
        ("PUT", f"/resources/{resource['id']}/content", explanation, "RESOURCE_NOT_FOUND"),
        ("GET", f"/topics/{topic}/items", None, "TOPIC_NOT_FOUND"),
        ("PATCH", f"/items/{item['id']}", {"review_status": "approved"}, "ITEM_NOT_FOUND"),
        ("GET", f"/topics/{topic}/video-candidates", None, "TOPIC_NOT_FOUND"),
        (
            "POST",
            f"/topics/{topic}/video-candidates",
            {"youtube_video_id": "EXAMPLE0009", "title": "x"},
            "TOPIC_NOT_FOUND",
        ),
        ("PATCH", f"/video-candidates/{video['id']}", {"is_relevant": True}, "RESOURCE_NOT_FOUND"),
        ("GET", f"/learning-paths/{course.path_id}/video-quality", None, "COURSE_NOT_FOUND"),
    ]
    for method, path, body, code in routes:
        response = await stranger.request(method, API + path, json=body)
        assert response.status_code == 404, f"{method} {path}: {response.text}"
        assert response.json()["code"] == code
    regenerate = await stranger.post(
        f"{API}/resources/{resource['id']}/regenerate",
        headers={"Idempotency-Key": "b2b5b6a4-0b7e-4d57-8a6b-5b1c7f0a9c10"},
    )
    assert regenerate.status_code == 404


async def test_a_learner_cannot_use_the_instructor_routes_and_the_admin_can(
    course: Course,
    ai: FakeAiService,
    engine: AsyncEngine,
    client_for: ClientFactory,
    client: httpx.AsyncClient,
) -> None:
    topic = course.topic_ids[0]
    await ingest_explanation(ai, course, topic)
    learner, _ = await make_learner(engine, client_for, "solo-aprendiz")
    denied = await learner.get(f"{API}/topics/{topic}/resources")
    assert denied.status_code == 403
    assert denied.json()["code"] == "INSUFFICIENT_ROLE"
    assert (await learner.get(f"{API}/topics/{topic}/items")).status_code == 403
    assert (await client.get(f"{API}/topics/{topic}/resources")).status_code == 200
    # El instructor no puede usar la ruta del aprendiz.
    assert (
        await course.owner.post(
            f"{API}/me/video-feedback",
            json={"video_candidate_id": 1, "enrollment_id": 1, "rating": "useful"},
        )
    ).status_code == 403


async def test_content_routes_require_a_token(bare_client: httpx.AsyncClient) -> None:
    assert (await bare_client.get(f"{API}/topics/1/resources")).status_code == 401
    assert (await bare_client.post(f"{API}/me/video-feedback", json={})).status_code == 401
