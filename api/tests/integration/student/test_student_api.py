from typing import Any

import httpx
import pytest

from tests.integration.conftest import ClientFactory, MakeFn

pytestmark = pytest.mark.integration

ME = "/api/v1/me"


async def course_and_path(make: MakeFn) -> dict[str, int]:
    teacher = await make("users", {"full_name": "Docente", "email": "docente@example.com"})
    course = await make("courses", {"owner_user_id": teacher["id"], "name": "Ciencia de datos"})
    topic = await make("topics", {"course_id": course["id"], "name": "Regresión"})
    path = await make("learning-paths", {"course_id": course["id"], "name": "Ruta base"})
    return {"course": course["id"], "topic": topic["id"], "path": path["id"]}


async def enroll(student: httpx.AsyncClient, path_id: int, **extra: Any) -> dict[str, Any]:
    response = await student.post(f"{ME}/enrollments", json={"learning_path_id": path_id, **extra})
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


# --- inscripciones ----------------------------------------------------------------------------


async def test_unauthenticated_requests_are_401(bare_client: httpx.AsyncClient) -> None:
    for path in (f"{ME}/enrollments", f"{ME}/enrollments/1/steps", f"{ME}/enrollments/1/badge"):
        assert (await bare_client.get(path)).status_code == 401


async def test_a_student_enrolls_and_sees_only_their_own_enrollments(
    client_for: ClientFactory, make: MakeFn
) -> None:
    ids = await course_and_path(make)
    ana = client_for(sub="ana-sub", email="ana@example.com")
    luis = client_for(sub="luis-sub", email="luis@example.com")

    mine = await enroll(
        ana, ids["path"], profile_description="Ingeniera", personal_objective="Aprender"
    )
    assert mine["status"] == "enrolled"
    assert mine["profile_description"] == "Ingeniera"
    me = (await ana.get("/api/v1/me")).json()
    assert mine["user_id"] == me["id"]  # el usuario sale del token

    assert (await ana.get(f"{ME}/enrollments")).json()["total"] == 1
    assert (await luis.get(f"{ME}/enrollments")).json()["total"] == 0  # no ve la de Ana
    assert (await luis.get(f"{ME}/enrollments/{mine['id']}")).status_code == 404  # ni por id


async def test_the_user_cannot_be_chosen_in_the_request(
    client_for: ClientFactory, make: MakeFn
) -> None:
    ids = await course_and_path(make)
    ana = client_for(sub="ana-sub", email="ana@example.com")
    response = await ana.post(
        f"{ME}/enrollments", json={"learning_path_id": ids["path"], "user_id": 1}
    )
    assert response.status_code == 422


async def test_enrolling_twice_in_the_same_path_is_a_conflict(
    client_for: ClientFactory, make: MakeFn
) -> None:
    ids = await course_and_path(make)
    ana = client_for(sub="ana-sub", email="ana@example.com")
    await enroll(ana, ids["path"])
    again = await ana.post(f"{ME}/enrollments", json={"learning_path_id": ids["path"]})
    assert again.status_code == 409
    assert again.json()["code"] == "ALREADY_ENROLLED"


async def test_unknown_or_inactive_paths_cannot_be_enrolled(
    client_for: ClientFactory, client: httpx.AsyncClient, make: MakeFn
) -> None:
    ids = await course_and_path(make)
    ana = client_for(sub="ana-sub", email="ana@example.com")
    assert (await ana.post(f"{ME}/enrollments", json={"learning_path_id": 999})).status_code == 404
    await client.patch(f"/api/v1/learning-paths/{ids['path']}/deactivate")
    inactive = await ana.post(f"{ME}/enrollments", json={"learning_path_id": ids["path"]})
    assert inactive.status_code == 404


async def test_profile_update_and_abandon(client_for: ClientFactory, make: MakeFn) -> None:
    ids = await course_and_path(make)
    ana = client_for(sub="ana-sub", email="ana@example.com")
    mine = await enroll(ana, ids["path"])

    updated = await ana.patch(
        f"{ME}/enrollments/{mine['id']}", json={"personal_objective": "Dominar la regresión"}
    )
    assert updated.status_code == 200
    assert updated.json()["personal_objective"] == "Dominar la regresión"
    # el estudiante no puede cambiar su estado ni otros campos por esta vía
    assert (
        await ana.patch(f"{ME}/enrollments/{mine['id']}", json={"status": "completed"})
    ).status_code == 422

    left = await ana.patch(f"{ME}/enrollments/{mine['id']}/abandon")
    assert left.json()["status"] == "abandoned"
    closed = await ana.patch(f"{ME}/enrollments/{mine['id']}", json={"personal_objective": "x"})
    assert closed.status_code == 422
    assert closed.json()["code"] == "ENROLLMENT_CLOSED"


async def test_other_students_cannot_touch_my_enrollment(
    client_for: ClientFactory, make: MakeFn
) -> None:
    ids = await course_and_path(make)
    ana = client_for(sub="ana-sub", email="ana@example.com")
    luis = client_for(sub="luis-sub", email="luis@example.com")
    mine = await enroll(ana, ids["path"])
    base = f"{ME}/enrollments/{mine['id']}"
    assert (await luis.patch(base, json={"personal_objective": "hackeado"})).status_code == 404
    assert (await luis.patch(f"{base}/abandon")).status_code == 404
    assert (await luis.get(f"{base}/steps")).status_code == 404
    assert (await luis.get(f"{base}/diagnostic")).status_code == 404
    assert (await luis.get(f"{base}/attempts")).status_code == 404
    assert (await luis.get(f"{base}/badge")).status_code == 404
    assert (await ana.get(base)).json()["personal_objective"] is None  # intacta


async def test_a_teacher_can_also_use_the_student_endpoints_for_their_own_data(
    client_for: ClientFactory, make: MakeFn, engine: Any
) -> None:
    from tests.integration.conftest import insert_user

    ids = await course_and_path(make)
    await insert_user(engine, email="profe@example.com", role="teacher", sub="profe-sub")
    teacher = client_for(sub="profe-sub", email="profe@example.com")
    assert (
        await teacher.post(f"{ME}/enrollments", json={"learning_path_id": ids["path"]})
    ).status_code == 201


# --- ruta, diagnóstico, intentos y badge ------------------------------------------------------


async def test_my_steps_in_order(client_for: ClientFactory, make: MakeFn) -> None:
    ids = await course_and_path(make)
    second = await make("topics", {"course_id": ids["course"], "name": "Clasificación"})
    ana = client_for(sub="ana-sub", email="ana@example.com")
    mine = await enroll(ana, ids["path"])
    await make(
        "path-steps", {"enrollment_id": mine["id"], "topic_id": second["id"], "step_order": 2}
    )
    await make(
        "path-steps", {"enrollment_id": mine["id"], "topic_id": ids["topic"], "step_order": 1}
    )

    steps = (await ana.get(f"{ME}/enrollments/{mine['id']}/steps")).json()
    assert steps["total"] == 2
    assert [s["step_order"] for s in steps["items"]] == [1, 2]


async def test_diagnostic_read_and_single_submission(
    client_for: ClientFactory, make: MakeFn
) -> None:
    ids = await course_and_path(make)
    ana = client_for(sub="ana-sub", email="ana@example.com")
    mine = await enroll(ana, ids["path"])
    base = f"{ME}/enrollments/{mine['id']}/diagnostic"

    assert (await ana.get(base)).status_code == 404  # aún no se generó
    await make(
        "diagnostics",
        {"enrollment_id": mine["id"], "questions": [{"id": 1, "text": "¿Qué es la varianza?"}]},
    )
    assert (await ana.get(base)).json()["questions"][0]["id"] == 1

    sent = await ana.patch(f"{base}/answers", json={"answers": {"1": "La dispersión"}})
    assert sent.status_code == 200
    assert sent.json()["answers"] == {"1": "La dispersión"}
    assert sent.json()["completed_at"].endswith("-05:00")
    again = await ana.patch(f"{base}/answers", json={"answers": {"1": "otra"}})
    assert again.status_code == 409
    assert again.json()["code"] == "ALREADY_SUBMITTED"


async def test_attempt_submission_never_lets_the_student_grade_themselves(
    client_for: ClientFactory, make: MakeFn
) -> None:
    ids = await course_and_path(make)
    ana = client_for(sub="ana-sub", email="ana@example.com")
    mine = await enroll(ana, ids["path"])
    step = await make(
        "path-steps", {"enrollment_id": mine["id"], "topic_id": ids["topic"], "step_order": 1}
    )
    attempt = await make(
        "assessment-attempts",
        {
            "enrollment_id": mine["id"],
            "assessment_type": "topic",
            "path_step_id": step["id"],
            "questions": [{"id": 1}],
        },
    )
    base = f"{ME}/enrollments/{mine['id']}/attempts"

    listing = (await ana.get(base)).json()
    assert listing["total"] == 1
    assert listing["items"][0]["id"] == attempt["id"]

    cheat = await ana.patch(f"{base}/{attempt['id']}/submit", json={"answers": ["a"], "score": 100})
    assert cheat.status_code == 422  # el puntaje no es un campo permitido

    sent = await ana.patch(f"{base}/{attempt['id']}/submit", json={"answers": ["a", "b"]})
    assert sent.status_code == 200
    body = sent.json()
    assert body["answers"] == ["a", "b"]
    assert body["submitted_at"].endswith("-05:00")
    assert body["score"] is None
    assert body["passed"] is None
    assert (
        await ana.patch(f"{base}/{attempt['id']}/submit", json={"answers": ["z"]})
    ).status_code == 409


async def test_cannot_submit_an_attempt_of_someone_elses_enrollment(
    client_for: ClientFactory, client: httpx.AsyncClient, make: MakeFn
) -> None:
    ids = await course_and_path(make)
    ana = client_for(sub="ana-sub", email="ana@example.com")
    luis = client_for(sub="luis-sub", email="luis@example.com")
    ana_enrollment = await enroll(ana, ids["path"])
    luis_enrollment = await enroll(luis, ids["path"])
    attempt = await make(
        "assessment-attempts", {"enrollment_id": ana_enrollment["id"], "assessment_type": "final"}
    )
    # Luis intenta entregar el intento de Ana, por su propia inscripción y por la de ella
    for enrollment_id in (luis_enrollment["id"], ana_enrollment["id"]):
        response = await luis.patch(
            f"{ME}/enrollments/{enrollment_id}/attempts/{attempt['id']}/submit",
            json={"answers": ["x"]},
        )
        assert response.status_code == 404
    untouched = (await client.get(f"/api/v1/assessment-attempts/{attempt['id']}")).json()
    assert untouched["answers"] is None


async def test_badge_visible_only_to_its_owner(client_for: ClientFactory, make: MakeFn) -> None:
    ids = await course_and_path(make)
    ana = client_for(sub="ana-sub", email="ana@example.com")
    luis = client_for(sub="luis-sub", email="luis@example.com")
    mine = await enroll(ana, ids["path"])
    base = f"{ME}/enrollments/{mine['id']}/badge"

    assert (await ana.get(base)).status_code == 404  # todavía no la aprobó
    await make(
        "assessment-attempts",
        {"enrollment_id": mine["id"], "assessment_type": "final", "score": 90},
    )
    await make("badges", {"enrollment_id": mine["id"]})
    assert (await ana.get(base)).json()["enrollment_id"] == mine["id"]
    assert (await luis.get(base)).status_code == 404


async def test_student_endpoints_do_not_open_the_staff_crud(client_for: ClientFactory) -> None:
    ana = client_for(sub="ana-sub", email="ana@example.com")
    assert (await ana.get("/api/v1/enrollments")).status_code == 403
    assert (await ana.get("/api/v1/assessment-attempts")).status_code == 403
