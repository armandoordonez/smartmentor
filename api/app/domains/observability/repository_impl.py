"""Consultas de solo lectura de observabilidad (`llm_call_logs`, vistas y tablas de evaluación).

`smartmentor_api` solo puede leer `llm_call_logs` y las vistas (ADR 0019); nada de aquí escribe.
"""

from typing import Any

from sqlalchemy import bindparam, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.observability.entities import (
    CourseCost,
    ItemValidityRow,
    LlmCallLog,
    LlmStats,
    LogFilters,
    LogSummary,
    PathScope,
    StepStats,
    TaskSummary,
    VideoTopicRanking,
)
from app.domains.observability.models import LlmCallLogModel


def _conditions(filters: LogFilters) -> list[Any]:
    found: list[Any] = []
    if filters.task:
        found.append(LlmCallLogModel.task == filters.task)
    if filters.model:
        found.append(LlmCallLogModel.model == filters.model)
    if filters.prompt_id:
        found.append(LlmCallLogModel.prompt_id == filters.prompt_id)
    if filters.status:
        found.append(LlmCallLogModel.status == filters.status)
    return found


def _log(row: LlmCallLogModel) -> LlmCallLog:
    return LlmCallLog(
        id=row.id,
        ai_job_id=row.ai_job_id,
        enrollment_id=row.enrollment_id,
        provider=row.provider,
        task=row.task,
        model=row.model,
        prompt_id=row.prompt_id,
        prompt_version=row.prompt_version,
        input_sha256=row.input_sha256,
        json_valid=row.json_valid,
        call_attempt=row.call_attempt,
        from_cache=row.from_cache,
        input_tokens=row.input_tokens,
        output_tokens=row.output_tokens,
        cost_usd=float(row.cost_usd) if row.cost_usd is not None else None,
        latency_ms=row.latency_ms,
        status=row.status,
        error_message=row.error_message,
        created_at=row.created_at,
    )


def _in(sql: str) -> Any:
    return text(sql).bindparams(bindparam("courses", expanding=True))


class SqlAlchemyObservabilityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def search_logs(
        self, filters: LogFilters, *, limit: int, offset: int
    ) -> tuple[list[LlmCallLog], int]:
        conditions = _conditions(filters)
        total = (
            await self._session.execute(
                select(func.count()).select_from(LlmCallLogModel).where(*conditions)
            )
        ).scalar_one()
        rows = (
            (
                await self._session.execute(
                    select(LlmCallLogModel)
                    .where(*conditions)
                    .order_by(LlmCallLogModel.id.desc())
                    .limit(limit)
                    .offset(offset)
                )
            )
            .scalars()
            .all()
        )
        return [_log(r) for r in rows], int(total)

    async def summarize_logs(self, filters: LogFilters) -> LogSummary:
        conditions = _conditions(filters)
        invalid = func.count().filter(
            (LlmCallLogModel.json_valid.is_(False)) | (LlmCallLogModel.status == "invalid_output")
        )
        rows = await self._session.execute(
            select(
                LlmCallLogModel.task,
                func.count(),
                invalid,
                func.percentile_cont(0.5).within_group(LlmCallLogModel.latency_ms),
                func.percentile_cont(0.95).within_group(LlmCallLogModel.latency_ms),
                func.coalesce(func.sum(LlmCallLogModel.cost_usd), 0),
            )
            .where(*conditions)
            .group_by(LlmCallLogModel.task)
            .order_by(LlmCallLogModel.task)
        )
        by_task = [
            TaskSummary(
                task=str(task),
                calls=int(calls),
                invalid_json_rate=round(int(bad) / int(calls), 4) if calls else 0.0,
                latency_p50_ms=float(p50) if p50 is not None else None,
                latency_p95_ms=float(p95) if p95 is not None else None,
                cost_usd=float(cost),
            )
            for task, calls, bad, p50, p95, cost in rows.all()
        ]
        # Costo por curso: la vista `v_llm_cost_summary` ya une el registro con `ai_jobs`.
        per_course = await self._session.execute(
            text(
                "SELECT course_id, sum(calls), coalesce(sum(cost_usd), 0) "
                "FROM v_llm_cost_summary GROUP BY course_id ORDER BY course_id NULLS LAST"
            )
        )
        by_course = [CourseCost(c, int(n), float(cost)) for c, n, cost in per_course.all()]
        return LogSummary(by_task, by_course, round(sum(t.cost_usd for t in by_task), 6))

    async def scope(
        self, *, owner_user_id: int | None, learning_path_id: int | None
    ) -> list[PathScope]:
        rows = await self._session.execute(
            text(
                "SELECT lp.id, lp.course_id FROM learning_paths lp "
                "JOIN courses c ON c.id = lp.course_id WHERE lp.active AND c.active "
                "AND (CAST(:owner AS bigint) IS NULL OR c.owner_user_id = :owner) "
                "AND (CAST(:path AS bigint) IS NULL OR lp.id = :path) ORDER BY lp.id"
            ),
            {"owner": owner_user_id, "path": learning_path_id},
        )
        return [PathScope(int(p), int(c)) for p, c in rows.all()]

    async def item_validity(self, course_ids: list[int]) -> list[ItemValidityRow]:
        if not course_ids:
            return []
        rows = await self._session.execute(
            _in(
                "SELECT v.valid_votes, v.invalid_votes, v.slot1_verdict, v.slot2_verdict "
                "FROM v_item_validity v JOIN topics t ON t.id = v.topic_id "
                "WHERE t.course_id IN :courses AND v.review_status <> 'auto_rejected'"
            ),
            {"courses": course_ids},
        )
        return [ItemValidityRow(int(a), int(b), s1, s2) for a, b, s1, s2 in rows.all()]

    async def grading_pairs(self, course_ids: list[int]) -> list[tuple[float, float]]:
        if not course_ids:
            return []
        rows = await self._session.execute(
            _in(
                "SELECT h.score, aa.score FROM human_gradings h "
                "JOIN attempt_answers aa ON aa.id = h.attempt_answer_id "
                "JOIN assessment_items i ON i.id = aa.assessment_item_id "
                "JOIN topics t ON t.id = i.topic_id "
                "WHERE t.course_id IN :courses AND h.active AND aa.grader = 'llm_judge' "
                "AND aa.score IS NOT NULL"
            ),
            {"courses": course_ids},
        )
        return [(float(h), float(m)) for h, m in rows.all()]

    async def faithfulness(self, course_ids: list[int]) -> tuple[float | None, int]:
        if not course_ids:
            return None, 0
        row = (
            await self._session.execute(
                _in(
                    "SELECT avg(r.faithfulness), count(r.faithfulness) FROM resources r "
                    "JOIN topics t ON t.id = r.topic_id WHERE t.course_id IN :courses "
                    "AND r.active AND r.resource_type = 'text' AND r.review_status <> 'retired'"
                ),
                {"courses": course_ids},
            )
        ).one()
        return (float(row[0]) if row[0] is not None else None), int(row[1])

    async def video_rankings(self, course_ids: list[int]) -> list[VideoTopicRanking]:
        if not course_ids:
            return []
        rows = await self._session.execute(
            _in(
                "SELECT v.topic_id, v.rank, avg(CASE WHEN j.is_relevant THEN 1.0 ELSE 0.0 END) "
                "FROM video_candidates v JOIN topics t ON t.id = v.topic_id "
                "LEFT JOIN video_relevance_judgments j "
                "  ON j.video_candidate_id = v.id AND j.active "
                "WHERE t.course_id IN :courses AND v.active AND v.rank IS NOT NULL "
                "GROUP BY v.topic_id, v.id, v.rank ORDER BY v.topic_id, v.rank"
            ),
            {"courses": course_ids},
        )
        by_topic: dict[int, list[bool | None]] = {}
        for topic_id, _rank, share in rows.all():
            by_topic.setdefault(int(topic_id), []).append(None if share is None else share >= 0.5)
        return [VideoTopicRanking(t, r) for t, r in by_topic.items()]

    async def llm_stats(self, course_ids: list[int]) -> LlmStats:
        if not course_ids:
            return LlmStats()
        row = (
            await self._session.execute(
                _in(
                    "SELECT count(*), count(*) FILTER (WHERE l.json_valid IS FALSE "
                    "OR l.status = 'invalid_output'), count(*) FILTER (WHERE l.from_cache), "
                    "percentile_cont(0.95) WITHIN GROUP (ORDER BY l.latency_ms), "
                    "coalesce(sum(l.cost_usd), 0) FROM llm_call_logs l "
                    "JOIN ai_jobs j ON j.id = l.ai_job_id WHERE j.course_id IN :courses"
                ),
                {"courses": course_ids},
            )
        ).one()
        return LlmStats(
            calls=int(row[0]),
            invalid_outputs=int(row[1]),
            cache_hits=int(row[2]),
            latency_p95_ms=float(row[3]) if row[3] is not None else None,
            cost_usd=float(row[4]),
        )

    async def step_stats(self, path_ids: list[int]) -> StepStats:
        if not path_ids:
            return StepStats()
        row = (
            await self._session.execute(
                text(
                    "SELECT coalesce(sum(steps_passed), 0), "
                    "coalesce(sum(passed_first_attempt), 0), "
                    "avg(avg_attempts_used), coalesce(sum(attempts_exhausted), 0) "
                    "FROM v_path_step_metrics WHERE learning_path_id IN :paths"
                ).bindparams(bindparam("paths", expanding=True)),
                {"paths": path_ids},
            )
        ).one()
        return StepStats(
            steps_passed=int(row[0]),
            passed_first_attempt=int(row[1]),
            avg_attempts_used=float(row[2]) if row[2] is not None else None,
            attempts_exhausted=int(row[3]),
        )
