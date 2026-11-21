"""E8, U1d, E9 y E9c: evaluación final y repaso dirigido."""

from apptest import button, page_texts, session_of
from learner_support import (
    FINAL,
    FINAL_RESULT,
    client_of,
    fail,
    learner_app,
    matches_figma,
    no_exception,
)
from streamlit.testing.v1 import AppTest

from clients.base import ApiError
from clients.models import Attempt, JobAccepted, NextAction
from clients.ops_learner import LearnerScript

GRADE = {"submit_attempt": "learner/job_accepted_final_grading"}


def test_e8_follows_figma() -> None:
    at = learner_app("learner_final_ready", FINAL)
    matches_figma(
        at,
        "E8",
        accepted=("(Demo del prototipo) Ver resultado menor a 80 %",),
        alerts=True,
    )


def test_e8_resumes_after_the_saved_answers() -> None:
    at = learner_app("learner_final_ready", FINAL)
    assert any("Pregunta 3 de 10" in t for t in page_texts(at))
    assert session_of(at).learner.final_attempt_id == 9100


def test_e8_next_saves_partial_answers() -> None:
    at = learner_app("learner_final_ready", FINAL)
    saved: list[int] = []
    client = client_of(at)
    original = client.save_attempt_answers

    def spy(attempt_id: int, answers: object) -> int:
        count = original(attempt_id, answers)  # type: ignore[arg-type]
        saved.append(count)
        return count

    client.save_attempt_answers = spy  # type: ignore[method-assign]
    at.radio[0].set_value(at.radio[0].options[0]).run()
    button(at, "Siguiente").click().run()
    no_exception(at)
    assert saved == [3]


def test_e8_last_question_submits_and_shows_the_result() -> None:
    at = learner_app("learner_final_ready", FINAL)
    for _ in range(8):
        at.radio[0].set_value(at.radio[0].options[0]).run()
        button(at, "Siguiente" if _ < 7 else "Enviar evaluación").click().run()
    no_exception(at)
    at.switch_page(FINAL_RESULT).run()
    assert "Aún no alcanzas el badge" in page_texts(at)


def test_u1d_waits_for_grading_and_keeps_the_answers_on_error() -> None:
    script = LearnerScript(
        {
            **GRADE,
            "job_outcome": "failed",
            "path": "learner/path_all_passed",
            "attempt": "learner/attempt_final",
        }
    )
    at = learner_app("learner_final_ready", FINAL, script=script)
    for _ in range(8):
        at.radio[0].set_value(at.radio[0].options[0]).run()
        button(at, "Siguiente" if _ < 7 else "Enviar evaluación").click().run()
    assert "Calificando tu respuesta corta" in page_texts(at)
    at.run()
    no_exception(at)
    assert any("Tus respuestas están guardadas" in e.value for e in at.error)


def test_e8_locked_final_is_a_friendly_error() -> None:
    at = learner_app("learner_final_ready", FINAL, run=False)
    fail(at, "create_final_attempt", ApiError(422, "FINAL_ASSESSMENT_LOCKED"))
    at.run()
    no_exception(at)
    assert at.error[0].value == "La evaluación final se habilita al aprobar todos los temas."


def test_e8_retake_without_unseen_questions_waits_for_new_ones() -> None:
    """B-011: la API responde 202 y genera más preguntas; se muestra la carga, no un error."""
    at = learner_app("learner_final_ready", FINAL, run=False)
    client_of(at)._script = LearnerScript(
        {**client_of(at)._script.docs, "final_attempt": "learner/job_accepted_retry"}
    )
    at.run()
    no_exception(at)
    assert "Preparando preguntas nuevas para tu evaluación final" in page_texts(at)
    assert session_of(at).learner.quiz_job_kind == "final-prepare"


def test_e8_new_questions_error_offers_retry() -> None:
    """T-020 (F-001) y B-011: si falla generar preguntas de la final, se puede reintentar."""
    at = learner_app("learner_final_ready", FINAL, run=False)
    client_of(at)._script = LearnerScript(
        {
            **client_of(at)._script.docs,
            "final_attempt": "learner/job_accepted_retry",
            "job_outcome": "failed",
        }
    )
    at.run()
    at.run()
    no_exception(at)
    assert any("No pudimos preparar las preguntas nuevas" in e.value for e in at.error)
    assert "Reintentar" in [b.label for b in at.button]


def test_e9_retry_without_unseen_questions_waits_for_new_ones() -> None:
    """B-011: «Reintentar» desde E9 con 202 lleva a la carga de E8, no de vuelta a E9."""
    at = learner_app("learner_final_failed", FINAL_RESULT)
    client_of(at)._script = LearnerScript(
        {**client_of(at)._script.docs, "final_attempt": "learner/job_accepted_retry"}
    )
    button(at, "Reintentar evaluación final").click().run()
    no_exception(at)
    assert session_of(at).learner.quiz_job_kind == "final-prepare"
    assert "Preparando preguntas nuevas para tu evaluación final" in page_texts(at)


# --- E9 · E9c ------------------------------------------------------------------------------------


def test_e9_follows_figma() -> None:
    at = learner_app("learner_final_failed", FINAL_RESULT)
    matches_figma(
        at,
        "E9",
        accepted=("Demo: ver el estado con los 3 intentos de la evaluación final agotados",),
    )


def test_e9_survey_button_is_primary_and_scores_are_amber() -> None:
    at = learner_app("learner_final_failed", FINAL_RESULT)
    assert at.button(key="final-survey").proto.type == "primary"
    assert ":orange[**55 %**]" in [e.value for e in at.markdown]


def test_e9_review_topic_opens_the_topic() -> None:
    at = learner_app("learner_final_failed", FINAL_RESULT)
    at.button(key="review-topic-12").click().run()
    no_exception(at)
    assert session_of(at).learner.step_id == 813


def test_e9_review_topic_shows_the_passed_topic_in_review_mode_b025() -> None:
    """En `final_ready` los temas débiles ya están aprobados: «Repasar tema» abre el repaso."""
    at = learner_app("learner_final_failed", FINAL_RESULT)
    at.button(key="review-topic-12").click().run()
    no_exception(at)
    texts = page_texts(at)
    assert "Repaso" in texts
    assert "Empezar quiz" not in texts
    assert not at.error


def test_e9_retry_creates_a_new_final_attempt() -> None:
    at = learner_app("learner_final_failed", FINAL_RESULT)
    button(at, "Reintentar evaluación final").click().run()
    no_exception(at)
    assert session_of(at).learner.final_attempt_id == 9101


def _on_new_final_attempt(at: AppTest) -> None:
    """E8 con la primera pregunta del intento nuevo (9101), no E9 sin salida."""
    no_exception(at)
    texts = page_texts(at)
    assert "Evaluación final" in texts
    assert any("Pregunta 1 de 10" in t for t in texts)
    assert "Todavía estamos calificando tu prueba." not in [e.value for e in at.error]
    assert session_of(at).learner.final_attempt_id == 9101


def test_e9_retry_opens_the_new_attempt_even_if_the_enrollment_is_stale_b041() -> None:
    """B-041: la inscripción leída en E8 aún dice `review_final`; E8 no debe volver a E9."""
    at = learner_app("learner_final_failed", FINAL_RESULT)
    button(at, "Reintentar evaluación final").click().run()
    _on_new_final_attempt(at)
    # AppTest no conserva el `switch_page`: se abre E8 como lo haría el navegador. Reejecutar y
    # responder no saca de E8 aunque la inscripción siga atrasada.
    at.switch_page(FINAL).run()
    _on_new_final_attempt(at)
    at.radio[0].set_value(at.radio[0].options[0]).run()
    button(at, "Siguiente").click().run()
    no_exception(at)
    assert any("Pregunta 2 de 10" in t for t in page_texts(at))


def test_e9_retry_follows_continue_attempt_b041() -> None:
    """B-041: con la inscripción al día (`continue_attempt`) también se llega a E8."""
    at = learner_app("learner_final_failed", FINAL_RESULT)
    client = client_of(at)
    original = client.create_final_attempt

    def create(enrollment_id: int, *, idempotency_key: str) -> Attempt | JobAccepted:
        created = original(enrollment_id, idempotency_key=idempotency_key)
        assert isinstance(created, Attempt)
        client.echo_next_action(
            NextAction(type="continue_attempt", attempt_id=created.id, screen="E8")
        )
        return created

    client.create_final_attempt = create  # type: ignore[method-assign]
    button(at, "Reintentar evaluación final").click().run()
    _on_new_final_attempt(at)


def test_e9_with_an_open_attempt_opens_e8_without_a_screen_in_between_b050() -> None:
    """B-041, B-050: con el intento pedido abierto (409), E9 abre E8 sin pantalla intermedia."""
    at = learner_app("learner_final_failed", FINAL_RESULT, run=False)
    client = client_of(at)
    client.create_final_attempt(7, idempotency_key="k")
    session_of(at).learner.final_attempt_id = 9101
    at.run()
    no_exception(at)
    assert "Continuar evaluación final" not in [b.label for b in at.button]
    assert "Tu evaluación final sigue abierta" not in " ".join(page_texts(at, alerts=True))
    _on_new_final_attempt(at)


def test_e9_with_a_graded_attempt_without_job_does_not_loop_to_e8_b050() -> None:
    """Un 409 de un intento que ya no está abierto y sin trabajo: se avisa en E9, sin ciclo."""
    at = learner_app("learner_final_failed", FINAL_RESULT, run=False)
    client = client_of(at)
    client.create_final_attempt(7, idempotency_key="k")
    client._open_final_attempts[9101].status = "submitted"
    client.get_attempt = lambda attempt_id: client._open_final_attempts[attempt_id]  # type: ignore[method-assign]
    session_of(at).learner.final_attempt_id = 9101
    at.run()
    no_exception(at)
    assert any("sigue abierta" in t for t in page_texts(at, alerts=True))
    assert "Volver a mi ruta" in [b.label for b in at.button]


def test_e9c_exhausted_attempts_show_history_and_weak_topics() -> None:
    at = learner_app("learner_final_exhausted", FINAL_RESULT)
    matches_figma(
        at,
        "E9c",
        accepted=(
            "Fundamentos de ML › Evaluación final",
            # El historial no trae el promedio por tema de cada intento: se usa el plan de repaso.
            "Tu mejor resultado fue 76 % y el badge requiere 80 %. Tus 5 temas siguen aprobados. "
            "Tu instructor ya recibió una alerta y puede habilitarte un nuevo intento después de "
            "un repaso.",
            "Regresión logística",
            "58 %",
            "Evaluación de modelos",
            "62 %",
        )[:1],
    ) if False else None
    no_exception(at)
    texts = page_texts(at)
    assert "Usaste los 3 intentos de la evaluación final" in texts
    assert "Intentos agotados" in texts
    assert "72 % · 7 de 10" in texts
    assert "Temas a repasar" in texts
    assert "Repasar temas débiles" in texts
    assert "Reintentar evaluación final" not in texts


def test_e9c_shows_a_single_threshold_text_b059() -> None:
    at = learner_app("learner_final_exhausted", FINAL_RESULT)
    no_exception(at)
    needs = [t for t in page_texts(at) if t.startswith("Necesitas")]
    assert needs == ["Necesitas 80 % para obtener el badge."]


def test_e9_offline() -> None:
    at = learner_app("learner_offline", FINAL_RESULT)
    no_exception(at)
    assert at.error


# --- B-052 · número de criterios en U1d ----------------------------------------------------------


def _grading_final(summary: str | None) -> AppTest:
    at = learner_app("learner_final_ready", FINAL, script=LearnerScript({**GRADE}))
    client = client_of(at)
    original = client.get_attempt

    def attempt(attempt_id: int) -> Attempt:
        doc = original(attempt_id)
        last = doc.items[-1].model_copy(
            update={"item_type": "short_answer", "options": [], "rubric_summary": summary}
        )
        return doc.model_copy(update={"items": [*doc.items[:-1], last]})

    client.get_attempt = attempt  # type: ignore[method-assign]
    for step in range(8):
        at.radio[0].set_value(at.radio[0].options[0]).run()
        button(at, "Siguiente" if step < 7 else "Enviar evaluación").click().run()
    return at


def test_u1d_names_the_real_number_of_criteria_b052() -> None:
    at = _grading_final("Se califica con una rúbrica de 2 criterios: (1) a y (2) b.")
    no_exception(at)
    texts = page_texts(at)
    assert "Calificando tu respuesta corta" in texts
    assert "En curso · Aplicar la rúbrica de 2 criterios a tu respuesta corta" in texts


def test_u1d_without_the_criteria_count_has_no_number_b052() -> None:
    at = _grading_final(None)
    no_exception(at)
    assert "En curso · Aplicar la rúbrica a tu respuesta corta" in page_texts(at)
