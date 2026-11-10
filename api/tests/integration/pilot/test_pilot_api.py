"""Piloto contra el esquema real: configuración, sorteo con semilla, preparación e inicio."""

from typing import Any

import httpx
import pytest
from sqlalchemy import text
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


async def new_pilot(client: httpx.AsyncClient, course: Course, **extra: Any) -> dict[str, Any]:
    body = {
        "learning_path_id": course.path_id,
        "starts_on": "2026-12-01",
        "ends_on": "2026-12-20",
        "delayed_posttest_on": "2027-01-10",
        "random_seed": 42,
        **extra,
    }
    response = await client.post(f"{API}/pilots", json=body)
    assert response.status_code == 201, response.text
    created: dict[str, Any] = response.json()
    return created


async def enroll(
    engine: AsyncEngine,
    client_for: ClientFactory,
    course: Course,
    name: str,
    *,
    pilot_consent: bool,
) -> int:
    learner, learner_id = await make_learner(engine, client_for, name)
    if pilot_consent:
        granted = await learner.post(
            f"{API}/me/consents", json={"consent_type": "pilot_research", "document_version": "1.0"}
        )
        assert granted.status_code in (200, 201), granted.text
    return await insert_enrollment(engine, learner_id, course.path_id)


async def arms(engine: AsyncEngine) -> dict[int, tuple[str | None, bool]]:
    async with engine.connect() as conn:
        rows = await conn.execute(
            text("SELECT id, pilot_arm, analysis_included FROM enrollments ORDER BY id")
        )
        return {int(r[0]): (r[1], bool(r[2])) for r in rows.all()}


async def make_ready(ai: FakeAiService, course: Course) -> None:
    """Explicaciones, bancos y videos aprobados de todos los temas."""
    owner = course.owner
    for topic in course.topic_ids:
        await ingest_explanation(ai, course, topic)
        await ingest_quiz_bank(ai, course, topic)
        await ingest_videos(ai, course, topic)
        resource = (await owner.get(f"{API}/topics/{topic}/resources")).json()[0]
        await owner.patch(
            f"{API}/resources/{resource['id']}/review", json={"review_status": "approved"}
        )
    ids = [str(t) for t in course.topic_ids]
    await run_job(ai, owner, course, "diagnostic.generate_items", {"topic_ids": ids}, topic_id=None)
    await run_job(
        ai,
        owner,
        course,
        "items.generate_final_bank",
        {"topic_ids": ids, "n_short_answer": 1},
        topic_id=None,
    )
    for topic in course.topic_ids:
        items = (
            await owner.get(
                f"{API}/topics/{topic}/items",
                params={"review_status": "pending_review", "limit": 100},
            )
        ).json()["items"]
        for item in items:
            await owner.patch(f"{API}/items/{item['id']}", json={"review_status": "approved"})


async def test_the_admin_configures_the_pilot_and_only_one_stays_open_per_path(
    course: Course, client: httpx.AsyncClient
) -> None:
    pilot = await new_pilot(client, course)
    assert pilot["status"] == "draft"
    assert pilot["arms"] == {"personalized": 0, "fixed": 0}
    again = await client.post(
        f"{API}/pilots", json={"learning_path_id": course.path_id, "random_seed": 1}
    )
    assert again.status_code == 409

    fetched = await client.get(f"{API}/pilots/{pilot['id']}")
    assert fetched.json()["random_seed"] == 42
    listed = await client.get(f"{API}/pilots")
    assert listed.json()["total"] == 1

    body = {"learning_path_id": course.path_id, "starts_on": "2026-12-05", "ends_on": "2026-12-25"}
    updated = await client.put(f"{API}/pilots/{pilot['id']}", json=body)
    assert updated.status_code == 200
    assert updated.json()["starts_on"] == "2026-12-05"
    assert updated.json()["random_seed"] is None
    bad_dates = await client.put(
        f"{API}/pilots/{pilot['id']}", json={**body, "ends_on": "2026-11-01"}
    )
    assert bad_dates.status_code == 422
    unknown = await client.post(f"{API}/pilots", json={"learning_path_id": 9999})
    assert unknown.status_code == 404


async def test_randomizing_includes_only_those_with_consent_and_repeats_with_the_same_seed(
    course: Course, client: httpx.AsyncClient, engine: AsyncEngine, client_for: ClientFactory
) -> None:
    pilot = await new_pilot(client, course)
    with_consent = [
        await enroll(engine, client_for, course, f"con-{n}", pilot_consent=True) for n in range(3)
    ]
    without = await enroll(engine, client_for, course, "sin", pilot_consent=False)

    first = await client.post(f"{API}/pilots/{pilot['id']}/randomize")
    assert first.status_code == 200, first.text
    assert first.json() == {
        "personalized": 2,
        "fixed": 1,
        "skipped_without_consent": 1,
        "random_seed": 42,
    }
    chosen = await arms(engine)
    assert chosen[without] == (None, False)
    assert all(chosen[i][0] in ("personalized", "fixed") and chosen[i][1] for i in with_consent)
    assert (await client.get(f"{API}/pilots/{pilot['id']}")).json()["status"] == "randomized"

    again = await client.post(f"{API}/pilots/{pilot['id']}/randomize")
    assert again.status_code == 200
    assert await arms(engine) == chosen  # misma semilla, mismo sorteo

    # Cambiar la semilla anula el sorteo.
    body = {"learning_path_id": course.path_id, "starts_on": "2026-12-01", "ends_on": "2026-12-20"}
    reset = await client.put(f"{API}/pilots/{pilot['id']}", json={**body, "random_seed": 7})
    assert reset.json()["status"] == "draft"
    assert all(arm == (None, False) for arm in (await arms(engine)).values())


async def test_randomizing_without_any_consent_is_refused(
    course: Course, client: httpx.AsyncClient, engine: AsyncEngine, client_for: ClientFactory
) -> None:
    pilot = await new_pilot(client, course)
    only = await enroll(engine, client_for, course, "sin-uno", pilot_consent=False)
    refused = await client.post(f"{API}/pilots/{pilot['id']}/randomize")
    assert refused.status_code == 422
    assert refused.json()["code"] == "PILOT_CONSENT_REQUIRED"
    assert (await arms(engine))[only] == (None, False)


async def test_a_revoked_consent_leaves_the_learner_out_of_the_draw(
    course: Course, client: httpx.AsyncClient, engine: AsyncEngine, client_for: ClientFactory
) -> None:
    pilot = await new_pilot(client, course)
    learner, learner_id = await make_learner(engine, client_for, "revoca")
    await learner.post(
        f"{API}/me/consents", json={"consent_type": "pilot_research", "document_version": "1.0"}
    )
    await learner.patch(f"{API}/me/consents/pilot_research/revoke")
    await insert_enrollment(engine, learner_id, course.path_id)
    refused = await client.post(f"{API}/pilots/{pilot['id']}/randomize")
    assert refused.json()["code"] == "PILOT_CONSENT_REQUIRED"


async def test_the_pilot_starts_only_when_it_is_ready_and_then_it_is_frozen(
    course: Course,
    ai: FakeAiService,
    client: httpx.AsyncClient,
    engine: AsyncEngine,
    client_for: ClientFactory,
) -> None:
    pilot = await new_pilot(client, course)
    readiness = (await client.get(f"{API}/pilots/{pilot['id']}/readiness")).json()
    assert readiness["ready"] is False
    assert {
        "randomization",
        "min_consents",
        "item_bank",
        "approved_explanations",
        "video_backups",
    } <= set(readiness["missing"])
    refused = await client.post(f"{API}/pilots/{pilot['id']}/start")
    assert refused.status_code == 422
    assert refused.json()["code"] == "PILOT_NOT_READY"
    assert "item_bank" in refused.json()["missing"]

    await make_ready(ai, course)
    for n in range(1, 3):
        await enroll(engine, client_for, course, f"par-{n}", pilot_consent=True)
    assert (await client.post(f"{API}/pilots/{pilot['id']}/randomize")).status_code == 200
    ready = (await client.get(f"{API}/pilots/{pilot['id']}/readiness")).json()
    assert ready == {"ready": True, "missing": []}

    started = await client.post(f"{API}/pilots/{pilot['id']}/start")
    assert started.status_code == 200, started.text
    assert started.json()["status"] == "running"
    assert started.json()["arms"] == {"personalized": 1, "fixed": 1}

    frozen = await client.put(
        f"{API}/pilots/{pilot['id']}", json={"learning_path_id": course.path_id}
    )
    assert frozen.status_code == 409
    assert frozen.json()["code"] == "PILOT_ALREADY_STARTED"
    for path in ("randomize", "start"):
        again = await client.post(f"{API}/pilots/{pilot['id']}/{path}")
        assert again.status_code == 409
        assert again.json()["code"] == "PILOT_ALREADY_STARTED"


async def test_the_fixed_path_preview_asks_the_ai_service_for_the_fixed_arm(
    course: Course, ai: FakeAiService, client: httpx.AsyncClient
) -> None:
    pilot = await new_pilot(client, course)
    seen: dict[str, Any] = {}

    def sequence(input_: dict[str, Any]) -> dict[str, Any]:
        seen.update(input_)
        return {"pilot_arm": "fixed", "steps": []}

    ai.task_results["path.sequence"] = sequence
    preview = await client.get(f"{API}/pilots/{pilot['id']}/fixed-path-preview")
    assert preview.status_code == 200
    assert preview.json()["pilot_arm"] == "fixed"
    assert seen["pilot_arm"] == "fixed"
    assert [t["topic_id"] for t in seen["topics"]] == [str(t) for t in course.topic_ids]
    assert seen["topics"][1]["prerequisites"] == [str(course.topic_ids[0])]
    assert seen["mastery_skip_threshold"] == 80.0


async def test_only_the_admin_reaches_the_pilot_routes(
    course: Course,
    client: httpx.AsyncClient,
    bare_client: httpx.AsyncClient,
    engine: AsyncEngine,
    client_for: ClientFactory,
) -> None:
    pilot = await new_pilot(client, course)
    learner, _ = await make_learner(engine, client_for, "curioso")
    routes = [
        ("GET", f"/pilots/{pilot['id']}"),
        ("GET", "/pilots"),
        ("PUT", f"/pilots/{pilot['id']}"),
        ("POST", f"/pilots/{pilot['id']}/randomize"),
        ("POST", f"/pilots/{pilot['id']}/start"),
        ("GET", f"/pilots/{pilot['id']}/readiness"),
        ("GET", f"/pilots/{pilot['id']}/fixed-path-preview"),
    ]
    for method, path in routes:
        for who in (course.owner, learner):
            denied = await who.request(method, API + path, json={"learning_path_id": 1})
            assert denied.status_code == 403, f"{method} {path}: {denied.text}"
            assert denied.json()["code"] == "INSUFFICIENT_ROLE"
        assert (await bare_client.request(method, API + path)).status_code == 401
    missing = await client.get(f"{API}/pilots/9999")
    assert missing.status_code == 404
    assert missing.json()["code"] == "PILOT_NOT_FOUND"
