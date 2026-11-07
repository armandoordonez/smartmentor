"""Núcleo: autenticación (funciones puras), secretos, configuración, etiquetas y errores."""

import base64
import json
import tomllib
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from clients.base import ApiError
from core import auth
from core.bootstrap_secrets import main as bootstrap_main
from core.bootstrap_secrets import missing_variables, render_secrets
from core.config import Settings, get_settings
from core.errors import MESSAGES, action_message, describe_error
from core.labels import GLOSSARIES, glossary, role_label


def make_jwt(claims: dict[str, object]) -> str:
    """JWT de prueba sin firma real: solo se lee el payload."""

    def part(data: dict[str, object]) -> str:
        return base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip("=")

    return f"{part({'alg': 'none'})}.{part(claims)}.test-only-not-a-secret"


NOW = datetime(2026, 11, 7, 15, 0, tzinfo=UTC)


# --- Token ---------------------------------------------------------------------------------------


def test_token_expiry_reads_exp_without_validating_signature() -> None:
    token = make_jwt({"exp": int((NOW + timedelta(minutes=5)).timestamp())})
    assert auth.token_expiry(token) == NOW + timedelta(minutes=5)


@pytest.mark.parametrize("token", ["", "abc", "a.b.c", "a..c", make_jwt({"sub": "x"})])
def test_token_without_readable_exp_is_treated_as_expired(token: str) -> None:
    assert auth.token_expiry(token) is None
    assert auth.is_token_expired(token, now=NOW)


def test_token_expiry_with_leeway() -> None:
    soon = make_jwt({"exp": int((NOW + timedelta(seconds=20)).timestamp())})
    later = make_jwt({"exp": int((NOW + timedelta(minutes=4)).timestamp())})
    assert auth.is_token_expired(soon, now=NOW)  # vence dentro del margen de 30 s
    assert not auth.is_token_expired(later, now=NOW)
    assert auth.is_token_expired(later, now=NOW + timedelta(minutes=4))


def test_end_session_url_uses_id_token_hint() -> None:
    metadata = {
        "end_session_endpoint": "http://localhost:8180/realms/sm/protocol/openid-connect/logout"
    }
    url = auth.build_end_session_url(
        metadata,
        id_token="test-only-not-a-secret",
        post_logout_redirect_uri="http://localhost:8501",
    )
    assert url is not None
    assert url.startswith(metadata["end_session_endpoint"] + "?")
    assert "id_token_hint=test-only-not-a-secret" in url
    assert "post_logout_redirect_uri=http%3A%2F%2Flocalhost%3A8501" in url


def test_end_session_url_without_id_token_falls_back_to_client_id() -> None:
    url = auth.build_end_session_url(
        {"end_session_endpoint": "http://kc/logout"},
        id_token=None,
        post_logout_redirect_uri="http://localhost:8501",
    )
    assert url is not None
    assert "client_id=smartmentor-ui" in url
    assert "id_token_hint" not in url


def test_end_session_url_is_none_without_endpoint() -> None:
    assert auth.build_end_session_url({}, id_token=None, post_logout_redirect_uri="x") is None


# --- Configuración y secretos --------------------------------------------------


def test_fixtures_mode_is_refused_in_production() -> None:
    with pytest.raises(ValidationError, match="production"):
        Settings(app_data_source="fixtures", app_env="production")
    assert Settings(app_data_source="api", app_env="production").app_data_source == "api"


def test_settings_default_to_api_and_generic_profile() -> None:
    settings = Settings(_env_file=None)
    assert settings.app_data_source in ("api", "fixtures")  # el entorno de pruebas fija fixtures
    assert Settings(app_data_source="api").app_context_profile == "generic"
    assert "secret" not in repr(Settings(oidc_ui_client_secret="test-only-not-a-secret"))


def _api_settings(**changes: str) -> Settings:
    values = {
        "app_data_source": "api",
        "oidc_ui_client_secret": "test-only-not-a-secret",
        "app_cookie_secret": "test-only-cookie-not-a-secret",
        "oidc_server_metadata_url": "http://keycloak:8080/realms/sm/.well-known/x",
        "app_public_url": "http://localhost:8501/",
    }
    return Settings(**{**values, **changes})  # type: ignore[arg-type]


def test_render_secrets_is_valid_toml_with_the_auth_section() -> None:
    parsed = tomllib.loads(render_secrets(_api_settings()))
    assert parsed["auth"]["redirect_uri"] == "http://localhost:8501/oauth2callback"
    assert parsed["auth"]["expose_tokens"] == ["access", "id"]
    assert parsed["auth"]["keycloak"]["client_id"] == "smartmentor-ui"
    assert parsed["auth"]["keycloak"]["client_secret"] == "test-only-not-a-secret"


def test_render_secrets_escapes_quotes() -> None:
    parsed = tomllib.loads(render_secrets(_api_settings(oidc_ui_client_secret='a"b\\c')))
    assert parsed["auth"]["keycloak"]["client_secret"] == 'a"b\\c'


def test_missing_variables_are_reported_by_name_only() -> None:
    settings = _api_settings(oidc_ui_client_secret="", app_cookie_secret="")
    assert missing_variables(settings) == ["OIDC_UI_CLIENT_SECRET", "APP_COOKIE_SECRET"]


def test_bootstrap_writes_file_with_private_permissions(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    target = tmp_path / "home" / "secrets.toml"
    for name, value in {
        "APP_DATA_SOURCE": "api",
        "OIDC_UI_CLIENT_SECRET": "test-only-not-a-secret",
        "APP_COOKIE_SECRET": "test-only-cookie-not-a-secret",
        "OIDC_SERVER_METADATA_URL": "http://keycloak:8080/x",
        "STREAMLIT_SECRETS_FILE": str(target),
    }.items():
        monkeypatch.setenv(name, value)
    get_settings.cache_clear()
    assert bootstrap_main() == 0
    assert target.stat().st_mode & 0o777 == 0o600
    assert tomllib.loads(target.read_text(encoding="utf-8"))["auth"]["keycloak"]["client_id"]


def test_bootstrap_does_nothing_in_fixtures_mode(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    target = tmp_path / "secrets.toml"
    monkeypatch.setenv("STREAMLIT_SECRETS_FILE", str(target))
    get_settings.cache_clear()
    assert bootstrap_main() == 0
    assert not target.exists()


def test_bootstrap_fails_without_secrets(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("APP_DATA_SOURCE", "api")
    monkeypatch.setenv("STREAMLIT_SECRETS_FILE", str(tmp_path / "secrets.toml"))
    for name in ("OIDC_UI_CLIENT_SECRET", "APP_COOKIE_SECRET", "OIDC_SERVER_METADATA_URL"):
        monkeypatch.delenv(name, raising=False)
    get_settings.cache_clear()
    assert bootstrap_main() == 1


# --- Etiquetas ---------------------------------------------------------------------------------


def test_generic_glossary_is_the_default() -> None:
    labels = glossary()
    assert labels.role == {
        "learner": "Aprendiz",
        "instructor": "Instructor",
        "admin": "Administrador",
    }
    assert labels.role_short["admin"] == "Admin"
    assert labels.syllabus == "Contenido del curso"


def test_glossaries_cover_the_three_role_codes() -> None:
    for profile in GLOSSARIES.values():
        assert set(profile.role) == {"learner", "instructor", "admin"} == set(profile.role_short)


def test_academic_and_corporate_only_change_visible_text() -> None:
    assert glossary("academic").role["learner"] == "Estudiante"
    assert glossary("corporate").role["instructor"] == "Capacitador"
    assert glossary("academic").role["admin"] == glossary("generic").role["admin"]


def test_api_labels_win_over_the_glossary() -> None:
    assert role_label("learner") == "Aprendiz"
    assert role_label("learner", api_labels={"learner": "Colaborador"}) == "Colaborador"
    assert role_label("admin", short=True) == "Admin"


# --- Errores -----------------------------------------------------------------------------------


def test_401_is_the_session_expired_screen() -> None:
    view = describe_error(ApiError(401, "INVALID_TOKEN"), "Aprendiz", "Rutas")
    assert view.kind == "session_expired"
    assert view.title == "Tu sesión expiró"


def test_403_names_the_role_and_the_page() -> None:
    view = describe_error(ApiError(403, "INSUFFICIENT_ROLE"), "Aprendiz", "Panel de instructor")
    assert view.kind == "forbidden"
    assert view.title == "No tienes permiso para ver esta página"
    assert "Tu rol (Aprendiz)" in view.message
    assert "Panel de instructor" in view.message


@pytest.mark.parametrize("code", ["EMAIL_NOT_VERIFIED", "ACCOUNT_DEACTIVATED"])
def test_blocked_accounts_have_their_own_view(code: str) -> None:
    assert describe_error(ApiError(403, code), None, "SmartMentor").kind == "blocked"


def test_5xx_hides_technical_details() -> None:
    view = describe_error(
        ApiError(500, "INTERNAL_ERROR", "Traceback (most recent call)"), None, "x"
    )
    assert view.kind == "unavailable"
    assert "Traceback" not in view.message


def test_action_message_prefers_the_catalog_and_never_leaks_detail() -> None:
    assert (
        action_message(ApiError(409, "ENROLLMENT_ALREADY_EXISTS"))
        == MESSAGES["ENROLLMENT_ALREADY_EXISTS"]
    )
    assert "SELECT" not in action_message(ApiError(422, "VALIDATION_ERROR", "SELECT * FROM users"))
    assert action_message(ApiError(404, "NOT_FOUND")) == "No encontramos lo que buscas."


def test_messages_are_spanish_and_codes_are_upper_snake() -> None:
    for code, text in MESSAGES.items():
        assert code.isupper()
        assert text.endswith(".")
