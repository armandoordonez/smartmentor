"""Modo `api`: login de Keycloak simulado, token en cada llamada, A7 y errores 403 de la API.

No hay un Keycloak real aquí: se simulan `core.auth` (el token expuesto) y la API con `respx`. La
prueba técnica del login con Keycloak (7.0) queda para la Fase 8.
"""

import base64
import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest
import respx
from apptest import header_texts, new_app, page_texts, session_of
from streamlit.testing.v1 import AppTest
from support import FIXTURES_DIR

API = "http://api.test"


def jwt(expires_in: timedelta) -> str:
    def encode(data: dict[str, object]) -> str:
        return base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip("=")

    exp = int((datetime.now(UTC) + expires_in).timestamp())
    return f"{encode({'alg': 'none'})}.{encode({'exp': exp})}.test-only-not-a-secret"


def fixture(name: str) -> object:
    return json.loads((FIXTURES_DIR / f"{name}.json").read_text(encoding="utf-8"))


@pytest.fixture
def api_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_DATA_SOURCE", "api")
    monkeypatch.setenv("API_BASE_URL", API)


def logged_in_as(monkeypatch: pytest.MonkeyPatch, token: str | None) -> None:
    from core import auth

    monkeypatch.setattr(auth, "is_logged_in", lambda: True)
    monkeypatch.setattr(auth, "_exposed_token", lambda name: token if name == "access" else None)


@pytest.mark.usefixtures("api_mode")
def test_without_login_the_keycloak_login_screen_is_shown() -> None:
    at = new_app().run()
    assert [e.value for e in at.exception] == []
    texts = page_texts(at, skip_header=False)
    assert "Inicia sesión para continuar" in texts
    assert [b.label for b in at.button] == ["Iniciar sesión"]
    # En modo api no existe el selector de rol (A1).
    assert "¿Cómo quieres entrar?" not in texts


@respx.mock
@pytest.mark.usefixtures("api_mode")
def test_with_a_valid_token_the_user_comes_from_get_me(monkeypatch: pytest.MonkeyPatch) -> None:
    token = jwt(timedelta(minutes=5))
    logged_in_as(monkeypatch, token)
    me = respx.get(f"{API}/api/v1/me").mock(
        return_value=httpx.Response(200, json=fixture("me_instructor"))
    )
    courses = respx.get(f"{API}/api/v1/courses").mock(
        return_value=httpx.Response(200, json={"items": [], "total": 0, "limit": 50, "offset": 0})
    )
    paths = respx.get(f"{API}/api/v1/learning-paths").mock(
        return_value=httpx.Response(200, json=fixture("learning_paths"))
    )
    at = new_app().run()
    assert [e.value for e in at.exception] == []
    # El rol sale de GET /me (mayor privilegio: instructor), no del token.
    assert session_of(at).active_role == "instructor"
    assert me.calls.last.request.headers["Authorization"] == f"Bearer {token}"
    assert "Instructor" in header_texts(at)
    assert courses.called  # el inicio del instructor es «Mis cursos» (D1)
    # Cambiar de perfil (CU-35) abre el catálogo del aprendiz con el mismo token.
    at.button(key="switch-role-learner").click().run()
    assert [e.value for e in at.exception] == []
    assert paths.called
    assert paths.calls.last.request.headers["Authorization"] == f"Bearer {token}"
    assert "Rutas" in page_texts(at)


@respx.mock
@pytest.mark.usefixtures("api_mode")
def test_get_me_is_asked_once_per_session(monkeypatch: pytest.MonkeyPatch) -> None:
    logged_in_as(monkeypatch, jwt(timedelta(minutes=5)))
    me = respx.get(f"{API}/api/v1/me").mock(
        return_value=httpx.Response(200, json=fixture("me_learner"))
    )
    respx.get(f"{API}/api/v1/learning-paths").mock(
        return_value=httpx.Response(200, json=fixture("learning_paths"))
    )
    at = new_app().run()
    at.run()
    assert me.call_count == 1
    assert [e.value for e in at.exception] == []


@pytest.mark.usefixtures("api_mode")
def test_an_expired_token_shows_a7_before_any_api_call(monkeypatch: pytest.MonkeyPatch) -> None:
    logged_in_as(monkeypatch, jwt(timedelta(minutes=-1)))
    with respx.mock:  # cualquier llamada a la API fallaría la prueba: no debe haber ninguna
        at = new_app().run()
    assert [e.value for e in at.exception] == []
    texts = page_texts(at, skip_header=False)
    assert "Tu sesión expiró" in texts
    assert any("30 minutos sin actividad" in t for t in texts)
    assert [b.label for b in at.button] == ["Iniciar sesión", "Cambiar de cuenta"]


@respx.mock
@pytest.mark.usefixtures("api_mode")
def test_a_401_from_the_api_is_a7(monkeypatch: pytest.MonkeyPatch) -> None:
    logged_in_as(monkeypatch, jwt(timedelta(minutes=5)))
    respx.get(f"{API}/api/v1/me").mock(
        return_value=httpx.Response(
            401,
            json={"status": 401, "code": "INVALID_TOKEN", "title": "x", "request_id": "r1"},
            headers={"Content-Type": "application/problem+json"},
        )
    )
    at = new_app().run()
    assert "Tu sesión expiró" in page_texts(at, skip_header=False)


@respx.mock
@pytest.mark.parametrize(
    ("code", "title"),
    [
        ("EMAIL_NOT_VERIFIED", "No pudimos darte acceso"),
        ("ACCOUNT_DEACTIVATED", "No pudimos darte acceso"),
    ],
)
@pytest.mark.usefixtures("api_mode")
def test_blocked_accounts_are_explained_without_details(
    monkeypatch: pytest.MonkeyPatch, code: str, title: str
) -> None:
    logged_in_as(monkeypatch, jwt(timedelta(minutes=5)))
    respx.get(f"{API}/api/v1/me").mock(
        return_value=httpx.Response(
            403,
            json={"status": 403, "code": code, "title": "x", "detail": "secret detail"},
            headers={"Content-Type": "application/problem+json"},
        )
    )
    at = new_app().run()
    texts = page_texts(at, skip_header=False)
    assert title in texts
    assert not any("secret detail" in text for text in texts)


@respx.mock
@pytest.mark.usefixtures("api_mode")
def test_api_down_shows_unavailable_service(monkeypatch: pytest.MonkeyPatch) -> None:
    logged_in_as(monkeypatch, jwt(timedelta(minutes=5)))
    respx.get(f"{API}/api/v1/me").mock(side_effect=httpx.ConnectError("down"))
    at = new_app().run()
    assert [e.value for e in at.exception] == []
    assert "El servicio no está disponible." in [w.value.split("**")[1] for w in at.warning]


def test_fixtures_mode_is_refused_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("APP_DATA_SOURCE", "fixtures")
    at: AppTest = new_app().run()
    assert at.exception  # Settings lanza ValueError: no se puede saltar el login en producción
