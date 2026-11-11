"""Evaluación humana contra el esquema real: evaluadores, anotación ciega y calificación a mano."""

from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from app.domains.ai_gateway.fake import FakeAiService
from tests.integration.conftest import ClientFactory
from tests.integration.world_content import (
    API,
    Course,
    assign_evaluator,
    ingest_quiz_bank,
    insert_enrollment,
    insert_short_answer,
    make_course,
    make_instructor,
    make_learner,
)

pytestmark = pytest.mark.integration


@pytest.fixture
async def course(engine: AsyncEngine, client_for: ClientFactory) -> Course:
    owner, owner_id = await make_instructor(engine, client_for, "duena")
    return await make_course(owner, owner_id)


@pytest.fixture
async def evaluators(
    engine: AsyncEngine, client_for: ClientFactory, course: Course, client: httpx.AsyncClient
) -> tuple[httpx.AsyncClient, httpx.AsyncClient]:
    """Dos instructores asignados como evaluadores del curso."""
    first, first_id = await make_instructor(engine, client_for, "eval-uno")
    second, second_id = await make_instructor(engine, client_for, "eval-dos")
    for evaluator_id in (first_id, second_id):
        assigned = await assign_evaluator(client, course, evaluator_id)
        assert assigned.status_code == 201, assigned.text
    return first, second


async def first_item(course: Course, ai: FakeAiService) -> dict[str, Any]:
    await ingest_quiz_bank(ai, course, course.topic_ids[0])
    items = (await course.owner.get(f"{API}/topics/{course.topic_ids[0]}/items")).json()["items"]
    return dict(items[0])


# --- evaluadores por curso --------------------------------------------------------------------


async def test_only_the_admin_assigns_evaluators_and_the_owner_cannot_be_one(
    course: Course, client: httpx.AsyncClient, engine: AsyncEngine, client_for: ClientFactory
) -> None:
    _, other_id = await make_instructor(engine, client_for, "otro-doc")
    learner, learner_id = await make_learner(engine, client_for, "aprendiz")
    assert (await assign_evaluator(course.owner, course, other_id)).status_code == 403
    assert (await assign_evaluator(client, course, course.owner_id)).status_code == 422
    assert (await assign_evaluator(client, course, learner_id)).status_code == 422
    assert (await assign_evaluator(client, course, 99999)).status_code in (404, 422)
    created = await assign_evaluator(client, course, other_id)
    assert created.status_code == 201
    assert (await assign_evaluator(client, course, other_id)).status_code == 409
    listed = await client.get(f"{API}/courses/{course.id}/evaluators")
    assert [e["user_id"] for e in listed.json()] == [other_id]
    removed = await client.patch(f"{API}/course-evaluators/{created.json()['id']}/deactivate")
    assert removed.status_code == 200
    assert (await client.get(f"{API}/courses/{course.id}/evaluators")).json() == []
    again = await assign_evaluator(client, course, other_id)  # se reactiva
    assert again.status_code == 201
    _ = learner


# --- anotación ciega --------------------------------------------------------------------------

ANNOTATION = {
    "single_correct": True,
    "clear_stem": True,
    "bloom_ok": False,
    "plausible_distractors": True,
    "verdict": "valid",
}


async def test_the_blind_annotation_never_shows_the_other_evaluators_work(
    course: Course,
    ai: FakeAiService,
    evaluators: tuple[httpx.AsyncClient, httpx.AsyncClient],
) -> None:
    first, second = evaluators
    item = await first_item(course, ai)

    queue = await first.get(f"{API}/evaluation/annotation-queue")
    assert queue.status_code == 200
    assert queue.json()["total"] == 5
    assert queue.json()["items"][0]["correct_option"] is not None

    mine = await first.post(
        f"{API}/items/{item['id']}/annotations",
        json={**ANNOTATION, "comment": "SECRETO-DEL-PRIMERO", "verdict": "invalid"},
    )
    assert mine.status_code == 201, mine.text
    assert mine.json()["evaluator_slot"] == 1

    # Para el segundo evaluador el ítem sigue pendiente y no hay rastro del primero.
    pending = await second.get(f"{API}/evaluation/annotation-queue")
    assert pending.json()["total"] == 5
    assert "SECRETO-DEL-PRIMERO" not in pending.text
    assert all(i["own_annotation"] is None for i in pending.json()["items"])
    theirs = await second.post(f"{API}/items/{item['id']}/annotations", json=ANNOTATION)
    assert theirs.status_code == 201
    assert theirs.json()["evaluator_slot"] == 2
    assert "SECRETO-DEL-PRIMERO" not in theirs.text

    # Cada uno ve solo lo suyo en «ya anotados».
    done_second = await second.get(f"{API}/evaluation/annotation-queue", params={"done": True})
    assert done_second.json()["total"] == 1
    assert "SECRETO-DEL-PRIMERO" not in done_second.text
    assert done_second.json()["items"][0]["own_annotation"]["verdict"] == "valid"
    done_first = await first.get(f"{API}/evaluation/annotation-queue", params={"done": True})
    assert done_first.json()["items"][0]["own_annotation"]["verdict"] == "invalid"
    # Con los dos cupos llenos el ítem sale de la cola pendiente.
    assert (await first.get(f"{API}/evaluation/annotation-queue")).json()["total"] == 4


async def test_annotation_conflicts_and_full_slots(
    course: Course,
    ai: FakeAiService,
    evaluators: tuple[httpx.AsyncClient, httpx.AsyncClient],
    engine: AsyncEngine,
    client_for: ClientFactory,
    client: httpx.AsyncClient,
) -> None:
    first, second = evaluators
    item = await first_item(course, ai)
    path = f"{API}/items/{item['id']}/annotations"
    assert (await first.post(path, json=ANNOTATION)).status_code == 201
    repeated = await first.post(path, json=ANNOTATION)
    assert repeated.status_code == 409
    assert repeated.json()["code"] == "ANNOTATION_ALREADY_EXISTS"
    assert (await second.post(path, json=ANNOTATION)).status_code == 201

    third, third_id = await make_instructor(engine, client_for, "eval-tres")
    await assign_evaluator(client, course, third_id)
    full = await third.post(path, json=ANNOTATION)
    assert full.status_code == 409
    assert full.json()["code"] == "EVALUATOR_SLOTS_FULL"
    assert (await first.post(path, json={"verdict": "maybe"})).status_code == 422


async def test_only_assigned_evaluators_annotate_and_the_owner_does_not_evaluate_own_items(
    course: Course,
    ai: FakeAiService,
    evaluators: tuple[httpx.AsyncClient, httpx.AsyncClient],
    engine: AsyncEngine,
    client_for: ClientFactory,
    client: httpx.AsyncClient,
) -> None:
    item = await first_item(course, ai)
    path = f"{API}/items/{item['id']}/annotations"
    # El dueño: 403 EVALUATOR_NOT_ASSIGNED en la cola y al anotar.
    for response in (
        await course.owner.get(f"{API}/evaluation/annotation-queue"),
        await course.owner.post(path, json=ANNOTATION),
        await client.post(path, json=ANNOTATION),
    ):
        assert response.status_code in (403,), response.text
    assert (await course.owner.post(path, json=ANNOTATION)).json()[
        "code"
    ] == "EVALUATOR_NOT_ASSIGNED"
    # Un instructor sin asignación: el ítem no existe para él (404) y la cola le dice que no.
    stranger, _ = await make_instructor(engine, client_for, "extrano")
    missing = await stranger.post(path, json=ANNOTATION)
    assert missing.status_code == 404
    assert missing.json()["code"] == "ITEM_NOT_FOUND"
    queue = await stranger.get(f"{API}/evaluation/annotation-queue")
    assert queue.status_code == 403
    assert queue.json()["code"] == "EVALUATOR_NOT_ASSIGNED"
    # Un evaluador no puede pedir otro curso.
    first, _ = await make_instructor(engine, client_for, "eval-cuatro")
    other_course = await client.get(f"{API}/evaluation/annotation-queue")
    assert other_course.status_code == 403  # el admin no es instructor
    _ = first
    learner, _ = await make_learner(engine, client_for, "aprendiz")
    assert (await learner.get(f"{API}/evaluation/annotation-queue")).status_code == 403
    assert (await learner.post(path, json=ANNOTATION)).status_code == 403


async def test_a_retired_item_is_not_annotatable(
    course: Course,
    ai: FakeAiService,
    evaluators: tuple[httpx.AsyncClient, httpx.AsyncClient],
) -> None:
    first, _ = evaluators
    item = await first_item(course, ai)
    await course.owner.patch(f"{API}/items/{item['id']}", json={"review_status": "retired"})
    response = await first.post(f"{API}/items/{item['id']}/annotations", json=ANNOTATION)
    assert response.status_code == 409
    assert (await first.get(f"{API}/evaluation/annotation-queue")).json()["total"] == 4


# --- calificación humana ----------------------------------------------------------------------


async def test_the_llm_grade_is_returned_only_after_the_human_grade_is_saved(
    course: Course,
    ai: FakeAiService,
    evaluators: tuple[httpx.AsyncClient, httpx.AsyncClient],
    engine: AsyncEngine,
    client_for: ClientFactory,
) -> None:
    first, second = evaluators
    items = await first_item(course, ai)
    all_items = (await course.owner.get(f"{API}/topics/{course.topic_ids[0]}/items")).json()[
        "items"
    ]
    short = [i for i in all_items if i["item_type"] == "short_answer"]
    assert items
    _, learner_id = await make_learner(engine, client_for, "aprendiz")
    enrollment = await insert_enrollment(engine, learner_id, course.path_id)
    plain = await insert_short_answer(engine, enrollment, short[0]["id"], text_answer="Texto A")
    asked = await insert_short_answer(
        engine, enrollment, short[1]["id"], text_answer="Texto B", review_requested=True
    )

    random_queue = await first.get(f"{API}/evaluation/grading-queue", params={"sample": "random"})
    assert random_queue.status_code == 200
    assert random_queue.json()["total"] == 2
    entry = random_queue.json()["items"][0]
    assert entry["topic_name"]
    assert random_queue.json()["graded"] == 0
    for forbidden in ("score", "feedback", "is_correct", "rubric_detail", "llm"):
        assert forbidden not in entry
    assert "66.67" not in random_queue.text

    requested = await first.get(
        f"{API}/evaluation/grading-queue", params={"sample": "learner_request"}
    )
    assert [e["attempt_answer_id"] for e in requested.json()["items"]] == [asked]

    body = {
        "criteria": [{"criterion": "Define el concepto", "met": True, "points_awarded": 0.5}],
        "score": 50,
        "sample_type": "random",
    }
    saved = await first.post(f"{API}/attempt-answers/{plain}/human-gradings", json=body)
    assert saved.status_code == 201, saved.text
    assert saved.json()["llm_grading"]["score"] == 66.67
    assert saved.json()["llm_grading"]["feedback"] == "Bien"
    again = await first.post(f"{API}/attempt-answers/{plain}/human-gradings", json=body)
    assert again.status_code == 409
    assert again.json()["code"] == "HUMAN_GRADING_ALREADY_EXISTS"
    # Ya calificada por mí: sale de mi cola y cuenta como hecha; el segundo aún la ve.
    mine = (await first.get(f"{API}/evaluation/grading-queue")).json()
    assert (mine["total"], mine["graded"]) == (1, 1)
    assert (await second.get(f"{API}/evaluation/grading-queue")).json()["total"] == 2
    # Una muestra «a solicitud» exige que el aprendiz la haya pedido.
    wrong = await second.post(
        f"{API}/attempt-answers/{plain}/human-gradings",
        json={**body, "sample_type": "learner_request"},
    )
    assert wrong.status_code == 422
    right = await second.post(
        f"{API}/attempt-answers/{asked}/human-gradings",
        json={**body, "sample_type": "learner_request"},
    )
    assert right.status_code == 201
    invalid = await second.post(
        f"{API}/attempt-answers/{asked}/human-gradings", json={**body, "score": 120}
    )
    assert invalid.status_code == 422


async def test_grading_is_closed_to_those_who_are_not_evaluators_of_that_course(
    course: Course,
    ai: FakeAiService,
    evaluators: tuple[httpx.AsyncClient, httpx.AsyncClient],
    engine: AsyncEngine,
    client_for: ClientFactory,
    client: httpx.AsyncClient,
) -> None:
    await first_item(course, ai)
    short = next(
        i
        for i in (await course.owner.get(f"{API}/topics/{course.topic_ids[0]}/items")).json()[
            "items"
        ]
        if i["item_type"] == "short_answer"
    )
    _, learner_id = await make_learner(engine, client_for, "aprendiz")
    enrollment = await insert_enrollment(engine, learner_id, course.path_id)
    answer = await insert_short_answer(engine, enrollment, short["id"])
    body = {
        "criteria": [{"criterion": "x", "met": True, "points_awarded": 1}],
        "score": 80,
        "sample_type": "random",
    }
    path = f"{API}/attempt-answers/{answer}/human-gradings"

    # El dueño del curso no califica las respuestas de su propio curso.
    owner = await course.owner.post(path, json=body)
    assert owner.status_code == 403
    assert owner.json()["code"] == "EVALUATOR_NOT_ASSIGNED"
    assert (await course.owner.get(f"{API}/evaluation/grading-queue")).status_code == 403
    # Un evaluador de otro curso no la ve: 404.
    other_owner, other_owner_id = await make_instructor(engine, client_for, "duena-dos")
    other_course = await make_course(other_owner, other_owner_id)
    elsewhere, elsewhere_id = await make_instructor(engine, client_for, "eval-ajeno")
    await assign_evaluator(client, other_course, elsewhere_id)
    assert (await elsewhere.post(path, json=body)).status_code == 404
    assert (await elsewhere.get(f"{API}/evaluation/grading-queue")).json()["total"] == 0
    assert (
        await elsewhere.post(f"{API}/attempt-answers/99999/human-gradings", json=body)
    ).status_code == 404
    _ = elsewhere_id
