"""Observabilidad de solo lectura: registro de llamadas al LLM y métricas de evaluación (AD2, AD3).

`GET /metrics/evaluation` calcula lo que se puede obtener con SQL y las vistas (F1 de la extracción,
validez y κ de los ítems, QWK, fidelidad, P@3 y nDCG@3, latencia y costo del LLM, aprobación al
primer intento). El resto (AUC, RAGAS, dificultad y discriminación) lo publica el notebook.
"""

from dataclasses import dataclass, field
from typing import Protocol

from app.common.constants import RoleCode
from app.common.exceptions import NotFoundError
from app.domains.courses.service import ExtractionMetrics
from app.domains.identity.authentication import CurrentUser
from app.domains.observability import metrics
from app.domains.observability.entities import (
    ItemValidityRow,
    LlmCallLog,
    LlmStats,
    LogFilters,
    LogSummary,
    PathScope,
    StepStats,
    VideoTopicRanking,
)
from app.domains.observability.repository import ObservabilityRepository

QWK_CATEGORIES = 5
PRECISION_K = 3


class ExtractionSource(Protocol):
    async def metrics(self, user: CurrentUser, course_id: int) -> ExtractionMetrics: ...


class LogService:
    def __init__(self, repository: ObservabilityRepository) -> None:
        self._repository = repository

    async def search(
        self, filters: LogFilters, *, limit: int, offset: int
    ) -> tuple[list[LlmCallLog], int]:
        return await self._repository.search_logs(filters, limit=limit, offset=offset)

    async def summary(self, filters: LogFilters) -> LogSummary:
        return await self._repository.summarize_logs(filters)


@dataclass(frozen=True)
class CourseExtraction:
    course_id: int
    topics_f1: float | None
    prerequisites_f1: float | None
    corrections: int


@dataclass(frozen=True)
class ItemValidityMetrics:
    items: int
    annotated_items: int
    valid_votes: int
    invalid_votes: int
    valid_rate: float | None
    items_with_two_evaluators: int
    cohen_kappa: float | None


@dataclass(frozen=True)
class GradingMetrics:
    graded_by_human: int
    qwk: float | None


@dataclass(frozen=True)
class FaithfulnessMetrics:
    versions_measured: int
    mean: float | None


@dataclass(frozen=True)
class VideoMetrics:
    topics_judged: int
    topics_incomplete: int
    precision_at_3: float | None
    ndcg_at_3: float | None


@dataclass(frozen=True)
class EvaluationMetrics:
    learning_path_ids: list[int]
    extraction: list[CourseExtraction] = field(default_factory=list)
    item_validity: ItemValidityMetrics | None = None
    grading: GradingMetrics | None = None
    faithfulness: FaithfulnessMetrics | None = None
    videos: VideoMetrics | None = None
    llm: "LlmMetrics | None" = None
    steps: "StepMetrics | None" = None


@dataclass(frozen=True)
class LlmMetrics:
    calls: int
    invalid_json_rate: float | None
    cache_hit_rate: float | None
    latency_p95_ms: float | None
    cost_usd: float


@dataclass(frozen=True)
class StepMetrics:
    steps_passed: int
    first_attempt_pass_rate: float | None
    avg_attempts_used: float | None
    attempts_exhausted: int


def _validity(rows: list[ItemValidityRow]) -> ItemValidityMetrics:
    valid = sum(r.valid_votes for r in rows)
    invalid = sum(r.invalid_votes for r in rows)
    pairs = [
        (r.slot1_verdict, r.slot2_verdict) for r in rows if r.slot1_verdict and r.slot2_verdict
    ]
    return ItemValidityMetrics(
        items=len(rows),
        annotated_items=sum(1 for r in rows if r.valid_votes + r.invalid_votes > 0),
        valid_votes=valid,
        invalid_votes=invalid,
        valid_rate=round(valid / (valid + invalid), 4) if valid + invalid else None,
        items_with_two_evaluators=len(pairs),
        cohen_kappa=metrics.cohen_kappa([(a, b) for a, b in pairs if a and b]),
    )


def _videos(rankings: list[VideoTopicRanking]) -> VideoMetrics:
    precision: list[float | None] = []
    ndcg: list[float | None] = []
    incomplete = 0
    for ranking in rankings:
        top = ranking.relevance[:PRECISION_K]
        if not top or any(r is None for r in top):
            incomplete += 1  # P@3 exige el juicio de los tres primeros
            continue
        judged = [bool(r) for r in ranking.relevance if r is not None]
        precision.append(metrics.precision_at_k(judged, PRECISION_K))
        ndcg.append(metrics.ndcg_at_k(judged, PRECISION_K))
    return VideoMetrics(
        topics_judged=len(precision),
        topics_incomplete=incomplete,
        precision_at_3=metrics.mean(precision),
        ndcg_at_3=metrics.mean(ndcg),
    )


def _llm(stats: LlmStats) -> LlmMetrics:
    return LlmMetrics(
        calls=stats.calls,
        invalid_json_rate=round(stats.invalid_outputs / stats.calls, 4) if stats.calls else None,
        cache_hit_rate=round(stats.cache_hits / stats.calls, 4) if stats.calls else None,
        latency_p95_ms=stats.latency_p95_ms,
        cost_usd=stats.cost_usd,
    )


def _steps(stats: StepStats) -> StepMetrics:
    return StepMetrics(
        steps_passed=stats.steps_passed,
        first_attempt_pass_rate=(
            round(stats.passed_first_attempt / stats.steps_passed, 4)
            if stats.steps_passed
            else None
        ),
        avg_attempts_used=stats.avg_attempts_used,
        attempts_exhausted=stats.attempts_exhausted,
    )


class MetricsService:
    def __init__(self, repository: ObservabilityRepository, extraction: ExtractionSource) -> None:
        self._repository = repository
        self._extraction = extraction

    async def _scope(self, user: CurrentUser, learning_path_id: int | None) -> list[PathScope]:
        is_admin = user.has_any_role(RoleCode.ADMIN)
        found = await self._repository.scope(
            owner_user_id=None if is_admin else user.id, learning_path_id=learning_path_id
        )
        if learning_path_id is not None and not found:
            # Una ruta ajena es indistinguible de una inexistente.
            raise NotFoundError("Learning path", learning_path_id)
        return found

    async def evaluation(
        self, user: CurrentUser, learning_path_id: int | None
    ) -> EvaluationMetrics:
        scope = await self._scope(user, learning_path_id)
        courses = sorted({s.course_id for s in scope})
        paths = [s.learning_path_id for s in scope]
        extraction: list[CourseExtraction] = []
        for course_id in courses:
            found = await self._extraction.metrics(user, course_id)
            extraction.append(
                CourseExtraction(
                    course_id=course_id,
                    topics_f1=found.topics.f1 if found.topics else None,
                    prerequisites_f1=found.prerequisites.f1 if found.prerequisites else None,
                    corrections=found.corrections,
                )
            )
        pairs = await self._repository.grading_pairs(courses)
        mean_faithfulness, measured = await self._repository.faithfulness(courses)
        return EvaluationMetrics(
            learning_path_ids=paths,
            extraction=extraction,
            item_validity=_validity(await self._repository.item_validity(courses)),
            grading=GradingMetrics(
                graded_by_human=len(pairs),
                qwk=metrics.quadratic_weighted_kappa(
                    [
                        (
                            metrics.score_bucket(h, QWK_CATEGORIES),
                            metrics.score_bucket(m, QWK_CATEGORIES),
                        )
                        for h, m in pairs
                    ],
                    QWK_CATEGORIES,
                ),
            ),
            faithfulness=FaithfulnessMetrics(
                versions_measured=measured,
                mean=round(mean_faithfulness, 4) if mean_faithfulness is not None else None,
            ),
            videos=_videos(await self._repository.video_rankings(courses)),
            llm=_llm(await self._repository.llm_stats(courses)),
            steps=_steps(await self._repository.step_stats(paths)),
        )
