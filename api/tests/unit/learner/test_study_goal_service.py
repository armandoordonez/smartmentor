"""Metas de estudio (E11, P2): sin metas elegidas la respuesta es vacía y no un `404` (B-061)."""

from app.domains.identity.authentication import CurrentUser
from app.domains.learner.entities import StudyGoals
from app.domains.learner.service import StudyGoalService
from tests.unit.fakes import FakeUnitOfWork

USER = CurrentUser(
    id=7,
    full_name="Ana Aprendiz",
    email="ana@example.com",
    roles=frozenset({"learner"}),
    identity_provider=None,
    identity_subject=None,
)


class FakeStudyGoalRepository:
    """Una fila por aprendiz; el avance es fijo para comprobar que no se pierde con metas."""

    def __init__(self) -> None:
        self.rows: dict[int, tuple[int, int]] = {}

    async def get(self, user_id: int) -> tuple[int, int] | None:
        return self.rows.get(user_id)

    async def save(self, user_id: int, daily_minutes: int, monthly_topics: int) -> None:
        self.rows[user_id] = (daily_minutes, monthly_topics)

    async def progress(self, user_id: int, goals: tuple[int, int]) -> StudyGoals:
        return StudyGoals(
            daily_minutes_goal=goals[0],
            monthly_topics_goal=goals[1],
            daily_minutes_done=10,
            monthly_topics_done=2,
            streak_days=3,
        )


def make_service() -> tuple[StudyGoalService, FakeStudyGoalRepository, FakeUnitOfWork]:
    repository = FakeStudyGoalRepository()
    uow = FakeUnitOfWork()
    return StudyGoalService(repository, uow), repository, uow


async def test_without_goals_returns_the_empty_response_not_404() -> None:
    service, _, uow = make_service()
    goals = await service.get(USER)
    assert goals == StudyGoals(
        daily_minutes_goal=0,
        monthly_topics_goal=0,
        daily_minutes_done=0,
        monthly_topics_done=0,
        streak_days=0,
    )
    assert goals == StudyGoals.empty()
    assert uow.commits == 0  # leer no escribe


def test_the_empty_response_is_not_a_valid_goal() -> None:
    # El `PUT` exige al menos 1: un 0 nunca puede ser una meta elegida.
    assert StudyGoals.empty().daily_minutes_goal < 1
    assert StudyGoals.empty().monthly_topics_goal < 1


async def test_with_goals_returns_them_with_their_progress() -> None:
    service, repository, _ = make_service()
    repository.rows[USER.id] = (30, 3)
    goals = await service.get(USER)
    assert (goals.daily_minutes_goal, goals.monthly_topics_goal) == (30, 3)
    assert (goals.daily_minutes_done, goals.monthly_topics_done, goals.streak_days) == (10, 2, 3)


async def test_save_then_get_returns_the_chosen_goals() -> None:
    service, _, uow = make_service()
    saved = await service.save(USER, 45, 4)
    assert (saved.daily_minutes_goal, saved.monthly_topics_goal) == (45, 4)
    assert uow.commits == 1
    assert await service.get(USER) == saved


async def test_goals_are_per_learner() -> None:
    service, repository, _ = make_service()
    repository.rows[99] = (30, 3)
    assert await service.get(USER) == StudyGoals.empty()
