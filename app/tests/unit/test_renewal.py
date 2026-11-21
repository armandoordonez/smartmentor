"""B-030: tras renovar el token con `st.login`, volver a la misma página y con la misma sesión.

La redirección real de OIDC no se prueba aquí (ni con `AppTest`): se prueban el almacén de sesiones
aparcadas, la página que se recuerda y el orden «aparcar y luego redirigir» de `core.auth`.
"""

import base64
import json
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import streamlit as st
from support import FIXTURES_DIR

from clients.base import ApiError
from clients.models import Me
from core import auth, errors, renewal, widget_state
from core.renewal import RenewalStore
from core.session import AppSession, PendingClick
from core.widget_state import PressedButton

QUIZ = "pages/learner/quiz.py"


def make_jwt(claims: dict[str, object]) -> str:
    def part(data: dict[str, object]) -> str:
        return base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip("=")

    return f"{part({'alg': 'none'})}.{part(claims)}.test-only-not-a-secret"


def old_expired_token() -> str:
    now = datetime.now(UTC)
    return make_jwt(
        {
            "iat": int((now - timedelta(minutes=6)).timestamp()),
            "exp": int((now - timedelta(minutes=1)).timestamp()),
        }
    )


def a_me() -> Me:
    return Me.model_validate_json((FIXTURES_DIR / "me_learner.json").read_text(encoding="utf-8"))


# --- Almacén -----------------------------------------------------------------------------------


def test_a_parked_session_is_claimed_once() -> None:
    store = RenewalStore()
    session = AppSession()
    store.park("user-1", page=QUIZ, session=session, now=0)
    parked = store.claim("user-1", now=1)
    assert parked is not None
    assert parked.page == QUIZ
    assert parked.session is session
    assert store.claim("user-1", now=2) is None


def test_a_parked_session_expires() -> None:
    store = RenewalStore(ttl=600)
    store.park("user-1", page=QUIZ, session=AppSession(), now=0)
    assert store.claim("user-1", now=600) is None
    assert len(store) == 0


def test_expired_sessions_are_purged_when_another_is_parked() -> None:
    store = RenewalStore(ttl=10)
    store.park("user-1", page=QUIZ, session=AppSession(), now=0)
    store.park("user-2", page=QUIZ, session=AppSession(), now=20)
    assert len(store) == 1


def test_another_person_cannot_claim_the_session() -> None:
    store = RenewalStore()
    store.park("user-1", page=QUIZ, session=AppSession(), now=0)
    assert store.claim("user-2", now=1) is None
    assert len(store) == 1


# --- Página -------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("http://localhost:8501/quiz", QUIZ),
        ("https://example.org/app/final-assessment", "pages/learner/final_assessment.py"),
        ("http://localhost:8501/", None),
        ("http://localhost:8501", None),
        ("http://localhost:8501/unknown-page", None),
        (None, None),
        ("", None),
    ],
)
def test_the_page_comes_from_the_browser_url(url: str | None, expected: str | None) -> None:
    assert renewal.page_from_url(url) == expected


# --- Aparcar y recuperar ------------------------------------------------------------------------


def test_restore_returns_the_parked_session_with_the_page_to_go_back_to() -> None:
    store = RenewalStore()
    old = AppSession(me=a_me(), active_role="learner", selected_enrollment_id=7)
    old.learner.step_id = 813
    assert renewal.park(store, "user-1", QUIZ, old)
    restored = renewal.restore(store, "user-1", AppSession())
    assert restored is old
    assert restored.resume_page == QUIZ
    assert restored.learner.step_id == 813
    assert restored.selected_enrollment_id == 7


def test_an_open_tab_of_the_same_person_does_not_take_the_parked_session() -> None:
    store = RenewalStore()
    renewal.park(store, "user-1", QUIZ, AppSession())
    assert renewal.restore(store, "user-1", AppSession(me=a_me())) is None
    assert len(store) == 1


def test_without_identity_nothing_is_parked_or_restored() -> None:
    store = RenewalStore()
    assert not renewal.park(store, None, QUIZ, AppSession())
    assert len(store) == 0
    assert renewal.restore(store, None, AppSession()) is None


# --- core.auth ----------------------------------------------------------------------------------


def test_renewal_parks_before_redirecting(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(auth, "_exposed_token", lambda _name: old_expired_token())
    monkeypatch.setattr(st, "login", lambda provider: calls.append(f"login:{provider}"))
    assert auth.renew_silently_if_possible(before_redirect=lambda: calls.append("park"))
    assert calls == ["park", "login:keycloak"]


def test_a_valid_token_is_not_renewed_nor_parked(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    now = datetime.now(UTC)
    valid = make_jwt(
        {"iat": int(now.timestamp()), "exp": int((now + timedelta(minutes=4)).timestamp())}
    )
    monkeypatch.setattr(auth, "_exposed_token", lambda _name: valid)
    monkeypatch.setattr(st, "login", lambda _provider: calls.append("login"))
    assert not auth.renew_silently_if_possible(before_redirect=lambda: calls.append("park"))
    assert calls == []


NOW = datetime(2026, 11, 15, 10, 0, tzinfo=UTC)


def token_at(issued_ago: float, expires_in: float) -> str:
    return make_jwt(
        {
            "iat": int((NOW - timedelta(seconds=issued_ago)).timestamp()),
            "exp": int((NOW + timedelta(seconds=expires_in)).timestamp()),
        }
    )


# --- B-040 · Cuándo renovar ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("issued_ago", "expires_in", "has_action", "expected"),
    [
        # Con margen de sobra no se renueva, haya o no acción.
        (60, 240, False, "none"),
        (60, 240, True, "none"),
        # A punto de vencer y sin acción: se renueva ya, sin interrumpir nada.
        (240, 60, False, "safe_point"),
        (210, 90, False, "safe_point"),
        # A punto de vencer con una acción: se aplaza mientras el token sirva para la petición.
        (240, 60, True, "none"),
        (284, 16, True, "none"),
        # El token ya no sirve: se renueva ahora (con o sin acción).
        (290, 10, True, "now"),
        (360, -60, True, "now"),
        (360, -60, False, "now"),
        # Un token recién emitido no se renueva otra vez (evita el ciclo de redirecciones).
        (60, 60, False, "none"),
        (30, -5, True, "none"),
    ],
)
def test_plan_renewal(
    issued_ago: float, expires_in: float, has_action: bool, expected: str
) -> None:
    token = token_at(issued_ago, expires_in)
    assert auth.plan_renewal(token, has_action=has_action, now=NOW) == expected


def test_plan_renewal_without_token_or_claims_does_nothing() -> None:
    assert auth.plan_renewal(None, has_action=False, now=NOW) == "none"
    no_iat = make_jwt({"exp": int((NOW - timedelta(minutes=1)).timestamp())})
    assert auth.plan_renewal(no_iat, has_action=False, now=NOW) == "none"
    assert auth.plan_renewal("not-a-jwt", has_action=False, now=NOW) == "none"


def test_a_deferred_action_still_finds_a_valid_token() -> None:
    """Lo que `plan_renewal` deja pasar, `access_token` lo acepta: el margen es el mismo."""
    token = token_at(284, auth.EXPIRY_LEEWAY_SECONDS + 1)
    assert auth.plan_renewal(token, has_action=True, now=NOW) == "none"
    assert not auth.is_token_expired(token, now=NOW)


# --- B-040 · Borrador del formulario y clic pendiente ---------------------------------------------


def test_drafts_and_click_are_parked_and_restored_once() -> None:
    store = RenewalStore()
    drafts = {"resume-title": "Ingeniería", "resume-education": "undergraduate"}
    click = PressedButton(widget_id="$$ID-abc-resume-save", key="resume-save")
    assert renewal.park(store, "user-1", QUIZ, AppSession(), drafts=drafts, click=click)
    drafts["resume-title"] = "otro"  # lo aparcado no cambia si la página sigue escribiendo
    restored = renewal.restore(store, "user-1", AppSession())
    assert restored is not None
    assert restored.resume_drafts == {
        "resume-title": "Ingeniería",
        "resume-education": "undergraduate",
    }
    assert restored.resume_click == PendingClick(
        page=QUIZ, widget_id="$$ID-abc-resume-save", key="resume-save"
    )
    assert renewal.restore(store, "user-1", AppSession()) is None


def test_without_a_page_the_click_is_not_repeated() -> None:
    store = RenewalStore()
    click = PressedButton(widget_id="w", key="k")
    renewal.park(store, "user-1", None, AppSession(), click=click)
    restored = renewal.restore(store, "user-1", AppSession())
    assert restored is not None
    assert restored.resume_click is None


def test_a_renewal_without_drafts_restores_nothing_extra() -> None:
    store = RenewalStore()
    renewal.park(store, "user-1", QUIZ, AppSession())
    restored = renewal.restore(store, "user-1", AppSession())
    assert restored is not None
    assert restored.resume_drafts == {}
    assert restored.resume_click is None


def test_widget_state_outside_streamlit_is_safe() -> None:
    """Sin ejecución de Streamlit no hay acción, borrador ni clic que repetir."""
    assert widget_state.current_interaction() == widget_state.NO_INTERACTION
    assert widget_state.form_values() == {}
    assert not widget_state.press("w")


class _Rerun(Exception):
    pass


def _defer(monkeypatch: pytest.MonkeyPatch, error: ApiError) -> dict[str, object]:
    """`defer_to_main` desde un fragmento, con `st.session_state` y `st.rerun` simulados."""
    state: dict[str, object] = {}
    pressed = widget_state.Interaction(pending=True, pressed=PressedButton("w-1", "quiz-next"))

    def rerun(**_kwargs: object) -> None:
        raise _Rerun

    monkeypatch.setattr(st, "session_state", state)
    monkeypatch.setattr(st, "rerun", rerun)
    monkeypatch.setattr(errors, "current_interaction", lambda: pressed)
    with pytest.raises(_Rerun):
        errors.defer_to_main(error)
    return state


def test_a_fragment_click_with_an_expired_token_is_kept_for_main(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El token venció antes de enviar la petición del fragmento: el clic se repite al volver."""
    _defer(monkeypatch, ApiError(401, auth.TOKEN_EXPIRED_CODE, "expired"))
    assert errors.pop_deferred_click() == PressedButton("w-1", "quiz-next")
    assert errors.pop_deferred_click() is None
    assert errors.pop_deferred_error() is not None


def test_a_click_rejected_by_the_api_is_not_repeated(monkeypatch: pytest.MonkeyPatch) -> None:
    """Un 401 o 403 de la API (la petición sí salió) no guarda el clic para repetirlo."""
    _defer(monkeypatch, ApiError(401, "INVALID_TOKEN", "invalid"))
    assert errors.pop_deferred_click() is None
    _defer(monkeypatch, ApiError(403, "INSUFFICIENT_ROLE", "forbidden"))
    assert errors.pop_deferred_click() is None


class _FakeUser(dict[str, Any]):
    is_logged_in = True


def test_user_key_is_the_subject_of_the_identity_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth, "is_logged_in", lambda: True)
    monkeypatch.setattr(st, "user", _FakeUser(sub="abc-123", email="ana@example.org"))
    assert auth.user_key() == "abc-123"


def test_without_login_there_is_no_user_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth, "is_logged_in", lambda: False)
    assert auth.user_key() is None
