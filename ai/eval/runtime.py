"""Providers of an evaluation run: fakes by default, the real ones only with ``AI_EVAL_LIVE=1``.

The real LLM costs money, so ``build_live_runtime`` refuses to run unless the owner opted in with
``AI_EVAL_LIVE=1`` and the process is not in CI. The fakes need no key and no network.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass

import httpx
from google import genai

from app.adapters.fake_embedding import FakeEmbeddingProvider
from app.adapters.fake_llm import FakeLlmProvider
from app.adapters.gemini_embeddings import GeminiEmbeddingProvider
from app.adapters.youtube import YouTubeSearchProvider
from app.core.config import REPO_ROOT, Settings
from app.ports.embedding import EmbeddingProvider
from app.ports.llm import LlmProvider
from app.ports.video import (
    VideoSearchHit,
    VideoSearchProvider,
    VideoSearchQuery,
    VideoSearchUnavailableError,
)
from eval.fake_answers import install_content_fakes

EXAMPLES_DIR = REPO_ROOT / "prompts" / "examples"
FAKE_EMBEDDING_MODEL = "fake-embedding"
FAKE_EMBEDDING_DIMENSION = 64


class LiveEvaluationNotAllowedError(RuntimeError):
    """The real providers were requested without ``AI_EVAL_LIVE=1`` or inside CI."""


@dataclass
class EvalRuntime:
    provider: LlmProvider
    embedder: EmbeddingProvider
    video_search: VideoSearchProvider | None
    live: bool
    default_model: str
    small_model: str
    fake_llm: FakeLlmProvider | None = None  # scripted answers in tests


def _video_id(seed: str) -> str:
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:11]


class FakeVideoSearch:
    """Deterministic search: some good videos and others the filters must drop."""

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.queries: list[VideoSearchQuery] = []

    @property
    def name(self) -> str:
        return "fake"

    async def search(self, query: VideoSearchQuery) -> list[VideoSearchHit]:
        self.queries.append(query)
        if self.fail:
            raise VideoSearchUnavailableError("quota exceeded (fake)")
        q = query.text
        chapters = ["Introducción", "Ejemplo", "Cierre"]

        def hit(tag: str, title: str, seconds: int, lang: str | None) -> VideoSearchHit:
            return VideoSearchHit(
                youtube_video_id=_video_id(q + tag),
                title=title,
                channel_title="Canal de ejemplo",
                description=f"Explicación de {q}.",
                duration_seconds=seconds,
                language=lang,
                chapters=chapters if tag == "a" else [],
            )

        return [
            hit("a", f"{q} explicado paso a paso", 900, "es"),
            hit("b", f"{q} curso completo de varias horas", 5400, "es"),
            hit("c", f"{q} in ten minutes", 600, "en"),
            hit("d", f"Introducción a {q}", 480, "es"),
            hit("e", "Receta de cocina rápida", 600, "es"),
            hit("f", f"{q} en un minuto", 60, "es"),
        ][: query.max_results]


def _required[T](value: T | None) -> T:
    if value is None:
        raise LiveEvaluationNotAllowedError("incomplete configuration")
    return value


def build_fake_runtime() -> EvalRuntime:
    provider = install_content_fakes(FakeLlmProvider(EXAMPLES_DIR / "llm"))
    return EvalRuntime(
        provider=provider,
        fake_llm=provider,
        embedder=FakeEmbeddingProvider(FAKE_EMBEDDING_MODEL, FAKE_EMBEDDING_DIMENSION),
        video_search=FakeVideoSearch(),
        live=False,
        default_model="fake-default",
        small_model="fake-small",
    )


def build_live_runtime(settings: Settings, llm: LlmProvider) -> EvalRuntime:
    """Real providers for one evaluation run (plan 5.4.14: never in CI).

    ``llm`` is the real LLM adapter (``ai-base``); embeddings use Gemini and the video search
    uses YouTube when ``YOUTUBE_API_KEY`` is set. Without that key the run uses the instructor's
    list only (L-08).
    """
    if not settings.ai_eval_live:
        raise LiveEvaluationNotAllowedError("set AI_EVAL_LIVE=1 to call the real LLM")
    if os.environ.get("CI"):
        raise LiveEvaluationNotAllowedError("the real LLM is never called in CI")
    if missing := settings.missing_configuration():
        raise LiveEvaluationNotAllowedError(f"incomplete configuration: {missing}")
    api_key = _required(settings.gemini_api_key).get_secret_value()
    embedding_model = _required(settings.ai_embedding_model)
    dimension = _required(settings.embedding_dimension)
    default_model = _required(settings.ai_llm_model_default)
    small_model = _required(settings.ai_llm_model_small)
    client = genai.Client(api_key=api_key)
    youtube_key = os.environ.get("YOUTUBE_API_KEY")
    return EvalRuntime(
        provider=llm,
        embedder=GeminiEmbeddingProvider(client, embedding_model, dimension),
        video_search=(
            YouTubeSearchProvider(youtube_key, httpx.AsyncClient(timeout=20.0))
            if youtube_key
            else None
        ),
        live=True,
        default_model=default_model,
        small_model=small_model,
    )
