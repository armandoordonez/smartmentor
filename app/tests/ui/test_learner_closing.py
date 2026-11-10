"""E10, E11, E11b, E12, E13a y E13b: badge, progreso, autorizaciones, logros y encuesta."""

from apptest import button, page_texts, session_of
from learner_support import (
    ACHIEVEMENTS,
    BADGE,
    PROGRESS,
    SURVEY,
    client_of,
    fail,
    learner_app,
    matches_figma,
    no_exception,
)

from streamlit.testing.v1 import AppTest

from clients.base import ApiError
from clients.models_learner import StudyGoals


def test_e10_follows_figma() -> None:
    at = learner_app("learner_completed", BADGE)
    matches_figma(at, "E10", accepted=("★",))


def test_e10_without_pending_survey_hides_the_survey_card() -> None:
    at = learner_app("learner_badge", BADGE)
    no_exception(at)
    assert "Responder encuesta" not in page_texts(at)


def test_e10_public_verification_and_share() -> None:
    at = learner_app("learner_badge", BADGE)
    assert not at.code
    button(at, "Compartir").click().run()
    assert at.code
    assert "Verificación pública" in [e.label for e in at.expander]


def test_e10_survey_card_opens_the_survey() -> None:
    at = learner_app("learner_completed", BADGE)
    button(at, "Responder encuesta").click().run()
    no_exception(at)
    assert session_of(at).learner.survey_step == 1


def test_e10_offline() -> None:
    at = learner_app("learner_offline", BADGE)
    no_exception(at)
    assert at.error


# --- E12 -----------------------------------------------------------------------------------------


def test_e12_lists_obtained_and_locked_badges() -> None:
    at = learner_app("learner_badge", ACHIEVEMENTS)
    no_exception(at)
    texts = page_texts(at)
    assert "Logros" in texts
    assert "Tus badges digitales: imagen PNG + archivo JSON Open Badges." in texts
    assert "Fundamentos de Machine Learning" in texts
    assert "Obtenido 5 oct 2026" in texts
    assert "Bloqueado · inscríbete para obtenerlo" in texts
    assert "Ver badge" in texts


def test_e12_view_badge_opens_that_enrollment() -> None:
    at = learner_app("learner_badge", ACHIEVEMENTS)
    button(at, "Ver badge").click().run()
    no_exception(at)
    assert session_of(at).selected_enrollment_id == 7
    assert "¡Ruta completada!" in page_texts(at)


def test_e12_error_is_friendly() -> None:
    at = learner_app("learner_badge", ACHIEVEMENTS, run=False)
    fail(at, "list_badges", ApiError(500, "INTERNAL_ERROR"))
    at.run()
    no_exception(at)
    assert at.error


# --- E11 · E11b ----------------------------------------------------------------------------------


def test_e11_follows_figma() -> None:
    at = learner_app("learner_path", PROGRESS)
    matches_figma(
        at,
        "E11",
        accepted=(
            # La API no dice si hay prueba de retención (E14, P2), los intentos por tema se
            # calculan con los datos de la ruta y la persona de ejemplo no participa del piloto.
            "1,5",
            "Prueba de retención disponible · opcional",
            "10 preguntas · unos 10 minutos. Nos ayuda a medir cuánto recuerdas semanas después "
            "de terminar la ruta.",
            "Empezar prueba",
            "Piloto: participas · ruta personalizada",
            "Datos: autorizado el 1 oct 2026",
        ),
    )


def test_e11_without_goals_the_section_is_hidden() -> None:
    at = learner_app("learner_path", PROGRESS, run=False)
    client_of(at).get_study_goals = lambda: None  # type: ignore[method-assign]
    at.run()
    no_exception(at)
    assert "Mis metas · opcional" not in page_texts(at)


def test_e11_changing_the_daily_goal_saves_it() -> None:
    at = learner_app("learner_path", PROGRESS)
    saved: list[StudyGoals] = []
    client = client_of(at)
    original = client.set_study_goals

    def spy(update: object) -> StudyGoals:
        goals = original(update)  # type: ignore[arg-type]
        saved.append(goals)
        return goals

    client.set_study_goals = spy  # type: ignore[method-assign]
    at.segmented_control(key="goal-daily").set_value(45).run()
    no_exception(at)
    assert saved[0].daily_minutes_goal == 45


def test_e11_continue_follows_next_action() -> None:
    at = learner_app("learner_path", PROGRESS)
    button(at, "Continuar mi ruta").click().run()
    no_exception(at)
    assert session_of(at).learner.step_id == 813


def test_e11b_leave_the_pilot_revokes_only_the_pilot_consent() -> None:
    at = learner_app("learner_path", PROGRESS, run=False)
    client = client_of(at)
    client.grant_consent("pilot_research", "1.0")
    at.run()
    me = client.get_me()
    session_of(at).me = me
    at.run()
    revoked = []
    original = client.revoke_consent

    def spy(kind: str) -> object:
        revoked.append(kind)
        return original(kind)  # type: ignore[arg-type]

    client.revoke_consent = spy  # type: ignore[method-assign]
    button(at, "Gestionar mis autorizaciones").click().run()
    texts = page_texts(at)
    assert "Elige qué quieres cambiar. Puedes volver a autorizar más adelante." in texts
    assert button(at, "Confirmar").disabled
    at.radio(key="consents-choice").set_value("Salir del piloto").run()
    button(at, "Confirmar").click().run()
    no_exception(at)
    assert revoked == ["pilot_research"]


def test_e11b_revoking_everything_requests_deletion_and_asks_for_consent_again() -> None:
    at = learner_app("learner_path", PROGRESS)
    requests = []
    client = client_of(at)
    client.create_data_subject_request = lambda kind, comment: requests.append(kind)  # type: ignore[method-assign,assignment,return-value]
    button(at, "Gestionar mis autorizaciones").click().run()
    at.radio(key="consents-choice").set_value("Revocar la autorización y borrar mis datos").run()
    button(at, "Confirmar").click().run()
    no_exception(at)
    assert requests == ["deletion"]
    assert session_of(at).me is not None
    assert session_of(at).me.requires_consent  # type: ignore[union-attr]


def test_e11b_cancel_closes_the_panel() -> None:
    at = learner_app("learner_path", PROGRESS)
    button(at, "Gestionar mis autorizaciones").click().run()
    button(at, "Cancelar").click().run()
    assert "Elige qué quieres cambiar. Puedes volver a autorizar más adelante." not in page_texts(
        at
    )


def test_e11_offline() -> None:
    at = learner_app("learner_offline", PROGRESS)
    no_exception(at)
    assert at.error


# --- E13a · E13b ---------------------------------------------------------------------------------


def _fill(at: AppTest, count: int, start: int = 0) -> None:
    for index in range(start, start + count):
        at.radio[index].set_value(5).run()



def test_e13a_follows_figma() -> None:
    at = learner_app("learner_completed", SURVEY)
    matches_figma(at, "E13a", accepted=("Fundamentos de ML · Encuesta final",))


def test_e13a_next_needs_every_answer() -> None:
    at = learner_app("learner_completed", SURVEY)
    assert button(at, "Siguiente").disabled
    _fill(at, 8)
    assert not button(at, "Siguiente").disabled


def test_e13b_follows_figma_and_sends_the_survey() -> None:
    at = learner_app("learner_completed", SURVEY)
    _fill(at, 8)
    button(at, "Siguiente").click().run()
    matches_figma(at, "E13b", accepted=("Fundamentos de ML · Encuesta final",))
    sent = []
    client_of(at).submit_final_survey = lambda *a, **kw: sent.append(kw) or 85.0  # type: ignore[method-assign]
    _fill(at, 5)
    at.text_area(key="survey-comment").set_value("Más ejemplos.").run()
    button(at, "Enviar encuesta").click().run()
    no_exception(at)
    assert len(sent[0]["sus_items"]) == 10
    assert sent[0]["likert"] == {"q1": 5, "q2": 5, "q3": 5}
    assert sent[0]["comment"] == "Más ejemplos."


def test_e13b_back_keeps_step_one_answers() -> None:
    at = learner_app("learner_completed", SURVEY)
    _fill(at, 8)
    button(at, "Siguiente").click().run()
    button(at, "Anterior").click().run()
    assert not button(at, "Siguiente").disabled


def test_e13_already_answered_is_a_friendly_error() -> None:
    at = learner_app("learner_completed", SURVEY)
    _fill(at, 8)
    button(at, "Siguiente").click().run()
    _fill(at, 5)
    fail(at, "submit_final_survey", ApiError(409, "SURVEY_ALREADY_SUBMITTED"))
    button(at, "Enviar encuesta").click().run()
    assert at.error[0].value == "Ya respondiste la encuesta."


def test_e13_skip_returns_to_the_badge() -> None:
    at = learner_app("learner_completed", SURVEY)
    button(at, "Ahora no").click().run()
    no_exception(at)
    assert "¡Ruta completada!" in page_texts(at)
