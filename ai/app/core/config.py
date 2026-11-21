"""Typed settings of the AI service, read once from environment variables (plan 16.2).

Rules (ADR 0011 and 0012):

* Providers and model names have **no default in code**. When one is missing the service still
  starts (``/health`` answers) but ``/ready`` fails with a clear message and the worker refuses
  to run.
* Credentials only come from the environment (``.env`` loaded by compose). Nothing here holds a
  real value.
"""

from __future__ import annotations

from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Literal, Self
from urllib.parse import quote_plus

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

AI_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = AI_ROOT.parent

LlmProviderName = Literal["gemini", "anthropic", "fake"]
EmbeddingProviderName = Literal["gemini", "fake"]
REAL_LLM_PROVIDERS: frozenset[str] = frozenset({"gemini", "anthropic"})


def _empty_to_none(value: object) -> object:
    """``.env.example`` leaves optional values empty: treat ``""`` as missing."""
    if isinstance(value, str) and not value.strip():
        return None
    return value


class Settings(BaseSettings):
    """Environment variables of ``ai/`` (documented in the root ``.env.example``)."""

    model_config = SettingsConfigDict(extra="ignore", case_sensitive=False)

    app_env: str = "local"
    log_level: str = "INFO"
    app_timezone: str = "America/Bogota"
    ai_port: int = 8030

    # --- Database (least-privilege user smartmentor_ai, ADR 0019) ---
    database_host: str = "postgres"
    database_port: int = 5432
    database_name: str = "smartmentor"
    ai_database_user: str | None = None
    ai_database_password: SecretStr | None = None
    # true = la conexión exige TLS (bases administradas en la nube, como Neon). Local: false.
    database_ssl: bool = False

    # --- Service-to-service authentication (ADR 0014) ---
    oidc_issuer_url: str | None = None
    oidc_jwks_url: str | None = None
    ai_service_audience: str = Field(default="smartmentor-ai", min_length=1)

    # --- LLM and embeddings (ADR 0011, 0012): no defaults on purpose ---
    ai_llm_provider: LlmProviderName | None = None
    ai_llm_model_default: str | None = None
    ai_llm_model_small: str | None = None
    ai_embedding_provider: EmbeddingProviderName | None = None
    ai_embedding_model: str | None = None
    embedding_dimension: int | None = Field(default=None, ge=1, le=2000)
    gemini_api_key: SecretStr | None = None
    anthropic_api_key: SecretStr | None = None
    # 240 s (B-013): con 120 s, los bancos de preguntas (`items.generate_quiz_bank`,
    # `items.generate_final_bank`, `diagnostic.generate_items`) se cortaban a menudo con Gemini.
    ai_llm_timeout_seconds: float = Field(default=240.0, gt=0)

    # --- Budget in USD (plan 18.5): empty = not configured ---
    ai_daily_budget_usd: Decimal | None = Field(default=None, ge=0)
    ai_monthly_budget_usd: Decimal | None = Field(default=None, ge=0)
    ai_course_budget_usd: Decimal | None = Field(default=None, ge=0)
    ai_enrollment_budget_usd: Decimal | None = Field(default=None, ge=0)

    # --- Files ---
    ai_prompts_dir: Path = REPO_ROOT / "prompts"
    ai_prices_file: Path = AI_ROOT / "config" / "prices.yaml"

    # --- Worker (ADR 0010) ---
    ai_worker_poll_seconds: float = Field(default=2.0, gt=0)
    # El lease no se renueva mientras el trabajo corre: debe cubrir una llamada con sus reintentos
    # (3 intentos x 240 s, B-013). Solo retrasa la recuperación si un trabajador se cae.
    ai_job_lock_seconds: int = Field(default=1800, ge=10)
    ai_job_max_attempts: int = Field(default=3, ge=1)
    ai_job_retry_backoff_seconds: int = Field(default=30, ge=0)

    # --- Videos (ADR 0016, R-001) ---
    # La colecta es por tema y la comparte todo el curso: el inglés entra como respaldo del
    # español, con un puntaje de idioma menor (el español puntúa 1). Valor inicial sin validar
    # (plan 4.3). El español se prefiere siempre; con AI_VIDEO_ENGLISH_FALLBACK=false se descarta.
    ai_video_english_fallback: bool = True
    ai_video_english_score: float = Field(default=0.3, ge=0, le=1)
    # B-064: resultados que se piden a YouTube por búsqueda. La cuota se cobra por búsqueda, no
    # por resultado (hasta 50 por página), así que pedir 50 cuesta lo mismo que pedir 15.
    ai_video_search_results: int = Field(default=50, ge=1, le=50)
    # B-064: duración máxima de un video, en minutos (regla del primer corte: 40 o menos).
    ai_video_max_minutes: int = Field(default=40, ge=5, le=180)

    # 1 = the evaluation harness may call the real LLM (never in CI).
    ai_eval_live: bool = False

    # --- Nivel del diagnóstico (R-002, experimento E4) ---
    # Cómo la similitud perfil↔tema se vuelve prior: minmax (actual, por defecto) o absolute
    # (variante (c), lineal recortado entre los dos umbrales). Los umbrales por defecto son los de
    # app.domain.leveling.PriorScale, donde está su justificación; una prueba los mantiene iguales.
    ai_leveling_prior_scale: Literal["minmax", "absolute"] = "minmax"
    ai_leveling_similarity_floor: float = Field(default=0.5, ge=-1, le=1)
    ai_leveling_similarity_ceiling: float = Field(default=0.8, ge=-1, le=1)

    # --- Recuperación (RAG, R-005, experimento E5) ---
    # Fragmentos que se recuperan por explicación. Subirlo da más contexto (y más costo de LLM);
    # el caché de generación no cambia: su clave ya incluye los fragmentos recuperados.
    ai_rag_top_k: int = Field(default=4, ge=1, le=20)

    @field_validator(
        "ai_database_user",
        "ai_database_password",
        "oidc_issuer_url",
        "oidc_jwks_url",
        "ai_llm_provider",
        "ai_llm_model_default",
        "ai_llm_model_small",
        "ai_embedding_provider",
        "ai_embedding_model",
        "embedding_dimension",
        "gemini_api_key",
        "anthropic_api_key",
        "ai_daily_budget_usd",
        "ai_monthly_budget_usd",
        "ai_course_budget_usd",
        "ai_enrollment_budget_usd",
        mode="before",
    )
    @classmethod
    def _blank_is_missing(cls, value: object) -> object:
        return _empty_to_none(value)

    @model_validator(mode="after")
    def _check_similarity_band(self) -> Self:
        if self.ai_leveling_similarity_floor >= self.ai_leveling_similarity_ceiling:
            raise ValueError(
                "AI_LEVELING_SIMILARITY_FLOOR must be lower than AI_LEVELING_SIMILARITY_CEILING"
            )
        return self

    @property
    def database_configured(self) -> bool:
        return self.ai_database_user is not None and self.ai_database_password is not None

    @property
    def database_url(self) -> str:
        if self.ai_database_user is None or self.ai_database_password is None:
            raise RuntimeError("AI_DATABASE_USER and AI_DATABASE_PASSWORD are not set")
        user = quote_plus(self.ai_database_user)
        password = quote_plus(self.ai_database_password.get_secret_value())
        return (
            f"postgresql+asyncpg://{user}:{password}"
            f"@{self.database_host}:{self.database_port}/{self.database_name}"
            f"{'?ssl=require' if self.database_ssl else ''}"
        )

    @property
    def uses_real_llm(self) -> bool:
        return self.ai_llm_provider in REAL_LLM_PROVIDERS

    def configured_models(self) -> list[str]:
        """Model names that must have a price (LLM tiers and embeddings)."""
        names = [self.ai_llm_model_default, self.ai_llm_model_small, self.ai_embedding_model]
        return sorted({n for n in names if n})

    def missing_configuration(self) -> list[str]:
        """Variables whose absence makes ``/ready`` fail (no defaults in code)."""
        missing: list[str] = []
        required: tuple[tuple[str, object], ...] = (
            ("AI_LLM_PROVIDER", self.ai_llm_provider),
            ("AI_LLM_MODEL_DEFAULT", self.ai_llm_model_default),
            ("AI_LLM_MODEL_SMALL", self.ai_llm_model_small),
            ("AI_EMBEDDING_PROVIDER", self.ai_embedding_provider),
            ("AI_EMBEDDING_MODEL", self.ai_embedding_model),
            ("EMBEDDING_DIMENSION", self.embedding_dimension),
            ("OIDC_ISSUER_URL", self.oidc_issuer_url),
            ("OIDC_JWKS_URL", self.oidc_jwks_url),
        )
        missing += [name for name, value in required if value is None]
        if self.ai_llm_provider == "gemini" and self.gemini_api_key is None:
            missing.append("GEMINI_API_KEY")
        if self.ai_llm_provider == "anthropic" and self.anthropic_api_key is None:
            missing.append("ANTHROPIC_API_KEY")
        if self.ai_embedding_provider == "gemini" and self.gemini_api_key is None:
            missing.append("GEMINI_API_KEY")
        if self.uses_real_llm:
            # A real provider spends money: every cap must be set (.env.example, plan 18.5).
            missing += [
                name
                for name, value in (
                    ("AI_DAILY_BUDGET_USD", self.ai_daily_budget_usd),
                    ("AI_MONTHLY_BUDGET_USD", self.ai_monthly_budget_usd),
                    ("AI_COURSE_BUDGET_USD", self.ai_course_budget_usd),
                    ("AI_ENROLLMENT_BUDGET_USD", self.ai_enrollment_budget_usd),
                )
                if value is None
            ]
        return sorted(set(missing))


@lru_cache
def get_settings() -> Settings:
    return Settings()
