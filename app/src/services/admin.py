"""Pantallas de administración: usuarios y roles (AD1), log LLM (AD2) y métricas (AD3)."""

from dataclasses import dataclass

from clients.base import SmartMentorClient
from clients.models import EvaluationMetric, LlmLog, Role, User


@dataclass(frozen=True)
class MetricView:
    metric: EvaluationMetric
    meets_target: bool | None
    """None si la métrica solo se reporta (no tiene meta)."""


@dataclass(frozen=True)
class UserCounts:
    total: int
    teachers: int
    admins: int


class AdminService:
    def __init__(self, client: SmartMentorClient) -> None:
        self._client = client

    def me(self) -> User:
        return self._client.me()

    def users(self) -> list[User]:
        return sorted(self._client.list_users(), key=lambda u: (not u.active, u.full_name))

    @staticmethod
    def counts(users: list[User]) -> UserCounts:
        return UserCounts(
            total=len(users),
            teachers=sum("teacher" in u.roles for u in users),
            admins=sum("admin" in u.roles for u in users),
        )

    def create_user(self, full_name: str, email: str, role: Role) -> User:
        return self._client.create_user(full_name, email, role)

    def set_role(self, user_id: int, role: Role) -> User:
        return self._client.set_user_role(user_id, role)

    def set_active(self, user_id: int, active: bool) -> User:
        return self._client.set_user_active(user_id, active)

    def llm_log(self) -> LlmLog:
        return self._client.get_llm_log()

    def metrics(self) -> list[MetricView]:
        views = []
        for metric in self._client.list_evaluation_metrics():
            meets: bool | None = None
            if metric.target is not None and metric.comparison == "gte":
                meets = metric.value >= metric.target
            elif metric.target is not None and metric.comparison == "lte":
                meets = metric.value <= metric.target
            views.append(MetricView(metric=metric, meets_target=meets))
        return views
