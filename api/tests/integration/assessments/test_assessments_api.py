import httpx
import pytest

from tests.integration.conftest import MakeFn

pytestmark = pytest.mark.integration

ATTEMPTS = "/api/v1/assessment-attempts"


async def make_step(make: MakeFn, world: dict[str, int]) -> int:
    step = await make(
        "path-steps",
        {"enrollment_id": world["enrollment"], "topic_id": world["topic"], "step_order": 1},
    )
    return step["id"]


async def test_diagnostic_is_one_per_enrollment(
    client: httpx.AsyncClient, make: MakeFn, world: dict[str, int]
) -> None:
    created = await make(
        "diagnostics",
        {
            "enrollment_id": world["enrollment"],
            "questions": [{"id": 1, "text": "¿Qué es la varianza?"}],
            "level_by_topic": {str(world["topic"]): 0.55},
            "completed_at": "2026-10-07T10:00:00-05:00",
        },
    )
    assert created["completed_at"] == "2026-10-07T10:00:00-05:00"
    duplicate = await client.post(
        "/api/v1/diagnostics", json={"enrollment_id": world["enrollment"]}
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "DIAGNOSTIC_ALREADY_EXISTS"


async def test_naive_datetimes_are_rejected(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    response = await client.post(
        "/api/v1/diagnostics",
        json={"enrollment_id": world["enrollment"], "completed_at": "2026-10-07T10:00:00"},
    )
    assert response.status_code == 422


async def test_attempts_are_numbered_and_graded_with_the_path_thresholds(
    client: httpx.AsyncClient, make: MakeFn, world: dict[str, int]
) -> None:
    step = await make_step(make, world)
    base = {"enrollment_id": world["enrollment"], "assessment_type": "topic", "path_step_id": step}

    first = await make("assessment-attempts", {**base, "score": 60})
    assert (first["attempt_number"], first["passed"]) == (1, False)
    second = await make("assessment-attempts", {**base, "score": 70})
    assert (second["attempt_number"], second["passed"]) == (2, True)

    regraded = await client.patch(f"{ATTEMPTS}/{first['id']}", json={"score": 95})
    assert regraded.json()["passed"] is True

    passed_only = await client.get(ATTEMPTS, params={"passed": "true"})
    assert passed_only.json()["total"] == 2


async def test_attempts_stop_at_the_max_of_the_path(
    client: httpx.AsyncClient, make: MakeFn, world: dict[str, int]
) -> None:
    step = await make_step(make, world)
    await client.patch(f"/api/v1/learning-paths/{world['path']}", json={"max_attempts": 2})
    base = {"enrollment_id": world["enrollment"], "assessment_type": "topic", "path_step_id": step}
    await make("assessment-attempts", base)
    await make("assessment-attempts", base)
    third = await client.post(ATTEMPTS, json=base)
    assert third.status_code == 422
    assert third.json()["code"] == "MAX_ATTEMPTS_EXCEEDED"


async def test_step_from_another_enrollment_is_rejected(
    client: httpx.AsyncClient, make: MakeFn, world: dict[str, int]
) -> None:
    step = await make_step(make, world)
    other_student = await make("users", {"full_name": "Otro", "email": "otro@example.com"})
    other_enrollment = await make(
        "enrollments", {"user_id": other_student["id"], "learning_path_id": world["path"]}
    )
    response = await client.post(
        ATTEMPTS,
        json={
            "enrollment_id": other_enrollment["id"],
            "assessment_type": "topic",
            "path_step_id": step,
        },
    )
    assert response.status_code == 422
    assert response.json()["code"] == "STEP_ENROLLMENT_MISMATCH"


async def test_a_topic_attempt_needs_a_step_and_a_final_cannot_have_one(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    topic_without_step = await client.post(
        ATTEMPTS, json={"enrollment_id": world["enrollment"], "assessment_type": "topic"}
    )
    assert topic_without_step.status_code == 422


async def test_badge_is_issued_only_after_passing_the_final(
    client: httpx.AsyncClient, make: MakeFn, world: dict[str, int]
) -> None:
    body = {"enrollment_id": world["enrollment"]}
    too_early = await client.post("/api/v1/badges", json=body)
    assert too_early.status_code == 422
    assert too_early.json()["code"] == "FINAL_ASSESSMENT_NOT_PASSED"

    await make("assessment-attempts", {**body, "assessment_type": "final", "score": 79})
    still_no = await client.post("/api/v1/badges", json=body)
    assert still_no.status_code == 422

    await make("assessment-attempts", {**body, "assessment_type": "final", "score": 90})
    badge = await client.post(
        "/api/v1/badges",
        json={**body, "open_badges_metadata": {"@context": "https://w3id.org/openbadges/v2"}},
    )
    assert badge.status_code == 201
    assert badge.json()["issued_at"].endswith("-05:00")

    again = await client.post("/api/v1/badges", json=body)
    assert again.status_code == 409
    assert again.json()["code"] == "BADGE_ALREADY_ISSUED"
