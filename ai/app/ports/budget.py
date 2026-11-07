"""``BudgetGuard`` port (plan 5.4.11 and 18.5).

Checked before every paid call. Caps (USD): daily, monthly, per course and per enrollment, from
``AI_*_BUDGET_USD``. A cap that is not configured does not limit (the real provider cannot run
without them: ``/ready`` fails).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal, Protocol

BudgetScopeName = Literal["daily", "monthly", "course", "enrollment"]


@dataclass(frozen=True)
class BudgetScope:
    course_id: int | None = None
    enrollment_id: int | None = None


@dataclass(frozen=True)
class BudgetBreach:
    scope: BudgetScopeName
    limit_usd: Decimal
    spent_usd: Decimal

    def describe(self) -> str:
        return f"{self.scope} budget exhausted: spent {self.spent_usd} of {self.limit_usd} USD"


class BudgetGuard(Protocol):
    async def check(self, scope: BudgetScope, now: datetime) -> BudgetBreach | None:
        """``None`` when the call may go ahead; otherwise the first exhausted cap."""
        ...
