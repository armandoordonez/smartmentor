"""Video of a topic: result of ``video.collect_candidates`` and ``video.rank`` (no LLM prompt)."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import Field, model_validator

from app.domain.contracts.common import ContractModel

CharacterizationSource = Literal["metadata", "transcript", "instructor"]


class VideoCandidate(ContractModel):
    youtube_video_id: str = Field(pattern=r"^[A-Za-z0-9_-]{11}$")
    title: str = Field(min_length=1)
    url: str
    channel: str = ""
    origin: Literal["youtube_api", "instructor"]
    duration_seconds: int | None = Field(default=None, ge=1)
    language: str | None = Field(default=None, pattern=r"^[a-z]{2}$", description="ISO 639-1")
    has_captions: bool | None = None
    characterization: str | None = Field(
        default=None, description="Subtopics the video covers (closed list of the topic)"
    )
    characterization_source: CharacterizationSource | None = None
    similarity: float | None = Field(default=None, ge=-1, le=1, description="Cosine vs topic")
    rank: int = Field(ge=1)
    search_position: int | None = Field(
        default=None,
        ge=1,
        description="Position in the YouTube search results (1 = first); E6 baseline. "
        "None for the instructor's videos",
    )
    relevance_judgment: bool | None = Field(
        default=None, description="Instructor judgement for P@3 and nDCG@3 (D5e)"
    )


class VideoSearchSummary(ContractModel):
    """What the YouTube search returned and why the filters dropped videos (B-064)."""

    found: int = Field(ge=0, description="Videos returned by the YouTube search")
    excluded: dict[str, int] = Field(
        default_factory=dict,
        description="Videos dropped by the knowledge filters, by reason "
        "(duration_out_of_range, language_not_understood)",
    )
    queries: list[str] = Field(
        default_factory=list,
        description="Queries sent to YouTube, in order; empty when there is no YouTube key",
    )


class VideoResource(ContractModel):
    topic_id: str
    origin: Literal["youtube_api", "instructor", "none"] = Field(
        description="none = no API key and no instructor list (L-08)"
    )
    embedding_model: str
    candidates: list[VideoCandidate]
    selected_video_id: str | None = None
    backup_video_ids: list[str] = Field(default_factory=list)
    search_summary: VideoSearchSummary | None = Field(
        default=None, description="Only in video.collect_candidates (B-064): why there are few"
    )

    @model_validator(mode="after")
    def _check_ranking(self) -> Self:
        if (self.origin == "none") != (not self.candidates):
            raise ValueError("origin none <=> no candidates")
        ranks = sorted(c.rank for c in self.candidates)
        if ranks != list(range(1, len(self.candidates) + 1)):
            raise ValueError("candidate ranks must be 1..n without repetition")
        ids = {c.youtube_video_id for c in self.candidates}
        if len(ids) != len(self.candidates):
            raise ValueError("a video appears more than once")
        if self.selected_video_id is not None and self.selected_video_id not in ids:
            raise ValueError("selected_video_id must be one of the candidates")
        if self.candidates and self.selected_video_id is None:
            raise ValueError("a resource with candidates selects one")
        backups = set(self.backup_video_ids)
        if not backups <= ids or self.selected_video_id in backups:
            raise ValueError("backups are candidates different from the selected video")
        return self
