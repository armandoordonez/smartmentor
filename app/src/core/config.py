"""Configuración tipada de la interfaz, leída de variables de entorno (no de archivos).

Las variables y sus valores locales están en `app/README.md`; los secretos (`UI_CLIENT_SECRET`,
`APP_COOKIE_SECRET`) solo llegan por entorno y los escribe `core/bootstrap_secrets.py` en el
`secrets.toml` de Streamlit al arrancar el contenedor.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ContextProfile = Literal["generic", "academic", "corporate"]


class Settings(BaseSettings):
    """Variables de entorno de la interfaz."""

    model_config = SettingsConfigDict(extra="ignore", case_sensitive=False)

    # `api` usa la API real con login de Keycloak; `fixtures` usa JSON fijos y no pide login.
    app_data_source: Literal["api", "fixtures"] = "api"
    app_env: Literal["local", "test", "production"] = "local"
    app_timezone: str = "America/Bogota"
    app_public_url: str = "http://localhost:8501"

    # Perfil de contexto de las etiquetas (P2 para `academic` y `corporate`).
    app_context_profile: ContextProfile = "generic"
    # Organización responsable que citan los textos de A3, A3b y A3c.
    organization_name: str = "la organización responsable"
    # Ventana del piloto que cita A3b (C-03: las fechas definitivas son posteriores al hito).
    pilot_window_text: str = "entre el 2 y el 15 de noviembre de 2026"

    # API real.
    api_base_url: str = "http://api:8020"

    # Keycloak (cliente confidencial `smartmentor-ui`).
    oidc_server_metadata_url: str | None = Field(default=None)
    oidc_ui_client_id: str = "smartmentor-ui"
    oidc_ui_client_secret: str = Field(default="", repr=False)
    app_cookie_secret: str = Field(default="", repr=False)

    # Carpeta de los JSON del modo `fixtures` (por omisión, `tests/fixtures/` junto al código).
    app_fixtures_dir: Path | None = None

    @model_validator(mode="after")
    def _fixtures_never_in_production(self) -> Self:
        if self.app_data_source == "fixtures" and self.app_env == "production":
            msg = "APP_DATA_SOURCE=fixtures no se permite con APP_ENV=production (no pide login)"
            raise ValueError(msg)
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
