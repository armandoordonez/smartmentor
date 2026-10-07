"""Configuración tipada de la aplicación, leída de variables de entorno."""

from functools import lru_cache
from urllib.parse import quote_plus

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Variables de entorno de la API (ver .env.example en la raíz del repositorio)."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"), extra="ignore", case_sensitive=False
    )

    app_name: str = "SmartMentor API"
    app_version: str = "0.1.0"
    app_env: str = "local"
    log_level: str = "INFO"
    app_timezone: str = "America/Bogota"

    database_host: str = "localhost"
    database_port: int = 5432
    database_name: str = "smartmentor"
    database_user: str = "smartmentor"
    database_password: SecretStr

    # Contrato con el esquema (Liquibase) y el modelo de embeddings. Provisional: pendiente D-01.
    embedding_dimension: int = 1024

    # Autenticación con Keycloak (OpenID Connect). Son obligatorias: la API no arranca sin ellas.
    #   oidc_issuer_url: el `iss` de los tokens, tal como lo ve el cliente
    #                    (p. ej. http://localhost:8180/realms/smartmentor).
    #   oidc_jwks_url:   dónde la API descarga las llaves públicas (puede ser una URL interna de
    #                    la red de Docker, p. ej. http://keycloak:8080/realms/.../certs).
    #   oidc_audience:   el `aud` que deben traer los tokens.
    oidc_issuer_url: str = Field(min_length=1)
    oidc_jwks_url: str = Field(min_length=1)
    oidc_audience: str = Field(default="smartmentor-api", min_length=1)
    oidc_identity_provider: str = Field(default="keycloak", min_length=1)

    @property
    def database_url(self) -> str:
        user = quote_plus(self.database_user)
        password = quote_plus(self.database_password.get_secret_value())
        return (
            f"postgresql+asyncpg://{user}:{password}"
            f"@{self.database_host}:{self.database_port}/{self.database_name}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
