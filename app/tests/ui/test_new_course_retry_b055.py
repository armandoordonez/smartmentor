"""B-055: si la subida del syllabus falla, volver a pulsar no crea otro curso.

La página se prueba contra `ApiClient` con la API simulada (`respx`), para contar las peticiones
`POST /courses` y comprobar que el reintento manda la misma `Idempotency-Key` del syllabus.
"""

import json

import httpx
import pytest
import respx
from apptest import page_texts
from staff_support import (
    assert_no_exception,
    click,
    staff_app,
    staff_text_reader,  # noqa: F401
)
from support import FIXTURES_DIR

from clients.api import ApiClient

BASE = "http://api.test"
STAFF_DIR = FIXTURES_DIR / "staff"
NEW_COURSE = "pages/instructor/new_course.py"


def _fixture(name: str) -> object:
    return json.loads((STAFF_DIR / f"{name}.json").read_text("utf-8"))


@pytest.fixture
def api_client(monkeypatch: pytest.MonkeyPatch) -> ApiClient:
    client = ApiClient(BASE, lambda: "test-only-not-a-secret", http=httpx.Client(base_url=BASE))
    monkeypatch.setattr("core.container.get_client", lambda: client)
    return client


def _fill_paste_form():  # type: ignore[no-untyped-def]
    at = staff_app(page=NEW_COURSE)
    at.get("button_group")[0].set_value("Pegar texto").run()
    at.text_input(key="nc-name").set_value("Curso de prueba")
    at.run()
    at.text_area(key="nc-text").set_value("Tema 1: introducción").run()
    return at


@respx.mock
@pytest.mark.usefixtures("api_client")
@pytest.mark.parametrize(
    "failure",
    [
        httpx.Response(503, json={"code": "SERVICE_UNAVAILABLE", "detail": "x"}),
        httpx.ReadTimeout("timed out"),
    ],
    ids=["5xx", "timeout"],
)
def test_retry_after_a_failed_syllabus_upload_reuses_the_course(
    failure: httpx.Response | Exception,
) -> None:
    create = respx.post(f"{BASE}/api/v1/courses").mock(
        return_value=httpx.Response(201, json=_fixture("course_new"))
    )
    syllabus = respx.post(f"{BASE}/api/v1/courses/7/syllabus").mock(
        side_effect=[failure, httpx.Response(202, json=_fixture("job_accepted"))]
    )
    respx.get(url__regex=rf"{BASE}/api/v1/jobs/.*").mock(
        return_value=httpx.Response(200, json=_fixture("job_running"))
    )

    at = _fill_paste_form()
    at = click(at, "Extraer temas con IA")
    assert_no_exception(at)
    assert create.call_count == 1
    assert syllabus.call_count == 1
    assert not any("Extrayendo" in t for t in page_texts(at))  # sigue en el formulario

    at = click(at, "Extraer temas con IA")
    assert_no_exception(at)
    assert create.call_count == 1  # no se creó otro curso
    assert syllabus.call_count == 2
    first, second = (call.request for call in syllabus.calls)
    assert first.headers["Idempotency-Key"] == second.headers["Idempotency-Key"]
    assert any("Extrayendo" in t for t in page_texts(at))
