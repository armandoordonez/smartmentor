"""Fixtures of the content tests: a world with the fakes and the syllabus already structured."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.adapters.fake_embedding import FakeEmbeddingProvider
from app.adapters.fake_llm import FakeLlmProvider
from eval.pipeline import DEFAULT_SYLLABUS, EvalWorld, PipelineOptions
from eval.runtime import EvalRuntime, build_fake_runtime


@pytest.fixture
def runtime() -> EvalRuntime:
    return build_fake_runtime()


@pytest.fixture
def llm(runtime: EvalRuntime) -> FakeLlmProvider:
    assert runtime.fake_llm is not None
    return runtime.fake_llm


@pytest.fixture
def embedder(runtime: EvalRuntime) -> FakeEmbeddingProvider:
    assert isinstance(runtime.embedder, FakeEmbeddingProvider)
    return runtime.embedder


@pytest.fixture
async def world(runtime: EvalRuntime, tmp_path: Path) -> EvalWorld:
    options = PipelineOptions(
        syllabus_text=DEFAULT_SYLLABUS.read_text(encoding="utf-8"), out_dir=tmp_path
    )
    built = EvalWorld(options, runtime)
    await built.structure_syllabus()
    return built
