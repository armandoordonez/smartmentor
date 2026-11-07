"""``VideoSearchProvider`` and ``TranscriptProvider`` ports (plan 5.4.9).

Implemented in Phase 5 (YouTube Data API and ``metadata_transcripts``). Only the shape lives
here so the Phase 5 adapters and the fakes agree.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class VideoSearchQuery:
    text: str
    language: str = "es"
    max_results: int = 15
    embeddable_only: bool = True


@dataclass(frozen=True)
class VideoSearchHit:
    youtube_video_id: str
    title: str
    channel_title: str
    description: str
    duration_seconds: int | None
    language: str | None
    published_at: str | None = None
    chapters: list[str] = field(default_factory=list)


class VideoSearchUnavailableError(Exception):
    """The search failed (quota, network): ``VIDEO_SEARCH_UNAVAILABLE`` if no fallback exists."""


class VideoSearchProvider(Protocol):
    @property
    def name(self) -> str: ...

    async def search(self, query: VideoSearchQuery) -> list[VideoSearchHit]: ...


@dataclass(frozen=True)
class Transcript:
    youtube_video_id: str
    text: str
    source: str  # "metadata" (title, description, chapters) or "captions" (only if DEF-07)


class TranscriptProvider(Protocol):
    @property
    def name(self) -> str: ...

    async def transcript(self, video: VideoSearchHit) -> Transcript: ...
