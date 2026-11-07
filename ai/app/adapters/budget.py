"""``CallLogBudgetGuard``: budget caps computed from what ``llm_call_logs`` already spent.

Windows: the daily and monthly caps count from the start of the day and month in
``APP_TIMEZONE``; the course and enrollment caps count everything (``refs`` of the job).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from app.ports.budget import BudgetBreach, BudgetScope
from app.ports.call_logs import LlmCallLogRepository


@dataclass(frozen=True)
class BudgetLimits:
    daily_usd: Decimal | None = None
    monthly_usd: Decimal | None = None
    course_usd: Decimal | None = None
    enrollment_usd: Decimal | None = None


class CallLogBudgetGuard:
    def __init__(
        self, limits: BudgetLimits, call_logs: LlmCallLogRepository, timezone: str
    ) -> None:
        self._limits = limits
        self._logs = call_logs
        self._tz = ZoneInfo(timezone)

    async def check(self, scope: BudgetScope, now: datetime) -> BudgetBreach | None:
        local = now.astimezone(self._tz)
        day_start = local.replace(hour=0, minute=0, second=0, microsecond=0)
        month_start = day_start.replace(day=1)
        limits = self._limits
        if limits.daily_usd is not None:
            spent = await self._logs.spent_usd(since=day_start)
            if spent >= limits.daily_usd:
                return BudgetBreach("daily", limits.daily_usd, spent)
        if limits.monthly_usd is not None:
            spent = await self._logs.spent_usd(since=month_start)
            if spent >= limits.monthly_usd:
                return BudgetBreach("monthly", limits.monthly_usd, spent)
        if limits.course_usd is not None and scope.course_id is not None:
            spent = await self._logs.spent_usd(course_id=scope.course_id)
            if spent >= limits.course_usd:
                return BudgetBreach("course", limits.course_usd, spent)
        if limits.enrollment_usd is not None and scope.enrollment_id is not None:
            spent = await self._logs.spent_usd(enrollment_id=scope.enrollment_id)
            if spent >= limits.enrollment_usd:
                return BudgetBreach("enrollment", limits.enrollment_usd, spent)
        return None
