"""Configuración tipada de la interfaz, leída de variables de entorno."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Variables de entorno de la interfaz (ver app/README.md, sección Configuración)."""

    model_config = SettingsConfigDict(extra="ignore", case_sensitive=False)

    # Fuente de datos. Por ahora solo `sample`: el prototipo de la Fase 0 corre sin login ni API.
    # `api` (con Keycloak) llega después de la prueba técnica del login (ADR 0006, punto 6).
    app_data_source: Literal["sample"] = "sample"
    app_timezone: str = "America/Bogota"


@lru_cache
def get_settings() -> Settings:
    return Settings()
