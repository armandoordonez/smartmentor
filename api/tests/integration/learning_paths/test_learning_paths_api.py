import httpx
import pytest

from tests.integration.conftest import MakeFn

pytestmark = pytest.mark.integration


async def test_learning_path_defaults_match_the_brief(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    path = (await client.get(f"/api/v1/learning-paths/{world['path']}")).json()
    assert path["topic_pass_threshold"] == 70
    assert path["final_pass_threshold"] == 80
    assert path["mastery_skip_threshold"] == 80
    assert path["max_attempts"] == 3


async def test_thresholds_outside_0_100_are_rejected(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    response = await client.patch(
        f"/api/v1/learning-paths/{world['path']}", json={"final_pass_threshold": 120}
    )
    assert response.status_code == 422


async def test_a_student_can_enroll_only_once_per_path(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    again = await client.post(
        "/api/v1/enrollments",
        json={"user_id": world["student"], "learning_path_id": world["path"]},
    )
    assert again.status_code == 409
    assert again.json()["code"] == "ALREADY_ENROLLED"


async def test_enrollment_profile_and_status(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    updated = await client.patch(
        f"/api/v1/enrollments/{world['enrollment']}",
        json={
            "profile_description": "Ingeniero con experiencia en estadística",
            "profile_embedding": [0.01] * 1024,
            "status": "in_progress",
        },
    )
    assert updated.status_code == 200
    body = updated.json()
    assert body["status"] == "in_progress"
    assert body["has_profile_embedding"] is True
    assert "profile_embedding" not in body


async def test_path_step_topic_must_belong_to_the_path_course(
    client: httpx.AsyncClient, make: MakeFn, world: dict[str, int]
) -> None:
    other = await make("courses", {"owner_user_id": world["teacher"], "name": "Otro"})
    foreign = await make("topics", {"course_id": other["id"], "name": "Ajeno"})
    response = await client.post(
        "/api/v1/path-steps",
        json={"enrollment_id": world["enrollment"], "topic_id": foreign["id"], "step_order": 1},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "TOPIC_NOT_IN_PATH_COURSE"


async def test_path_step_order_and_topic_are_unique_per_enrollment(
    client: httpx.AsyncClient, make: MakeFn, world: dict[str, int]
) -> None:
    await make(
        "path-steps",
        {"enrollment_id": world["enrollment"], "topic_id": world["topic"], "step_order": 1},
    )
    second_topic = await make("topics", {"course_id": world["course"], "name": "Segundo"})

    same_topic = await client.post(
        "/api/v1/path-steps",
        json={"enrollment_id": world["enrollment"], "topic_id": world["topic"], "step_order": 2},
    )
    assert same_topic.json()["code"] == "TOPIC_ALREADY_IN_PATH"

    same_order = await client.post(
        "/api/v1/path-steps",
        json={
            "enrollment_id": world["enrollment"],
            "topic_id": second_topic["id"],
            "step_order": 1,
        },
    )
    assert same_order.status_code == 409
    assert same_order.json()["code"] == "STEP_ORDER_TAKEN"
