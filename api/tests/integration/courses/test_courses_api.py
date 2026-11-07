"""Flujo del instructor contra la base: curso, syllabus, revisión y publicación."""

import uuid
from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.domains.ai_gateway.fake import FakeAiService
from tests.integration.conftest import ClientFactory, insert_user
from tests.pdf_helpers import blank_pdf, text_pdf

pytestmark = pytest.mark.integration

API = "/api/v1"
TEXT = {"text": "Tema 1 fundamentos. Tema 2 regresión lineal. Tema 3 regresión logística."}


def key() -> dict[str, str]:
    return {"Idempotency-Key": str(uuid.uuid4())}


@pytest.fixture
async def instructor(client_for: ClientFactory, engine: AsyncEngine) -> httpx.AsyncClient:
    await insert_user(engine, email="doc@example.com", role="instructor", sub="doc-sub")
    return client_for(sub="doc-sub", email="doc@example.com")


@pytest.fixture
async def other_instructor(client_for: ClientFactory, engine: AsyncEngine) -> httpx.AsyncClient:
    await insert_user(engine, email="otro@example.com", role="instructor", sub="otro-sub")
    return client_for(sub="otro-sub", email="otro@example.com")


async def create_course(http: httpx.AsyncClient, name: str = "Machine Learning") -> dict[str, Any]:
    response = await http.post(
        f"{API}/courses",
        json={"name": name, "description": "Base", "learning_path": {"group_label": "Piloto"}},
    )
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


async def review_ready_course(http: httpx.AsyncClient) -> int:
    course = await create_course(http)
    uploaded = await http.post(f"{API}/courses/{course['id']}/syllabus", json=TEXT, headers=key())
    assert uploaded.status_code == 202, uploaded.text
    polled = await http.get(f"{API}/jobs/{uploaded.json()['job_id']}")
    assert polled.json()["ingested"] is True
    return int(course["id"])


# --- cursos -----------------------------------------------------------------------------------


async def test_create_and_read_a_course_with_its_learning_path(
    instructor: httpx.AsyncClient,
) -> None:
    course = await create_course(instructor)
    assert course["status"] == "draft"
    assert course["learning_path"]["name"] == "Machine Learning"
    assert course["learning_path"]["group_label"] == "Piloto"
    assert course["learning_path"]["status"] == "draft"
    fetched = (await instructor.get(f"{API}/courses/{course['id']}")).json()
    assert fetched["id"] == course["id"]
    updated = await instructor.patch(f"{API}/courses/{course['id']}", json={"name": "ML 2"})
    assert updated.json()["name"] == "ML 2"
    assert updated.json()["description"] == "Base"


async def test_listing_is_scoped_to_the_instructor_and_filterable(
    instructor: httpx.AsyncClient, other_instructor: httpx.AsyncClient, client: httpx.AsyncClient
) -> None:
    await create_course(instructor, "Mío")
    await create_course(other_instructor, "Ajeno")
    mine = (await instructor.get(f"{API}/courses")).json()
    assert [c["name"] for c in mine["items"]] == ["Mío"]
    assert (await client.get(f"{API}/courses")).json()["total"] == 2
    assert (await client.get(f"{API}/courses", params={"status": "published"})).json()["total"] == 0
    assert (await client.get(f"{API}/courses", params={"limit": 101})).status_code == 422


async def test_admin_assigns_and_unassigns_the_owner(
    client: httpx.AsyncClient, instructor: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    course = await create_course(client)  # un administrador puro: «Sin asignar»
    assert course["owner_user_id"] is None
    assert (await instructor.get(f"{API}/courses/{course['id']}")).status_code == 404
    async with engine.connect() as conn:
        owner = (
            await conn.execute(text("SELECT id FROM users WHERE email='doc@example.com'"))
        ).scalar_one()
    assigned = await client.patch(
        f"{API}/courses/{course['id']}/owner", json={"owner_user_id": owner}
    )
    assert assigned.json()["owner_user_id"] == owner
    assert (await instructor.get(f"{API}/courses/{course['id']}")).status_code == 200
    bad = await client.patch(f"{API}/courses/{course['id']}/owner", json={"owner_user_id": 9999})
    assert (bad.status_code, bad.json()["code"]) == (422, "OWNER_NOT_FOUND")
    assert (
        await client.patch(f"{API}/courses/{course['id']}/owner", json={"owner_user_id": None})
    ).json()["owner_user_id"] is None


# --- syllabus ---------------------------------------------------------------------------------


async def test_a_text_syllabus_runs_the_whole_extraction(
    instructor: httpx.AsyncClient, ai: FakeAiService
) -> None:
    course = await create_course(instructor)
    uploaded = await instructor.post(
        f"{API}/courses/{course['id']}/syllabus", json=TEXT, headers=key()
    )
    assert uploaded.status_code == 202
    accepted = uploaded.json()
    assert accepted["status"] == "queued"
    assert accepted["poll_url"] == f"/api/v1/jobs/{accepted['job_id']}"
    assert uploaded.headers["location"] == accepted["poll_url"]
    assert (await instructor.get(f"{API}/courses/{course['id']}")).json()["status"] == "extracting"

    polled = (await instructor.get(accepted["poll_url"])).json()
    assert polled["status"] == "succeeded"
    assert polled["ingested"] is True
    fetched = (await instructor.get(f"{API}/courses/{course['id']}")).json()
    assert fetched["status"] == "in_review"
    assert fetched["extraction_error_code"] is None

    topics = (await instructor.get(f"{API}/courses/{course['id']}/topics")).json()
    assert [t["name"] for t in topics["topics"]] == [
        "Fundamentos",
        "Regresión lineal",
        "Regresión logística",
    ]
    assert topics["review_counts"] == {"unchanged": 3, "corrected": 0, "added": 0, "deleted": 0}
    assert topics["topics"][2]["learning_outcomes"][0]["code"] == "lo_logistic_regression_1"
    assert len(ai.submitted) == 1


async def test_a_pdf_syllabus_is_extracted_by_the_api_before_queuing(
    instructor: httpx.AsyncClient, engine: AsyncEngine, ai: FakeAiService
) -> None:
    course = await create_course(instructor)
    response = await instructor.post(
        f"{API}/courses/{course['id']}/syllabus",
        files={
            "file": ("plan.pdf", text_pdf("Introduccion a Machine Learning"), "application/pdf")
        },
        headers=key(),
    )
    assert response.status_code == 202, response.text
    async with engine.connect() as conn:
        row = (
            await conn.execute(
                text(
                    "SELECT source_type, file_name, page_count, extracted_char_count, "
                    "extracted_text, length(file_sha256), id FROM syllabus_documents"
                )
            )
        ).one()
    assert row[:3] == ("pdf", "plan.pdf", 1)
    assert row[3] > 20
    assert "Machine Learning" in row[4]
    assert row[5] == 64
    assert ai.submitted[0].input == {"syllabus_document_id": row[6]}


async def test_a_pdf_without_text_is_422_and_nothing_is_queued(
    instructor: httpx.AsyncClient, ai: FakeAiService
) -> None:
    course = await create_course(instructor)
    response = await instructor.post(
        f"{API}/courses/{course['id']}/syllabus",
        files={"file": ("escaneo.pdf", blank_pdf(), "application/pdf")},
        headers=key(),
    )
    assert response.status_code == 422
    assert response.json()["code"] == "SYLLABUS_NO_TEXT"
    assert ai.submitted == []
    assert (await instructor.get(f"{API}/courses/{course['id']}")).json()["status"] == "draft"


@pytest.mark.parametrize(
    ("files", "json_body", "status", "code"),
    [
        (
            {"file": ("a.exe", b"MZ....", "application/octet-stream")},
            None,
            415,
            "SYLLABUS_UNSUPPORTED_TYPE",
        ),
        ({"file": ("a.txt", b"hola", "text/plain")}, None, 415, "SYLLABUS_UNSUPPORTED_TYPE"),
        (None, {"text": "   "}, 422, "VALIDATION_ERROR"),
        (None, {"texto": "x"}, 422, "VALIDATION_ERROR"),
    ],
    ids=["ejecutable", "txt-como-archivo", "texto-vacio", "campo-incorrecto"],
)
async def test_invalid_syllabus_uploads(
    instructor: httpx.AsyncClient,
    files: dict[str, Any] | None,
    json_body: dict[str, Any] | None,
    status: int,
    code: str,
) -> None:
    course = await create_course(instructor)
    response = await instructor.post(
        f"{API}/courses/{course['id']}/syllabus", files=files, json=json_body, headers=key()
    )
    assert (response.status_code, response.json()["code"]) == (status, code)


async def test_a_pdf_over_10_mb_is_413(instructor: httpx.AsyncClient) -> None:
    course = await create_course(instructor)
    big = b"%PDF-1.4\n" + b"0" * (10 * 1024 * 1024 + 1)
    response = await instructor.post(
        f"{API}/courses/{course['id']}/syllabus",
        files={"file": ("grande.pdf", big, "application/pdf")},
        headers=key(),
    )
    assert (response.status_code, response.json()["code"]) == (413, "SYLLABUS_TOO_LARGE")


async def test_idempotency_key_rules_on_the_syllabus(
    instructor: httpx.AsyncClient, ai: FakeAiService
) -> None:
    course = await create_course(instructor)
    url = f"{API}/courses/{course['id']}/syllabus"
    missing = await instructor.post(url, json=TEXT)
    assert (missing.status_code, missing.json()["code"]) == (428, "IDEMPOTENCY_KEY_REQUIRED")
    malformed = await instructor.post(url, json=TEXT, headers={"Idempotency-Key": "no-es-uuid"})
    assert malformed.status_code == 422

    headers = key()
    first = await instructor.post(url, json=TEXT, headers=headers)
    replay = await instructor.post(url, json=TEXT, headers=headers)
    assert replay.status_code == 202
    assert replay.json() == first.json()
    assert replay.headers["idempotent-replayed"] == "true"
    assert len(ai.submitted) == 1  # no se encoló otro trabajo
    reused = await instructor.post(url, json={"text": "Otro programa distinto"}, headers=headers)
    assert (reused.status_code, reused.json()["code"]) == (422, "IDEMPOTENCY_KEY_REUSED")


async def test_a_failed_extraction_is_502_and_the_course_can_try_again(
    instructor: httpx.AsyncClient, ai: FakeAiService
) -> None:
    ai.fail_next("syllabus.structure", code="INVALID_OUTPUT", retryable=True)
    course = await create_course(instructor)
    uploaded = await instructor.post(
        f"{API}/courses/{course['id']}/syllabus", json=TEXT, headers=key()
    )
    polled = await instructor.get(f"{API}/jobs/{uploaded.json()['job_id']}")
    assert polled.status_code == 502
    problem = polled.json()
    assert problem["code"] == "AI_TASK_FAILED"
    assert problem["retryable"] is True
    assert problem["job_id"] == uploaded.json()["job_id"]
    assert problem["request_id"]
    state = (await instructor.get(f"{API}/courses/{course['id']}")).json()
    assert (state["status"], state["extraction_error_code"]) == (
        "extraction_failed",
        "INVALID_OUTPUT",
    )
    retry = await instructor.post(
        f"{API}/courses/{course['id']}/syllabus", json={"text": TEXT["text"] + " v2"}, headers=key()
    )
    assert retry.status_code == 202


async def test_the_ai_service_being_down_is_503_and_keeps_the_course_intact(
    instructor: httpx.AsyncClient, ai: FakeAiService
) -> None:
    course = await create_course(instructor)
    ai.unavailable = True
    response = await instructor.post(
        f"{API}/courses/{course['id']}/syllabus", json=TEXT, headers=key()
    )
    assert response.status_code == 503
    assert response.json()["code"] == "AI_SERVICE_UNAVAILABLE"
    assert response.json()["retryable"] is True
    ai.unavailable = False
    assert (await instructor.get(f"{API}/courses/{course['id']}")).json()["status"] == "draft"
    retried = await instructor.post(
        f"{API}/courses/{course['id']}/syllabus", json=TEXT, headers=key()
    )
    assert retried.status_code == 202


async def test_re_extraction_discards_the_review_only_when_confirmed(
    instructor: httpx.AsyncClient,
) -> None:
    course_id = await review_ready_course(instructor)
    await instructor.post(f"{API}/courses/{course_id}/topics", json={"name": "Extra"})
    refused = await instructor.post(
        f"{API}/courses/{course_id}/extractions",
        json={"confirm_discard_review": False},
        headers=key(),
    )
    assert (refused.status_code, refused.json()["code"]) == (422, "BUSINESS_RULE_VIOLATION")
    accepted = await instructor.post(
        f"{API}/courses/{course_id}/extractions",
        json={"confirm_discard_review": True},
        headers=key(),
    )
    assert accepted.status_code == 202
    await instructor.get(accepted.json()["poll_url"])
    topics = (await instructor.get(f"{API}/courses/{course_id}/topics")).json()
    assert next(t["name"] for t in topics["topics"]) == "Fundamentos"
    assert topics["review_counts"]["added"] == 0  # el tema «Extra» se descartó


# --- temas ------------------------------------------------------------------------------------


async def test_topic_crud_with_outcomes_and_prerequisites_in_one_operation(
    instructor: httpx.AsyncClient,
) -> None:
    course_id = await review_ready_course(instructor)
    topics = (await instructor.get(f"{API}/courses/{course_id}/topics")).json()["topics"]
    first = topics[0]
    created = await instructor.post(
        f"{API}/courses/{course_id}/topics",
        json={
            "name": "Árboles de decisión",
            "subtopics": ["Entropía"],
            "estimated_minutes": 90,
            "bloom_level": "apply",
            "learning_outcomes": [{"statement": "Construir un árbol", "bloom_level": "apply"}],
            "prerequisite_topic_ids": [first["id"]],
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert (body["origin"], body["review_status"]) == ("instructor", "added")
    assert body["prerequisite_topic_ids"] == [first["id"]]
    assert body["learning_outcomes"][0]["code"] == f"lo_t{body['id']}_1"

    edited = await instructor.put(
        f"{API}/topics/{first['id']}",
        json={
            "name": "Fundamentos (revisado)",
            "learning_outcomes": [
                {
                    "id": first["learning_outcomes"][0]["id"],
                    "statement": "Corregido",
                    "bloom_level": "apply",
                },
                {"statement": "Nuevo", "bloom_level": "analyze"},
            ],
        },
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["review_status"] == "corrected"
    assert {o["statement"] for o in edited.json()["learning_outcomes"]} == {"Corregido", "Nuevo"}

    listing = (await instructor.get(f"{API}/courses/{course_id}/topics")).json()
    assert listing["review_counts"] == {"unchanged": 2, "corrected": 1, "added": 1, "deleted": 0}

    gone = await instructor.patch(f"{API}/topics/{body['id']}/deactivate")
    assert gone.json()["review_status"] == "deleted"
    after = (await instructor.get(f"{API}/courses/{course_id}/topics")).json()
    assert after["review_counts"]["deleted"] == 1
    assert body["id"] not in [t["id"] for t in after["topics"]]


async def test_a_prerequisite_cycle_is_422_with_the_closed_path(
    instructor: httpx.AsyncClient,
) -> None:
    course_id = await review_ready_course(instructor)
    topics = {
        t["name"]: t
        for t in (await instructor.get(f"{API}/courses/{course_id}/topics")).json()["topics"]
    }
    fundamentals, linear = topics["Fundamentos"], topics["Regresión lineal"]
    response = await instructor.put(
        f"{API}/topics/{fundamentals['id']}",
        json={"name": "Fundamentos", "prerequisite_topic_ids": [linear["id"]]},
    )
    assert (response.status_code, response.json()["code"]) == (422, "PREREQUISITE_CYCLE")
    cycle = response.json()["cycle"]
    assert cycle[0] == cycle[-1] == fundamentals["id"]
    assert linear["id"] in cycle
    own = await instructor.put(
        f"{API}/topics/{linear['id']}", json={"name": "x", "prerequisite_topic_ids": [linear["id"]]}
    )
    assert own.json()["code"] == "PREREQUISITE_SELF"


async def test_the_topic_graph_lists_nodes_and_edges_from_prerequisite_to_topic(
    instructor: httpx.AsyncClient,
) -> None:
    course_id = await review_ready_course(instructor)
    graph = (await instructor.get(f"{API}/courses/{course_id}/topic-graph")).json()
    by_name = {n["name"]: n["id"] for n in graph["nodes"]}
    assert len(graph["edges"]) == 3
    assert {
        "from": by_name["Fundamentos"],
        "to": by_name["Regresión lineal"],
        "origin": "llm",
    } in graph["edges"]


async def test_extraction_metrics_endpoint(instructor: httpx.AsyncClient) -> None:
    course_id = await review_ready_course(instructor)
    metrics = (await instructor.get(f"{API}/courses/{course_id}/extraction-metrics")).json()
    assert metrics["topics"] == {"precision": 1.0, "recall": 1.0, "f1": 1.0}
    assert metrics["corrections"] == 0
    await instructor.post(f"{API}/courses/{course_id}/topics", json={"name": "Extra"})
    after = (await instructor.get(f"{API}/courses/{course_id}/extraction-metrics")).json()
    assert after["topics"]["recall"] == pytest.approx(0.75)
    assert after["corrections"] == 1


# --- publicación ------------------------------------------------------------------------------


async def test_publication_end_to_end_with_polling(
    instructor: httpx.AsyncClient, ai: FakeAiService
) -> None:
    course_id = await review_ready_course(instructor)
    published = await instructor.post(f"{API}/courses/{course_id}/publish", headers=key())
    assert published.status_code == 202, published.text
    assert (await instructor.get(f"{API}/courses/{course_id}")).json()[
        "status"
    ] == "generating_content"
    submitted = ai.submitted[-1]
    assert submitted.job_type == "course.generate_content"
    assert submitted.input["learning_path_id"] > 0

    polled = (await instructor.get(published.json()["poll_url"])).json()
    assert polled["ingested"] is True
    done = (await instructor.get(f"{API}/courses/{course_id}")).json()
    assert done["status"] == "published"
    assert done["learning_path"]["status"] == "published"
    again = await instructor.get(published.json()["poll_url"])  # idempotente
    assert again.json()["ingested"] is True


async def test_publication_requires_review_state_and_outcomes(
    instructor: httpx.AsyncClient,
) -> None:
    draft = await create_course(instructor)
    early = await instructor.post(f"{API}/courses/{draft['id']}/publish", headers=key())
    assert (early.status_code, early.json()["code"]) == (409, "INVALID_STATE_TRANSITION")

    course_id = await review_ready_course(instructor)
    bare = (
        await instructor.post(f"{API}/courses/{course_id}/topics", json={"name": "Sin resultados"})
    ).json()
    blocked = await instructor.post(f"{API}/courses/{course_id}/publish", headers=key())
    assert (blocked.status_code, blocked.json()["code"]) == (422, "COURSE_REVIEW_INCOMPLETE")
    assert blocked.json()["missing"] == [bare["id"]]
    assert (await instructor.post(f"{API}/courses/{course_id}/publish")).status_code == 428


async def test_the_sweep_ingests_a_publication_nobody_polled(
    instructor: httpx.AsyncClient, engine: AsyncEngine, ai: FakeAiService
) -> None:
    from app.domains.ai_gateway.sweeper import sweep_once
    from app.main import app

    course_id = await review_ready_course(instructor)
    await instructor.post(f"{API}/courses/{course_id}/publish", headers=key())
    checked = await sweep_once(app.state.session_factory, ai)
    assert checked == 1
    assert (await instructor.get(f"{API}/courses/{course_id}")).json()["status"] == "published"
    assert await sweep_once(app.state.session_factory, ai) == 0


async def test_polling_the_same_finished_job_from_many_requests_ingests_once(
    instructor: httpx.AsyncClient, ai: FakeAiService
) -> None:
    import asyncio

    ai.auto_complete = False
    course = await create_course(instructor)
    uploaded = await instructor.post(
        f"{API}/courses/{course['id']}/syllabus", json=TEXT, headers=key()
    )
    job_id = uploaded.json()["job_id"]
    ai.complete(job_id)
    responses = await asyncio.gather(*(instructor.get(f"{API}/jobs/{job_id}") for _ in range(6)))
    assert {r.status_code for r in responses} == {200}
    topics = (await instructor.get(f"{API}/courses/{course['id']}/topics")).json()["topics"]
    assert len(topics) == 3  # sin duplicados


# --- trazabilidad y errores ---------------------------------------------------------------------


async def test_request_id_travels_back_and_into_errors(instructor: httpx.AsyncClient) -> None:
    ok = await instructor.get(f"{API}/courses", headers={"X-Request-ID": "req-abc-123"})
    assert ok.headers["x-request-id"] == "req-abc-123"
    missing = await instructor.get(f"{API}/courses/9999", headers={"X-Request-ID": "req-abc-124"})
    assert missing.status_code == 404
    assert missing.json()["request_id"] == "req-abc-124"
    assert missing.json()["code"] == "COURSE_NOT_FOUND"
    assert missing.headers["content-type"].startswith("application/problem+json")
    hostile = await instructor.get(f"{API}/courses", headers={"X-Request-ID": 'x y"; drop'})
    assert hostile.headers["x-request-id"] != 'x y"; drop'
    generated = await instructor.get(f"{API}/courses")
    assert len(generated.headers["x-request-id"]) == 32


async def test_error_bodies_follow_rfc_9457(instructor: httpx.AsyncClient) -> None:
    problem = (await instructor.get(f"{API}/courses/9999")).json()
    assert set(problem) == {"type", "title", "status", "detail", "instance", "code", "request_id"}
    assert problem["type"] == "https://smartmentor/errors/course-not-found"
    assert problem["instance"] == "/api/v1/courses/9999"
    validation = (await instructor.post(f"{API}/courses", json={"name": ""})).json()
    assert validation["code"] == "VALIDATION_ERROR"
    assert validation["errors"][0].keys() == {"loc", "msg", "type"}  # nunca el valor recibido
    assert (await instructor.get(f"{API}/nope")).json()["code"] == "HTTP_404"
