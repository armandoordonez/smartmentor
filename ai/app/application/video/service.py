"""``video.collect_candidates`` and ``video.rank`` (plan 5.4.9, ADR 0016).

Chain: YouTube search (``relevanceLanguage``, ``videoEmbeddable``) + the instructor's list ->
characterisation by metadata with the closed list of subtopics -> embeddings -> score (similarity
with the topic + language and duration adjustments, ``domain/video_ranking.py``) -> top 3 (the
selected video and two backups). A topic is never left without a video silently: with no key and
no instructor list the resource has ``origin = none`` (L-08) and the instructor must add one.
"""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Sequence
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.application.content.context import TaskContext, TaskResult, load_topic
from app.application.llm_runner import CallContext, EmbeddingRunner
from app.application.video.characterize import covered_subtopics, video_embedding_text
from app.domain.contracts.video import (
    CharacterizationSource,
    VideoCandidate,
    VideoResource,
    VideoSearchSummary,
)
from app.domain.errors import TaskError
from app.domain.video_ranking import (
    MAX_DURATION_SECONDS,
    Rankable,
    Ranked,
    RankingPreferences,
    rank_videos,
    select_with_backups,
)
from app.ports.catalog import CatalogReader, TopicRecord
from app.ports.embedding import EmbeddingPurpose
from app.ports.video import (
    TranscriptProvider,
    VideoSearchHit,
    VideoSearchProvider,
    VideoSearchQuery,
    VideoSearchUnavailableError,
)

logger = logging.getLogger("app.video")

VIDEO_CONTRACT = "video_resource.v1"
WATCH_URL = "https://www.youtube.com/watch?v={video_id}"
SIMILARITY_PURPOSE: EmbeddingPurpose = "similarity"
SEARCH_RESULTS = 50  # B-064: the quota is per search call, not per result (up to 50)
QUERY_SUBTOPICS = 2
# B-064: with the topic name and two subtopics YouTube often returns nothing (0 for «Fundamentos de
# MLOps» on 2026-11-16). Below this many results a second, broader search is made.
FALLBACK_BELOW = 5


class InstructorVideo(BaseModel):
    youtube_video_id: str = Field(pattern=r"^[A-Za-z0-9_-]{11}$")
    title: str = Field(min_length=1)


class CollectInput(BaseModel):
    topic_id: str
    language: str = Field(default="es", pattern=r"^[a-z]{2}$")
    instructor_videos: list[InstructorVideo] = Field(default_factory=list, max_length=20)


class PreferencesInput(BaseModel):
    language: str = Field(default="es", pattern=r"^[a-z]{2}$")
    min_duration_seconds: int = Field(default=240, ge=1)
    max_duration_seconds: int = Field(default=MAX_DURATION_SECONDS, ge=1)
    english_allowed: bool = False

    def to_domain(self) -> RankingPreferences:
        return RankingPreferences(
            language=self.language,
            min_duration_seconds=self.min_duration_seconds,
            max_duration_seconds=self.max_duration_seconds,
            english_allowed=self.english_allowed,
        )


class CandidateInput(BaseModel):
    """A characterised candidate (``VideoCandidate`` without ``rank``) sent to ``video.rank``."""

    youtube_video_id: str = Field(pattern=r"^[A-Za-z0-9_-]{11}$")
    title: str = Field(min_length=1)
    url: str = ""
    channel: str = ""
    origin: Literal["youtube_api", "instructor"] = "youtube_api"
    duration_seconds: int | None = Field(default=None, ge=1)
    language: str | None = Field(default=None, pattern=r"^[a-z]{2}$")
    has_captions: bool | None = None
    characterization: str | None = None
    characterization_source: CharacterizationSource | None = None
    similarity: float | None = Field(default=None, ge=-1, le=1)
    search_position: int | None = Field(default=None, ge=1)


class RankInput(BaseModel):
    topic_id: str
    candidates: list[CandidateInput] = Field(default_factory=list, max_length=50)
    preferences: PreferencesInput = Field(default_factory=PreferencesInput)


def _search_text(topic: TopicRecord) -> str:
    return " ".join([topic.name, *topic.subtopics[:QUERY_SUBTOPICS]])


def _fallback_text(topic: TopicRecord) -> str:
    """The topic name with the course as context (B-064).

    A generic topic name («Fundamentos e instalación») needs its course («Curso de Claude Code»)
    to find relevant videos. The course name is cut at « - » (subtitles like the group) and left
    out if the topic name already contains it.
    """
    course = topic.course_name.split(" - ")[0].strip()
    if not course or course.lower() in topic.name.lower():
        return topic.name
    return f"{topic.name} {course}"


def search_texts(topic: TopicRecord) -> list[str]:
    """The precise query first and the broad one as fallback, without repeating a query."""
    return list(dict.fromkeys([_search_text(topic), _fallback_text(topic)]))


class VideoRecommender:
    def __init__(
        self,
        *,
        catalog: CatalogReader,
        search: VideoSearchProvider | None,
        transcripts: TranscriptProvider,
        embeddings: EmbeddingRunner,
        english_fallback: bool = True,
        english_score: float = 0.3,
        search_results: int = SEARCH_RESULTS,
        max_duration_seconds: int = MAX_DURATION_SECONDS,
    ) -> None:
        # La colecta es por tema (la comparte todo el curso): el inglés es respaldo, no descarte.
        self._english_fallback = english_fallback
        self._english_score = english_score
        self._search_results = search_results
        self._max_duration_seconds = max_duration_seconds
        self._catalog = catalog
        self._search = search
        self._transcripts = transcripts
        self._embeddings = embeddings

    # ---------- video.collect_candidates ----------

    async def _hits(
        self, topic: TopicRecord, data: CollectInput
    ) -> tuple[list[VideoSearchHit], list[str]]:
        """YouTube results and the queries made (none without a key).

        The precise query goes first; if it returns fewer than ``FALLBACK_BELOW`` videos, the
        broad one adds its results after them (without repeating videos).
        """
        if self._search is None:
            return [], []
        hits: list[VideoSearchHit] = []
        queries: list[str] = []
        for text in search_texts(topic):
            if queries and len(hits) >= FALLBACK_BELOW:
                break
            query = VideoSearchQuery(
                text=text,
                language=data.language,
                max_results=self._search_results,
                embeddable_only=True,
            )
            try:
                found = await self._search.search(query)
            except VideoSearchUnavailableError as exc:
                if hits or data.instructor_videos:
                    logger.warning("video search unavailable; keeping what was found")
                    break
                raise TaskError("VIDEO_SEARCH_UNAVAILABLE", "the video search failed") from exc
            queries.append(text)
            seen = {h.youtube_video_id for h in hits}
            hits += [h for h in found if h.youtube_video_id not in seen]
        return hits, queries

    def _collect_prefs(self, data: CollectInput) -> RankingPreferences:
        return RankingPreferences(
            language=data.language,
            max_duration_seconds=self._max_duration_seconds,
            english_allowed=self._english_fallback,
            english_score=self._english_score,
        )

    async def collect(self, data: CollectInput, ctx: CallContext) -> VideoResource:
        topic = await load_topic(self._catalog, data.topic_id)
        instructor_ids = {v.youtube_video_id for v in data.instructor_videos}
        searched, queries = await self._hits(topic, data)
        hits = [h for h in searched if h.youtube_video_id not in instructor_ids]
        found = len(hits)
        # E6: posición en los resultados de YouTube (1 = el primero), la línea base del ranking.
        positions = {h.youtube_video_id: n for n, h in enumerate(hits, start=1)}
        hits += [
            VideoSearchHit(
                youtube_video_id=v.youtube_video_id,
                title=v.title,
                channel_title="",
                description="",
                duration_seconds=None,
                language=None,
            )
            for v in data.instructor_videos
        ]
        if not hits:
            return self._resource(
                topic.id,
                [],
                [],
                self._collect_prefs(data),
                VideoSearchSummary(found=0, queries=queries),
            )

        texts: list[str] = []
        covered_by_id: dict[str, list[str]] = {}
        sources: dict[str, CharacterizationSource] = {}
        for hit in hits:
            transcript = await self._transcripts.transcript(hit)
            covered = covered_subtopics(topic.subtopics, transcript.text)
            covered_by_id[hit.youtube_video_id] = covered
            sources[hit.youtube_video_id] = (
                "instructor"
                if hit.youtube_video_id in instructor_ids
                else ("transcript" if transcript.source == "captions" else "metadata")
            )
            texts.append(video_embedding_text(hit, transcript, covered))
        vectors = await self._embeddings.embed(
            [topic.similarity_text(), *texts], SIMILARITY_PURPOSE, ctx
        )
        topic_vector = vectors[0]
        rankables = [
            Rankable(
                video_id=hit.youtube_video_id,
                similarity=_dot(topic_vector, vectors[i + 1]),
                language=hit.language,
                duration_seconds=hit.duration_seconds,
                trusted=hit.youtube_video_id in instructor_ids,
            )
            for i, hit in enumerate(hits)
        ]
        prefs = self._collect_prefs(data)
        ranked, excluded = rank_videos(rankables, prefs)
        if excluded:
            logger.info("candidates excluded by filters", extra={"excluded": excluded})
        by_id = {h.youtube_video_id: h for h in hits}
        candidates = [
            VideoCandidate(
                youtube_video_id=r.video_id,
                title=by_id[r.video_id].title,
                url=WATCH_URL.format(video_id=r.video_id),
                channel=by_id[r.video_id].channel_title,
                origin="instructor" if r.video_id in instructor_ids else "youtube_api",
                duration_seconds=by_id[r.video_id].duration_seconds,
                language=by_id[r.video_id].language,
                has_captions=None,
                characterization=", ".join(covered_by_id[r.video_id]) or None,
                characterization_source=sources[r.video_id],
                similarity=round(max(-1.0, min(1.0, r.similarity)), 4),
                rank=rank,
                search_position=positions.get(r.video_id),
            )
            for rank, r in enumerate(ranked, start=1)
        ]
        summary = VideoSearchSummary(
            found=found, excluded=dict(Counter(excluded.values())), queries=queries
        )
        return self._resource(topic.id, candidates, ranked, prefs, summary)

    # ---------- video.rank ----------

    async def rank(self, data: RankInput, ctx: CallContext) -> VideoResource:
        topic = await load_topic(self._catalog, data.topic_id)
        prefs = data.preferences.to_domain()
        similarity = {c.youtube_video_id: c.similarity for c in data.candidates}
        missing = [c for c in data.candidates if c.similarity is None]
        if missing:
            texts = [c.characterization or c.title for c in missing]
            vectors = await self._embeddings.embed(
                [
                    topic.similarity_text(),
                    *[f"{c.title}. {t}" for c, t in zip(missing, texts, strict=True)],
                ],
                SIMILARITY_PURPOSE,
                ctx,
            )
            for c, vector in zip(missing, vectors[1:], strict=True):
                similarity[c.youtube_video_id] = _dot(vectors[0], vector)
        rankables = [
            Rankable(
                video_id=c.youtube_video_id,
                similarity=similarity[c.youtube_video_id] or 0.0,
                language=c.language,
                duration_seconds=c.duration_seconds,
                trusted=c.origin == "instructor",
            )
            for c in data.candidates
        ]
        ranked, _ = rank_videos(rankables, prefs)
        by_id = {c.youtube_video_id: c for c in data.candidates}
        candidates = [
            VideoCandidate(
                youtube_video_id=r.video_id,
                title=by_id[r.video_id].title,
                url=by_id[r.video_id].url or WATCH_URL.format(video_id=r.video_id),
                channel=by_id[r.video_id].channel,
                origin=by_id[r.video_id].origin,
                duration_seconds=by_id[r.video_id].duration_seconds,
                language=by_id[r.video_id].language,
                has_captions=by_id[r.video_id].has_captions,
                characterization=by_id[r.video_id].characterization,
                characterization_source=by_id[r.video_id].characterization_source,
                similarity=round(max(-1.0, min(1.0, r.similarity)), 4),
                rank=rank,
                search_position=by_id[r.video_id].search_position,
            )
            for rank, r in enumerate(ranked, start=1)
        ]
        return self._resource(topic.id, candidates, ranked, prefs)

    # ---------- result ----------

    def _resource(
        self,
        topic_id: str,
        candidates: list[VideoCandidate],
        ranked: Sequence[Ranked],
        prefs: RankingPreferences,
        summary: VideoSearchSummary | None = None,
    ) -> VideoResource:
        if not candidates:
            return VideoResource(
                topic_id=topic_id,
                origin="none",
                embedding_model=self._embeddings.model,
                candidates=[],
                search_summary=summary,
            )
        selected, backups = select_with_backups(ranked, prefs.backup_count)
        origin = next(c.origin for c in candidates if c.youtube_video_id == selected)
        return VideoResource(
            topic_id=topic_id,
            origin=origin,
            embedding_model=self._embeddings.model,
            candidates=candidates,
            selected_video_id=selected,
            backup_video_ids=backups,
            search_summary=summary,
        )


def _dot(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine similarity of two L2-normalised vectors."""
    return sum(x * y for x, y in zip(a, b, strict=True))


class CollectCandidatesTask:
    job_type = "video.collect_candidates"

    def __init__(self, recommender: VideoRecommender, catalog: CatalogReader) -> None:
        self._recommender = recommender
        self._catalog = catalog

    async def run(self, raw: dict[str, Any], ctx: TaskContext) -> TaskResult:
        data = CollectInput.model_validate(raw)
        topic = await load_topic(self._catalog, data.topic_id)
        resource = await self._recommender.collect(
            data, ctx.call(self.job_type, course_id=topic.course_id)
        )
        return TaskResult(VIDEO_CONTRACT, resource.model_dump(mode="json"))


class RankTask:
    """``video.rank`` (synchronous in the HTTP service)."""

    job_type = "video.rank"

    def __init__(self, recommender: VideoRecommender) -> None:
        self._recommender = recommender

    async def run(self, raw: dict[str, Any], ctx: TaskContext) -> TaskResult:
        resource = await self._recommender.rank(
            RankInput.model_validate(raw), ctx.call(self.job_type)
        )
        return TaskResult(VIDEO_CONTRACT, resource.model_dump(mode="json"))
