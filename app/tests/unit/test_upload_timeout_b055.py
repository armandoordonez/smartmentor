"""B-055: las cargas de archivos esperan más que el resto de llamadas y el valor es configurable.

Con la base en la nube lenta, `POST /courses/{id}/syllabus` tardó 11,9 s y la app lo cortó a los
10 s aunque la API sí lo aceptó. Las pruebas no esperan de verdad: miran el tiempo de espera con
el que `httpx` envía cada petición (`request.extensions["timeout"]`).
"""

import json

import httpx
import pytest
import respx
from pydantic import ValidationError
from support import FIXTURES_DIR

from clients.api import DEFAULT_UPLOAD_TIMEOUT_SECONDS, ApiClient
from clients.base import ApiError
from core.config import Settings

BASE = "http://api.test"
STAFF_DIR = FIXTURES_DIR / "staff"
SLOW_SYLLABUS_SECONDS = 11.9  # lo que tardó la API con Neon lento


def _accepted() -> httpx.Response:
    body = json.loads((STAFF_DIR / "job_accepted.json").read_text("utf-8"))
    return httpx.Response(202, json=body)


def _timeouts(route: respx.Route) -> dict[str, float | None]:
    timeouts: dict[str, float | None] = route.calls.last.request.extensions["timeout"]
    return timeouts


def _client(**kwargs: float) -> ApiClient:
    return ApiClient(
        BASE, lambda: "test-only-not-a-secret", http=httpx.Client(base_url=BASE), **kwargs
    )


@respx.mock
def test_syllabus_pdf_upload_waits_80_seconds_by_default() -> None:
    route = respx.post(f"{BASE}/api/v1/courses/1/syllabus").mock(return_value=_accepted())
    _client().upload_syllabus(1, text=None, file=("s.pdf", b"%PDF"), idempotency_key="k")
    assert _timeouts(route) == {"connect": 3.0, "read": 80.0, "write": 80.0, "pool": 80.0}


@respx.mock
def test_pasted_syllabus_text_uses_the_upload_timeout_too() -> None:
    route = respx.post(f"{BASE}/api/v1/courses/1/syllabus").mock(return_value=_accepted())
    _client().upload_syllabus(1, text="Tema 1", file=None, idempotency_key="k")
    assert _timeouts(route)["read"] == 80.0
    assert _timeouts(route)["connect"] == 3.0


@respx.mock
def test_material_upload_uses_the_upload_timeout() -> None:
    material = json.loads((STAFF_DIR / "material.json").read_text("utf-8"))
    route = respx.post(f"{BASE}/api/v1/courses/1/materials").mock(
        return_value=httpx.Response(201, json=material)
    )
    _client().upload_material(1, file=("apuntes.md", b"# Tema"), origin="own_notes")
    assert _timeouts(route)["read"] == 80.0


@respx.mock
def test_changing_the_setting_changes_the_upload_timeout() -> None:
    route = respx.post(f"{BASE}/api/v1/courses/1/syllabus").mock(return_value=_accepted())
    _client(upload_timeout_seconds=150).upload_syllabus(
        1, text=None, file=("s.pdf", b"%PDF"), idempotency_key="k"
    )
    assert _timeouts(route) == {"connect": 3.0, "read": 150.0, "write": 150.0, "pool": 150.0}


@respx.mock
def test_the_other_calls_keep_the_10_second_timeout() -> None:
    me = respx.get(f"{BASE}/api/v1/me").mock(
        return_value=httpx.Response(
            200, json=json.loads((FIXTURES_DIR / "me_learner.json").read_text("utf-8"))
        )
    )
    # El cliente de la aplicación trae 10 s propios (`DEFAULT_TIMEOUT`); aquí se usa el real.
    from clients.api import DEFAULT_TIMEOUT

    with httpx.Client(base_url=BASE, timeout=DEFAULT_TIMEOUT) as http:
        client = ApiClient(
            BASE, lambda: "test-only-not-a-secret", http=http, upload_timeout_seconds=300
        )
        client.get_me()
        assert _timeouts(me) == {"connect": 3.0, "read": 10.0, "write": 10.0, "pool": 10.0}
        respx.get(f"{BASE}/api/v1/courses").mock(
            return_value=httpx.Response(
                200, json={"items": [], "total": 0, "limit": 50, "offset": 0}
            )
        )
        client.list_courses()
        assert respx.calls.last.request.extensions["timeout"]["read"] == 10.0


@respx.mock
def test_a_slow_syllabus_is_not_cut_by_the_default_10_second_timeout() -> None:
    """La API tarda 11,9 s: con 10 s `httpx` corta; con el tiempo de las cargas, no."""

    def slow_server(request: httpx.Request) -> httpx.Response:
        read_timeout = request.extensions["timeout"]["read"]
        if read_timeout is not None and read_timeout < SLOW_SYLLABUS_SECONDS:
            raise httpx.ReadTimeout("timed out", request=request)
        return _accepted()

    respx.post(f"{BASE}/api/v1/courses/1/syllabus").mock(side_effect=slow_server)
    accepted = _client().upload_syllabus(1, text=None, file=("s.pdf", b"%PDF"), idempotency_key="k")
    assert accepted.job_id
    # Contraprueba: con el tiempo de espera general (10 s) se corta, como en B-055.
    with pytest.raises(ApiError) as error:
        _client(upload_timeout_seconds=10).upload_syllabus(
            1, text=None, file=("s.pdf", b"%PDF"), idempotency_key="k"
        )
    assert error.value.status == 503


def test_settings_default_is_80_and_matches_the_client_default() -> None:
    assert Settings().api_upload_timeout_seconds == 80.0
    assert DEFAULT_UPLOAD_TIMEOUT_SECONDS == 80.0


def test_settings_reads_the_upload_timeout_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("API_UPLOAD_TIMEOUT_SECONDS", "120")
    assert Settings().api_upload_timeout_seconds == 120.0


@pytest.mark.parametrize("value", ["0", "-5", "601", "abc"])
def test_settings_rejects_an_unreasonable_upload_timeout(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("API_UPLOAD_TIMEOUT_SECONDS", value)
    with pytest.raises(ValidationError):
        Settings()


def test_get_client_passes_the_configured_upload_timeout_b055(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """La unión `Settings` → `get_client()` → `ApiClient`: cambiar la variable cambia la espera."""
    from core import container

    settings = Settings(app_data_source="api", api_base_url=BASE, api_upload_timeout_seconds=123.0)
    monkeypatch.setattr(container, "get_settings", lambda: settings)
    monkeypatch.setattr(container, "_http_pool", lambda base_url: httpx.Client(base_url=base_url))
    client = container.get_client()
    assert isinstance(client, ApiClient)
    assert client._upload_timeout.read == 123.0
