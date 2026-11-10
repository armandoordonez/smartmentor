"""Ayudas de las pruebas de las páginas del aprendiz (F07b)."""

from typing import Any

from apptest import new_app, page_texts, session_of
from figma_compare import figma_texts, missing_in_order
from streamlit.testing.v1 import AppTest

from clients.base import ApiError
from clients.fixtures import SCENARIOS_BY_KEY, FixturesClient
from clients.ops_learner import LearnerScript
from core.session import AppSession

DIAGNOSTIC = "pages/learner/diagnostic.py"
DIAGNOSTIC_RESULT = "pages/learner/diagnostic_result.py"
PATH = "pages/learner/path.py"
TOPIC = "pages/learner/topic.py"
QUIZ = "pages/learner/quiz.py"
QUIZ_RESULT = "pages/learner/quiz_result.py"
FINAL = "pages/learner/final_assessment.py"
FINAL_RESULT = "pages/learner/final_result.py"
BADGE = "pages/learner/badge.py"
PROGRESS = "pages/learner/progress.py"
ACHIEVEMENTS = "pages/learner/achievements.py"
SURVEY = "pages/learner/final_survey.py"
RETENTION = "pages/learner/retention_test.py"


def learner_app(
    scenario: str, page: str, *, script: LearnerScript | None = None, run: bool = True
) -> AppTest:
    """App con la sesión de un escenario del aprendiz, ya abierta en `page`."""
    at = new_app()
    client = FixturesClient(scenario, script=script)
    at.session_state["app_session"] = AppSession(
        me=client.get_me(),
        active_role=SCENARIOS_BY_KEY[scenario].role,
        scenario_key=scenario,
        fixtures_client=client,
    )
    at.run()
    at.switch_page(page)
    if run:
        at.run()
    return at


def client_of(at: AppTest) -> FixturesClient:
    client = session_of(at).fixtures_client
    assert client is not None
    return client


def fail(at: AppTest, operation: str, error: ApiError) -> None:
    """Hace que una operación del cliente de fixtures lance `error`."""

    def boom(*_: Any, **__: Any) -> Any:
        raise error

    setattr(client_of(at), operation, boom)


def no_exception(at: AppTest) -> None:
    assert [e.value for e in at.exception] == []


def matches_figma(at: AppTest, screen: str, accepted: tuple[str, ...] = ()) -> None:
    """Los textos del frame aparecen en orden; solo faltan las diferencias aceptadas."""
    no_exception(at)
    missing = missing_in_order(figma_texts(screen), page_texts(at))
    assert missing == list(accepted), f"{screen}: faltan o desordenados {missing}"
