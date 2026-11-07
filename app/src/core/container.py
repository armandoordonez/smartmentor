"""Arma el cliente de datos según `APP_DATA_SOURCE` y lo entrega a servicios y páginas.

- `fixtures`: un `FixturesClient` por sesión del navegador (vive en `AppSession`), sin login.
- `api`: un `ApiClient` que lee el token en cada llamada (`core.auth.access_token`); la conexión
  HTTP (`httpx.Client`) se comparte entre sesiones con `st.cache_resource` porque no guarda
  ningún dato personal ni el token.
"""

import httpx
import streamlit as st

from clients.api import DEFAULT_TIMEOUT, ApiClient
from clients.base import SmartMentorClient
from clients.fixtures import FixturesClient
from core import auth
from core.config import get_settings
from core.session import get_session


@st.cache_resource
def _http_pool(base_url: str) -> httpx.Client:
    return httpx.Client(base_url=base_url, timeout=DEFAULT_TIMEOUT)


def get_client() -> SmartMentorClient:
    """Cliente de datos de la sesión actual."""
    settings = get_settings()
    if settings.app_data_source == "fixtures":
        session = get_session()
        if session.fixtures_client is None:
            session.fixtures_client = FixturesClient(
                session.scenario_key or "learner", directory=settings.app_fixtures_dir
            )
        return session.fixtures_client
    return ApiClient(
        settings.api_base_url, auth.access_token, http=_http_pool(settings.api_base_url)
    )
