"""Builds the content services from the pieces of the container (one call from ``container.py``).

Two settings are read straight from the environment because ``core/config.py`` belongs to
``ai-base``: ``AI_SOURCES_DIR`` (reference documents per course, see ``DirectorySourceReader``;
default ``ai/sources``) and ``YOUTUBE_API_KEY`` (empty: videos come only from the instructor's
list, L-08). Proposal: add both to ``Settings`` and to ``.env.example``.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import httpx
from sqlalchemy.ext.asyncio import AsyncEngine

from app.adapters.memory_knowledge import InMemoryKnowledgeStore
from app.adapters.metadata_transcripts import MetadataTranscriptProvider
from app.adapters.youtube import YouTubeSearchProvider
from app.application.content.registry import ContentDeps, ContentServices, build_content_services
from app.application.embeddings.sources import (
    CombinedSourceReader,
    DirectorySourceReader,
    SourceMaterialReader,
)
from app.application.embeddings.store import KnowledgeStore
from app.application.llm_runner import EmbeddingRunner, LlmRunner
from app.core.config import AI_ROOT
from app.ports.catalog import CatalogReader
from app.ports.jobs import JobRepository
from app.ports.video import VideoSearchProvider

YOUTUBE_TIMEOUT_SECONDS = 20.0


def build_content_for_container(
    *,
    runner: LlmRunner,
    embedding_runner: EmbeddingRunner,
    catalog: CatalogReader,
    jobs: JobRepository,
    clock: Callable[[], datetime],
    engine: AsyncEngine | None,
) -> ContentServices:
    sources_dir = Path(os.environ.get("AI_SOURCES_DIR") or AI_ROOT / "sources")
    knowledge: KnowledgeStore
    sources: SourceMaterialReader
    if engine is not None:
        from app.adapters.pg_knowledge import PgKnowledgeStore
        from app.adapters.postgres.syllabus_sources import PostgresSyllabusSourceReader

        knowledge = PgKnowledgeStore(engine)
        # El syllabus del curso es la fuente mínima del RAG; la carpeta agrega apuntes (DEF-08).
        sources = CombinedSourceReader(
            PostgresSyllabusSourceReader(engine), DirectorySourceReader(sources_dir)
        )
    else:
        knowledge = InMemoryKnowledgeStore()
        sources = DirectorySourceReader(sources_dir)
    search: VideoSearchProvider | None = None
    if key := os.environ.get("YOUTUBE_API_KEY", "").strip():
        search = YouTubeSearchProvider(key, httpx.AsyncClient(timeout=YOUTUBE_TIMEOUT_SECONDS))
    return build_content_services(
        ContentDeps(
            runner=runner,
            embeddings=embedding_runner,
            catalog=catalog,
            knowledge=knowledge,
            sources=sources,
            jobs=jobs,
            transcripts=MetadataTranscriptProvider(),
            clock=clock,
            video_search=search,
        )
    )
