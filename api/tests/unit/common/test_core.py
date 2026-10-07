import json
import logging

from pydantic import SecretStr

from app.core.config import Settings
from app.core.logging import JsonFormatter, mask_email, request_id_var


def test_database_url_escapes_special_characters() -> None:
    settings = Settings(
        database_host="db",
        database_port=5433,
        database_name="smartmentor",
        database_user="smartmentor",
        database_password=SecretStr("p@ss/word:1"),
    )
    assert settings.database_url == (
        "postgresql+asyncpg://smartmentor:p%40ss%2Fword%3A1@db:5433/smartmentor"
    )


def test_mask_email_hides_the_local_part() -> None:
    assert mask_email("juan.perez@example.com") == "j***@example.com"
    assert mask_email("sin-arroba") == "***"


def test_json_formatter_includes_request_id_and_bogota_offset() -> None:
    formatter = JsonFormatter("smartmentor-api", "test", "America/Bogota")
    token = request_id_var.set("req-1")
    try:
        record = logging.LogRecord("app", logging.INFO, __file__, 1, "hola", None, None)
        payload = json.loads(formatter.format(record))
    finally:
        request_id_var.reset(token)
    assert payload["request_id"] == "req-1"
    assert payload["message"] == "hola"
    assert payload["timestamp"].endswith("-05:00")


def test_empty_oidc_settings_are_rejected_at_startup() -> None:
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Settings(
            database_password=SecretStr("x"),
            oidc_issuer_url="",
            oidc_jwks_url="http://keycloak/certs",
        )
