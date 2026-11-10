"""Cálculo de métricas (κ, QWK, P@3, nDCG@3) y su servicio con datos canned."""

import math

from app.domains.courses.service import ExtractionMetrics, Score
from app.domains.identity.authentication import CurrentUser
from app.domains.observability import metrics
from app.domains.observability.entities import (
    ItemValidityRow,
    LlmStats,
    LogFilters,
    LogSummary,
    PathScope,
    StepStats,
    VideoTopicRanking,
)
from app.domains.observability.service import MetricsService
from tests.unit.conftest import current


def test_cohen_kappa_known_values() -> None:
    perfect = [
        ("valid", "valid"),
        ("invalid", "invalid"),
        ("valid", "valid"),
        ("invalid", "invalid"),
    ]
    assert metrics.cohen_kappa(perfect) == 1.0
    chance = [
        ("valid", "valid"),
        ("valid", "invalid"),
        ("invalid", "valid"),
        ("invalid", "invalid"),
    ]
    assert metrics.cohen_kappa(chance) == 0.0
    # Ejemplo clásico: 20 acuerdos sí, 15 acuerdos no, 5 + 10 desacuerdos -> κ = 0.4
    classic = [("y", "y")] * 20 + [("n", "n")] * 15 + [("y", "n")] * 5 + [("n", "y")] * 10
    assert math.isclose(metrics.cohen_kappa(classic) or 0, 0.4, abs_tol=0.01)
    assert metrics.cohen_kappa([]) is None
    assert metrics.cohen_kappa([("valid", "valid")] * 3) is None  # sin varianza


def test_quadratic_weighted_kappa() -> None:
    same = [(0, 0), (1, 1), (2, 2), (3, 3), (4, 4)]
    assert metrics.quadratic_weighted_kappa(same, 5) == 1.0
    opposite = [(0, 4), (4, 0), (1, 3), (3, 1)]
    assert (metrics.quadratic_weighted_kappa(opposite, 5) or 0) < 0
    near = [(0, 1), (1, 1), (2, 2), (3, 4), (4, 4)]
    value = metrics.quadratic_weighted_kappa(near, 5)
    assert value is not None
    assert 0.8 < value < 1
    assert metrics.quadratic_weighted_kappa([], 5) is None
    assert metrics.quadratic_weighted_kappa([(1, 1), (1, 1)], 5) is None


def test_precision_and_ndcg_at_three() -> None:
    assert metrics.precision_at_k([True, False, True]) == 2 / 3
    assert metrics.precision_at_k([]) is None
    assert metrics.ndcg_at_k([True, True, True]) == 1.0
    assert metrics.ndcg_at_k([False, False, False]) is None
    worse = metrics.ndcg_at_k([False, True, True]) or 0
    better = metrics.ndcg_at_k([True, True, False]) or 0
    assert 0 < worse < better < 1.01


def test_score_buckets_cover_the_whole_scale() -> None:
    assert [metrics.score_bucket(s) for s in (0, 19.9, 20, 59.9, 80, 100)] == [0, 0, 1, 2, 4, 4]


class FakeRepository:
    def __init__(self) -> None:
        self.scope_calls: list[tuple[int | None, int | None]] = []

    async def search_logs(self, filters: LogFilters, *, limit: int, offset: int):  # type: ignore[no-untyped-def]
        return [], 0

    async def summarize_logs(self, filters: LogFilters) -> LogSummary:
        return LogSummary([], [], 0.0)

    async def scope(
        self, *, owner_user_id: int | None, learning_path_id: int | None
    ) -> list[PathScope]:
        self.scope_calls.append((owner_user_id, learning_path_id))
        if learning_path_id not in (None, 1):
            return []
        return [PathScope(1, 10)]

    async def item_validity(self, course_ids: list[int]) -> list[ItemValidityRow]:
        return [
            ItemValidityRow(2, 0, "valid", "valid"),
            ItemValidityRow(0, 2, "invalid", "invalid"),
            ItemValidityRow(1, 0, "valid", None),
            ItemValidityRow(0, 0, None, None),
        ]

    async def grading_pairs(self, course_ids: list[int]) -> list[tuple[float, float]]:
        return [(100, 100), (0, 0), (50, 60)]

    async def faithfulness(self, course_ids: list[int]) -> tuple[float | None, int]:
        return 0.91234, 4

    async def video_rankings(self, course_ids: list[int]) -> list[VideoTopicRanking]:
        return [
            VideoTopicRanking(1, [True, True, False]),
            VideoTopicRanking(2, [True, None, False]),  # falta un juicio: se excluye
        ]

    async def llm_stats(self, course_ids: list[int]) -> LlmStats:
        return LlmStats(
            calls=10, invalid_outputs=1, cache_hits=5, latency_p95_ms=900.0, cost_usd=1.5
        )

    async def step_stats(self, path_ids: list[int]) -> StepStats:
        return StepStats(steps_passed=4, passed_first_attempt=3, avg_attempts_used=1.5)


class FakeExtraction:
    async def metrics(self, user: CurrentUser, course_id: int) -> ExtractionMetrics:
        return ExtractionMetrics(Score(1, 1, 0.9), Score(None, None, None), 2)


async def test_the_service_assembles_every_metric_and_scopes_instructors_to_their_paths() -> None:
    repository = FakeRepository()
    service = MetricsService(repository, FakeExtraction())  # type: ignore[arg-type]
    result = await service.evaluation(current(2, "instructor"), None)
    assert repository.scope_calls == [(2, None)]
    assert result.learning_path_ids == [1]
    assert result.extraction[0].topics_f1 == 0.9
    assert result.extraction[0].prerequisites_f1 is None
    validity = result.item_validity
    assert validity is not None
    assert (validity.items, validity.annotated_items, validity.items_with_two_evaluators) == (
        4,
        3,
        2,
    )
    assert validity.valid_rate == round(3 / 5, 4)
    assert validity.cohen_kappa == 1.0
    assert result.grading is not None
    assert result.grading.qwk is not None
    assert result.faithfulness is not None
    assert result.faithfulness.mean == 0.9123
    assert result.videos is not None
    assert (result.videos.topics_judged, result.videos.topics_incomplete) == (1, 1)
    assert result.videos.precision_at_3 == round(2 / 3, 4)
    assert result.llm is not None
    assert result.llm.invalid_json_rate == 0.1
    assert result.steps is not None
    assert result.steps.first_attempt_pass_rate == 0.75

    await service.evaluation(current(1, "admin"), 1)
    assert repository.scope_calls[-1] == (None, 1)


async def test_a_path_that_is_not_visible_is_a_404() -> None:
    import pytest

    from app.common.exceptions import NotFoundError

    service = MetricsService(FakeRepository(), FakeExtraction())  # type: ignore[arg-type]
    with pytest.raises(NotFoundError):
        await service.evaluation(current(2, "instructor"), 99)
