"""Configuración tipada de la aplicación, leída de variables de entorno."""

from functools import lru_cache
from typing import Literal
from urllib.parse import quote_plus

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Variables de entorno de la API (ver .env.example en la raíz del repositorio)."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"), extra="ignore", case_sensitive=False
    )

    app_name: str = "SmartMentor API"
    app_version: str = "0.2.0"
    app_env: str = "local"
    log_level: str = "INFO"
    app_timezone: str = "America/Bogota"

    database_host: str = "localhost"
    database_port: int = 5432
    database_name: str = "smartmentor"
    database_user: str = "smartmentor"
    database_password: SecretStr

    # Perfil de etiquetas visibles de los roles (sección 13.3 del plan). Solo cambia texto.
    app_context_profile: Literal["generic", "academic", "corporate"] = "generic"

    # Segundo factor (DEF-27, G-03): cuando está activo, las rutas de instructor y admin exigen que
    # el token lo indique (`amr`/`acr`). Se activa en la Fase 8, cuando Keycloak ya lo configura.
    require_second_factor: bool = False

    # Servicio de IA (`ai/`). `fake` usa FakeAiService (desarrollo sin `ai/`); `http` llama a `ai/`
    # con un token de servicio obtenido por client credentials (ADR 0014).
    ai_service_mode: Literal["fake", "http"] = "fake"
    ai_service_url: str = "http://ai:8030"
    ai_service_timeout_seconds: float = 10.0
    ai_service_client_id: str = "smartmentor-api-service"
    ai_service_client_secret: SecretStr = SecretStr("")
    ai_service_token_url: str | None = None  # por defecto, el endpoint de tokens de Keycloak
    # Cada cuántos segundos el barrido del lifespan ingiere trabajos terminados (0 lo desactiva).
    ai_sweep_interval_seconds: int = 60

    # Emisor de los badges Open Badges 2.0 (E10). Las URL de la aserción «hosted» se arman con la
    # dirección pública con la que se pide la aserción.
    badge_issuer_name: str = "SmartMentor"
    badge_issuer_url: str = "http://localhost:8501"

    # Límites de carga y de idempotencia (docs/contracts/api-v2.md, sección 1).
    syllabus_max_bytes: int = 10 * 1024 * 1024
    idempotency_ttl_seconds: int = 24 * 3600

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
    # Cliente de Keycloak con el que Swagger UI (/docs) pide el token con usuario y contraseña.
    # Solo desarrollo: vacío lo desactiva (en producción queda solo "pegar un token").
    oidc_docs_client_id: str | None = "smartmentor-dev-tools"

    @property
    def oidc_token_url(self) -> str:
        """Endpoint de tokens de Keycloak, tal como lo ve el navegador (lo usa Swagger UI)."""
        return f"{self.oidc_issuer_url.rstrip('/')}/protocol/openid-connect/token"

    @property
    def ai_token_url(self) -> str:
        return self.ai_service_token_url or self.oidc_token_url

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
