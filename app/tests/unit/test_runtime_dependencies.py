"""Dependencias que Streamlit carga solo al usarlas; las pruebas con AppTest no las cubren."""

import importlib.metadata
import importlib.util

MIN_AUTHLIB = (1, 3, 2)


def test_authlib_is_installed_for_st_login() -> None:
    """`st.login` falla al ejecutarse sin Authlib: el extra `streamlit[auth]` debe traerla."""
    assert importlib.util.find_spec("authlib") is not None
    version = importlib.metadata.version("authlib")
    parts = tuple(int(part) for part in version.split(".")[:3] if part.isdigit())
    assert parts >= MIN_AUTHLIB
