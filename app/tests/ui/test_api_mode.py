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
import streamlit as st
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
    assert any("3 horas sin actividad" in t for t in texts)
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


# --- B-030 · Renovación del token: vuelve a la misma página y con la misma sesión ---------------


def jwt_issued(issued_ago: timedelta, expires_in: timedelta) -> str:
    def encode(data: dict[str, object]) -> str:
        return base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip("=")

    now = datetime.now(UTC)
    claims = {
        "iat": int((now - issued_ago).timestamp()),
        "exp": int((now + expires_in).timestamp()),
    }
    return f"{encode({'alg': 'none'})}.{encode(claims)}.test-only-not-a-secret"


@respx.mock
@pytest.mark.usefixtures("api_mode")
def test_silent_renewal_returns_to_the_same_page_with_the_same_session_b030(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """La redirección de OIDC no se simula: se prueba aparcar antes de `st.login` y recuperar en
    la sesión nueva (otra `AppTest`, como la que abre Streamlit al volver a la raíz)."""
    from core import auth, renewal

    token = {"access": jwt(timedelta(minutes=5))}
    logins: list[str] = []
    store = renewal.RenewalStore()
    monkeypatch.setattr(renewal, "STORE", store)
    monkeypatch.setattr(auth, "is_logged_in", lambda: True)
    monkeypatch.setattr(auth, "user_key", lambda: "sub-ana")
    monkeypatch.setattr(auth, "_exposed_token", lambda name: token.get(name))
    monkeypatch.setattr(st, "login", lambda provider: logins.append(provider))
    respx.get(f"{API}/api/v1/me").mock(return_value=httpx.Response(200, json=fixture("me_learner")))
    respx.get(f"{API}/api/v1/learning-paths").mock(
        return_value=httpx.Response(200, json=fixture("learning_paths"))
    )
    respx.get(f"{API}/api/v1/me/profile").mock(
        return_value=httpx.Response(200, json=fixture("profile"))
    )
    at = new_app().run()
    at.switch_page("pages/learner/my_profile.py").run()
    assert [e.value for e in at.exception] == []
    session_of(at).learner.step_id = 813  # estado del aprendiz que debe sobrevivir

    # El token vence (emitido hace 6 min): se aparca la sesión y se redirige a Keycloak sin A7.
    token["access"] = jwt_issued(timedelta(minutes=6), timedelta(minutes=-1))
    at.run()
    assert [e.value for e in at.exception] == []
    assert logins == ["keycloak"]
    texts = page_texts(at, skip_header=False)
    assert "Renovando tu sesión…" in texts
    assert "Tu sesión expiró" not in texts
    assert len(store) == 1

    # Vuelta de Keycloak: sesión nueva en la raíz con un token nuevo.
    token["access"] = jwt(timedelta(minutes=5))
    back = new_app().run()
    assert [e.value for e in back.exception] == []
    assert session_of(back).learner.step_id == 813
    assert session_of(back).current_page == "pages/learner/my_profile.py"
    assert "Descripción de tu perfil" in [t.label for t in back.text_area]
    assert len(store) == 0


@respx.mock
@pytest.mark.usefixtures("api_mode")
def test_a_freshly_issued_expired_token_shows_a7_without_parking(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from core import renewal

    store = renewal.RenewalStore()
    monkeypatch.setattr(renewal, "STORE", store)
    logged_in_as(monkeypatch, jwt_issued(timedelta(seconds=30), timedelta(seconds=-5)))
    at = new_app().run()
    assert "Tu sesión expiró" in page_texts(at, skip_header=False)
    assert len(store) == 0


# --- B-040 · La renovación del token no descarta el clic que la provoca ------------------------

RESUME = "pages/learner/onboarding_resume.py"
SAVED_TEXT = "Listo: tu perfil quedó guardado."


def _empty_profile() -> dict[str, object]:
    profile: dict[str, object] = json.loads(
        (FIXTURES_DIR / "profile.json").read_text(encoding="utf-8")
    )
    profile.update(education_level=None, qualification_title=None, job_title=None)
    return profile


def _learner_api(
    monkeypatch: pytest.MonkeyPatch,
    token: dict[str, str],
    profile: dict[str, object] | None = None,
) -> list[str]:
    """Aprendiz con la API simulada; devuelve los logins que se pidieron a Keycloak."""
    from core import auth

    logins: list[str] = []
    monkeypatch.setattr(auth, "is_logged_in", lambda: True)
    monkeypatch.setattr(auth, "user_key", lambda: "sub-ana")
    monkeypatch.setattr(auth, "_exposed_token", lambda name: token.get(name))
    monkeypatch.setattr(st, "login", lambda provider: logins.append(provider))
    respx.get(f"{API}/api/v1/me").mock(return_value=httpx.Response(200, json=fixture("me_learner")))
    respx.get(f"{API}/api/v1/learning-paths").mock(
        return_value=httpx.Response(200, json=fixture("learning_paths"))
    )
    respx.get(f"{API}/api/v1/me/profile").mock(
        return_value=httpx.Response(200, json=profile if profile is not None else _empty_profile())
    )
    return logins


def _fill_resume(at: AppTest) -> None:
    at.selectbox(key="resume-education").select("undergraduate")
    at.text_input(key="resume-title").input("Ingeniería de sistemas")


def _open_resume(
    monkeypatch: pytest.MonkeyPatch, profile: dict[str, object] | None = None
) -> tuple[AppTest, dict[str, str], list[str]]:
    from core import renewal

    monkeypatch.setattr(renewal, "STORE", renewal.RenewalStore())
    token = {"access": jwt_issued(timedelta(minutes=1), timedelta(minutes=4))}
    logins = _learner_api(monkeypatch, token, profile)
    at = new_app().run()
    at.switch_page(RESUME).run()
    assert [e.value for e in at.exception] == []
    return at, token, logins


@respx.mock
@pytest.mark.usefixtures("api_mode")
def test_a_click_when_the_token_expires_keeps_the_form_and_is_repeated_b040(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """E2b: el clic en «Guardar y continuar» llega con el token vencido. Antes, el formulario
    volvía vacío y no se guardaba nada; ahora se aparcan los valores y el clic, y al volver de
    Keycloak (otra `AppTest`, la sesión nueva) el formulario los conserva y el clic se repite."""
    from core import renewal

    saved = respx.put(f"{API}/api/v1/me/profile").mock(
        return_value=httpx.Response(200, json=fixture("profile"))
    )
    at, token, logins = _open_resume(monkeypatch)

    # La persona llena el formulario y pulsa justo cuando el token vence.
    token["access"] = jwt_issued(timedelta(minutes=6), timedelta(seconds=-1))
    _fill_resume(at)
    at.button(key="resume-save").click().run()
    assert [e.value for e in at.exception] == []
    assert logins == ["keycloak"]
    assert "Renovando tu sesión…" in page_texts(at, skip_header=False)
    assert not saved.called  # nada se hizo con el token vencido
    assert len(renewal.STORE) == 1

    # Vuelta de Keycloak: sesión nueva en la raíz con un token nuevo.
    token["access"] = jwt(timedelta(minutes=5))
    back = new_app().run()
    assert [e.value for e in back.exception] == []
    assert session_of(back).current_page == RESUME
    assert back.selectbox(key="resume-education").value == "undergraduate"
    assert back.text_input(key="resume-title").value == "Ingeniería de sistemas"
    # El clic se repitió una sola vez y con los valores del formulario.
    assert saved.call_count == 1
    body = json.loads(saved.calls.last.request.content)
    assert body["education_level"] == "undergraduate"
    assert body["qualification_title"] == "Ingeniería de sistemas"
    assert SAVED_TEXT in [s.value for s in back.success]

    back.run()  # otra ejecución no repite el clic
    assert saved.call_count == 1
    assert len(renewal.STORE) == 0


@respx.mock
@pytest.mark.usefixtures("api_mode")
def test_no_renewal_in_the_middle_of_an_action_while_the_token_still_works_b040(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Con 60 s por delante, el clic se atiende con el token actual; la renovación queda para la
    siguiente ejecución sin acción (aquí, una recarga), sin interrumpir nada."""
    from core import renewal

    saved = respx.put(f"{API}/api/v1/me/profile").mock(
        return_value=httpx.Response(200, json=fixture("profile"))
    )
    at, token, logins = _open_resume(monkeypatch)

    token["access"] = jwt_issued(timedelta(minutes=4), timedelta(seconds=60))
    _fill_resume(at)
    at.button(key="resume-save").click().run()
    assert [e.value for e in at.exception] == []
    assert logins == []
    assert saved.call_count == 1
    assert SAVED_TEXT in [s.value for s in at.success]

    # Ejecución sin acción y con el token a punto de vencer: se renueva ya, sin clic pendiente.
    at.run()
    assert logins == ["keycloak"]
    assert "Renovando tu sesión…" in page_texts(at, skip_header=False)
    parked = renewal.STORE.claim("sub-ana")
    assert parked is not None
    assert parked.click is None
    assert parked.page == RESUME
    assert parked.drafts["resume-title"] == "Ingeniería de sistemas"


@respx.mock
@pytest.mark.usefixtures("api_mode")
def test_a_changed_widget_with_an_expired_token_is_restored_without_a_click_b040(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Un widget cambiado (sin botón) que llega con el token vencido: su valor se conserva y no
    hay clic que repetir."""
    saved = respx.put(f"{API}/api/v1/me/profile").mock(
        return_value=httpx.Response(200, json=fixture("profile"))
    )
    at, token, logins = _open_resume(monkeypatch)

    token["access"] = jwt_issued(timedelta(minutes=6), timedelta(seconds=-1))
    at.text_input(key="resume-job").input("Analista").run()
    assert logins == ["keycloak"]

    token["access"] = jwt(timedelta(minutes=5))
    back = new_app().run()
    assert [e.value for e in back.exception] == []
    assert back.text_input(key="resume-job").value == "Analista"
    assert session_of(back).resume_click is None
    assert not saved.called


@respx.mock
@pytest.mark.usefixtures("api_mode")
def test_restoring_the_draft_over_a_saved_resume_does_not_warn_b053(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """E2b con la hoja de vida ya guardada: al volver de Keycloak el borrador pisa los valores del
    perfil y Streamlit no debe avisar de «default value» más «Session State API» (B-053)."""
    from streamlit.elements.lib import policies

    saved_profile = fixture("profile")
    assert isinstance(saved_profile, dict)
    respx.put(f"{API}/api/v1/me/profile").mock(return_value=httpx.Response(200, json=saved_profile))
    at, token, logins = _open_resume(monkeypatch, saved_profile)
    assert at.text_input(key="resume-title").value == "Ingeniería industrial"

    token["access"] = jwt_issued(timedelta(minutes=6), timedelta(seconds=-1))
    at.text_input(key="resume-title").input("Ingeniería de sistemas")
    at.text_input(key="resume-job").input("Arquitecta")
    at.selectbox(key="resume-experience").select("3_5_years")
    at.pills(key="resume-tools").set_value(["Excel"])
    at.selectbox(key="resume-cefr-0").select("C1")
    at.button(key="resume-save").click().run()
    assert logins == ["keycloak"]

    # Streamlit avisa una sola vez por proceso: se reinicia para que la prueba lo vea.
    monkeypatch.setattr(policies, "_shown_default_value_warning", False)
    token["access"] = jwt(timedelta(minutes=5))
    with caplog.at_level("WARNING", logger="streamlit"):
        back = new_app().run()
    assert [e.value for e in back.exception] == []
    warned = [r.getMessage() for r in caplog.records if "Session State API" in r.getMessage()]
    assert warned == []
    # El borrador se conserva: ningún valor vuelve al del perfil guardado.
    assert back.text_input(key="resume-title").value == "Ingeniería de sistemas"
    assert back.text_input(key="resume-job").value == "Arquitecta"
    assert back.selectbox(key="resume-experience").value == "3_5_years"
    assert back.pills(key="resume-tools").value == ["Excel"]
    assert back.selectbox(key="resume-cefr-0").value == "C1"
    assert back.selectbox(key="resume-language-0").value == "en"
