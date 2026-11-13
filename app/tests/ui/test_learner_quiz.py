"""E6, E6b, E6c, U1b, U1c, E7, E7b y E7c: tema, quiz y resultado."""

from apptest import button, page_texts, session_of
from learner_support import (
    QUIZ,
    QUIZ_RESULT,
    TOPIC,
    client_of,
    fail,
    learner_app,
    matches_figma,
    no_exception,
)
from streamlit.testing.v1 import AppTest

from clients.base import ApiError
from clients.ops_learner import LearnerScript

GRADE_SCRIPT = LearnerScript({"submit_attempt": "learner/job_accepted_grading"})
RETRY_SCRIPT = LearnerScript({"create_attempt": "learner/job_accepted_retry"})


def _answer_all(at: AppTest, count: int) -> None:
    """Responde `count` preguntas del quiz: opción 0 y, en la corta, un texto."""
    for _ in range(count):
        if at.radio:
            at.radio[0].set_value(at.radio[0].options[0]).run()
            label = "Siguiente"
        else:
            at.text_area[0].set_value("Porque no detectar un fraude cuesta más.").run()
            label = "Enviar quiz"
        button(at, label).click().run()


def _open_topic(scenario: str = "learner_path", script: LearnerScript | None = None) -> AppTest:
    at = learner_app(scenario, TOPIC, script=script)
    session_of(at).learner.step_id = 813
    at.run()
    return at


def test_e6_follows_figma() -> None:
    at = _open_topic()
    matches_figma(
        at,
        "E6",
        accepted=(
            # El curso se nombra completo; el índice de calidad no se muestra antes de calificar
            # (C-08); la API no dice cuántas preguntas son de cada tipo; el texto de ayuda del
            # comentario es un `placeholder` que `AppTest` no lee.
            "Fundamentos de ML › Tema 3 de 5",
            "▶ Video recomendado · 11 min · calidad 81 de 100",
            "Cuéntale a tu instructor qué mejorarías de este video…",
            "5 preguntas: 4 de opción múltiple y 1 de respuesta corta.",
        ),
    )


def test_e6_shows_remaining_attempts() -> None:
    at = _open_topic()
    assert "Apruebas con 70 %. Este es tu intento 2 de 3." in page_texts(at)


def test_e6_video_rating_is_sent_without_name() -> None:
    at = _open_topic()
    sent = []
    client_of(at).send_video_feedback = lambda **kwargs: sent.append(kwargs)  # type: ignore[method-assign]
    at.button_group[0].set_value("useful").run()
    button(at, "Enviar calificación").click().run()
    no_exception(at)
    assert sent[0]["rating"] == "useful"
    assert any("¡Gracias!" in s.value for s in at.success)


def test_e6_start_quiz_opens_the_attempt() -> None:
    at = _open_topic()
    button(at, "Empezar quiz").click().run()
    no_exception(at)
    assert session_of(at).learner.attempt_id == 9002
    assert "Quiz: Regresión logística" in page_texts(at)


def test_e6_start_quiz_can_need_new_questions_u1b() -> None:
    at = _open_topic(script=RETRY_SCRIPT)
    button(at, "Empezar quiz").click().run()
    no_exception(at)
    assert session_of(at).learner.quiz_job_kind == "prepare"
    assert any(
        t.startswith("Preparando preguntas nuevas para tu intento 2") for t in page_texts(at)
    )


def test_e6_exhausted_attempts_block_the_quiz() -> None:
    at = _open_topic("learner_exhausted")
    texts = page_texts(at)
    assert "Empezar quiz" not in texts
    assert any("Usaste todos los intentos" in w.value for w in at.warning)


def test_e6_api_error_is_friendly() -> None:
    at = learner_app("learner_path", TOPIC, run=False)
    session_of(at).learner.step_id = 813
    fail(at, "get_step_content", ApiError(409, "STEP_NOT_AVAILABLE"))
    at.run()
    no_exception(at)
    assert at.error[0].value == "Este tema todavía no está disponible."


def _with_next_action(at: AppTest, **fields: object) -> None:
    """Cambia el `next_action` de la inscripción del escenario (lo que diría la API)."""
    enrollment = client_of(at)._enrollments[0]
    enrollment.next_action = enrollment.next_action.model_copy(update=fields)


def test_e6_open_attempt_is_continued_not_restarted_b024() -> None:
    at = learner_app("learner_path", TOPIC, run=False)
    session_of(at).learner.step_id = 813
    _with_next_action(at, type="continue_attempt", screen="E6b", step_id=813, attempt_id=9002)
    at.run()
    texts = page_texts(at)
    assert "Empezar quiz" not in texts
    button(at, "Continuar quiz").click().run()
    no_exception(at)
    assert session_of(at).learner.attempt_id == 9002
    assert "Quiz: Regresión logística" in page_texts(at)


def test_e6_start_quiz_with_an_unknown_open_attempt_follows_the_api_b024() -> None:
    at = _open_topic()

    def in_progress(*_: object, **__: object) -> None:
        _with_next_action(at, type="continue_attempt", screen="E6b", step_id=813, attempt_id=9002)
        raise ApiError(409, "ATTEMPT_IN_PROGRESS")

    client_of(at).create_attempt = in_progress  # type: ignore[method-assign]
    button(at, "Empezar quiz").click().run()
    no_exception(at)
    assert not at.error
    assert "Quiz: Regresión logística" in page_texts(at)


def test_e6_passed_or_skipped_topic_can_be_reviewed_without_a_quiz_b025() -> None:
    for step_id, note in ((812, "Ya aprobaste este tema."), (811, "Este tema se omitió")):
        at = learner_app("learner_path", TOPIC, run=False)
        session_of(at).learner.step_id = step_id
        at.run()
        no_exception(at)
        # Con datos como los de la API real llega como aviso; si hay contenido, bajo el tema.
        texts = page_texts(at) + [i.value for i in at.info]
        assert "Empezar quiz" not in texts
        assert any(t.startswith(note) for t in texts)
        button(at, "Volver a mi ruta").click().run()
        assert "Ver otras rutas" in page_texts(at)


def test_e6_closed_topic_explains_why_when_the_api_hides_its_content_b025() -> None:
    """Con la API real un tema aprobado responde 409 STEP_NOT_AVAILABLE (p. ej. desde E9)."""
    at = learner_app("learner_path", TOPIC, run=False)
    session_of(at).learner.step_id = 812
    fail(at, "get_step_content", ApiError(409, "STEP_NOT_AVAILABLE"))
    at.run()
    no_exception(at)
    assert not at.error
    assert at.info[0].value == "Ya aprobaste este tema."
    assert "Regresión lineal" in page_texts(at)
    button(at, "Volver a mi ruta").click().run()
    assert "Ver otras rutas" in page_texts(at)


# --- E6b · E6c -----------------------------------------------------------------------------------


def _open_quiz(scenario: str = "learner_path", script: LearnerScript | None = None) -> AppTest:
    at = learner_app(scenario, QUIZ, script=script, run=False)
    state = session_of(at).learner
    state.step_id, state.attempt_id = 813, 9002
    at.run()
    return at


def test_e6b_first_question_follows_figma() -> None:
    at = _open_quiz()
    matches_figma(
        at,
        "E6b",
        accepted=(
            "Fundamentos de ML › Tema 3 de 5 · Pregunta 1 de 5",
            "(Demo del prototipo) Ver resultado menor a 70 %",
        ),
    )


def test_e6c_short_answer_shows_the_rubric_and_limit() -> None:
    at = _open_quiz()
    _answer_all(at, 4)
    no_exception(at)
    texts = page_texts(at)
    assert "Respuesta corta" in texts
    assert "0 / 500 caracteres" in texts
    assert "CÓMO SE CALIFICA" in texts
    assert "Responde sin ayuda de IA." in texts
    assert button(at, "Enviar quiz").disabled


def test_e6c_submit_with_only_multiple_choice_goes_to_result() -> None:
    at = _open_quiz()
    _answer_all(at, 5)
    no_exception(at)
    assert "¡Tema aprobado!" in page_texts(at)


def test_e6c_submit_with_short_answer_waits_for_grading_u1c() -> None:
    at = _open_quiz(script=GRADE_SCRIPT)
    _answer_all(at, 5)
    no_exception(at)
    assert "Calificando tu respuesta corta" in page_texts(at)
    at.run()  # segunda consulta: terminó
    no_exception(at)
    assert "¡Tema aprobado!" in page_texts(at)


def test_u1c_follows_figma() -> None:
    at = _open_quiz(script=GRADE_SCRIPT)
    _answer_all(at, 5)
    matches_figma(at, "U1c", accepted=("Prototipo: esta pantalla avanza sola a los 2 segundos.",))


def test_u1c_error_keeps_the_answers_and_offers_retry() -> None:
    script = LearnerScript(
        {"submit_attempt": "learner/job_accepted_grading", "job_outcome": "failed"}
    )
    at = _open_quiz(script=script)
    _answer_all(at, 5)
    at.run()
    no_exception(at)
    assert any("Tus respuestas están guardadas" in e.value for e in at.error)
    assert "Reintentar" in [b.label for b in at.button]


def test_u1b_error_offers_retry_and_back_to_the_path() -> None:
    """T-020 (F-001): si falla la generación de preguntas nuevas, no se inventa un quiz."""
    script = LearnerScript({"job_outcome": "failed"})
    at = learner_app("learner_path", QUIZ, script=script, run=False)
    learner = session_of(at).learner
    learner.step_id, learner.quiz_job_id, learner.quiz_job_kind = 813, "job-retry", "prepare"
    at.run()
    at.run()
    no_exception(at)
    assert any("No pudimos preparar las preguntas nuevas" in e.value for e in at.error)
    labels = [b.label for b in at.button]
    assert "Reintentar" in labels
    assert "Volver a mi ruta" in labels


def test_u1b_follows_figma_and_continues_to_the_new_quiz() -> None:
    at = _open_topic(script=RETRY_SCRIPT)
    button(at, "Empezar quiz").click().run()
    matches_figma(
        at,
        "U1b",
        accepted=("Prototipo: esta pantalla avanza sola a los 2 segundos.",),
    )
    at.switch_page(QUIZ).run()  # segunda consulta: las preguntas están listas
    no_exception(at)
    assert "Quiz: Regresión logística" in page_texts(at)


# --- E7 · E7b · E7c ------------------------------------------------------------------------------


def _result(scenario: str) -> AppTest:
    at = learner_app(scenario, QUIZ_RESULT, run=False)
    session_of(at).learner.step_id = 813
    at.run()
    return at


def test_e7_passed_shows_the_review_and_the_rubric() -> None:
    at = _result("learner_path")
    session_of(at).learner.attempt_id = 9002
    at.run()
    no_exception(at)
    texts = page_texts(at)
    assert "¡Tema aprobado!" in texts
    assert any(t.startswith("Obtuviste 80 % (4 de 5) en el intento 2 de 3") for t in texts)
    assert "Revisión de respuestas" in texts
    assert any(t.startswith("Puntaje: 2 de 3 criterios") for t in texts)
    assert "Pedir revisión del instructor" in texts
    assert "Siguiente tema" in texts


def test_e7_review_request_is_sent() -> None:
    at = _result("learner_path")
    session_of(at).learner.attempt_id = 9002
    at.run()
    sent = []
    client_of(at).request_answer_review = lambda i, _c: sent.append(i) or 1  # type: ignore[method-assign]
    button(at, "Pedir revisión del instructor").click().run()
    no_exception(at)
    assert sent == [1005]


def test_e7_review_already_requested_is_a_friendly_error() -> None:
    at = _result("learner_path")
    session_of(at).learner.attempt_id = 9002
    at.run()
    fail(at, "request_answer_review", ApiError(409, "REVIEW_ALREADY_REQUESTED"))
    button(at, "Pedir revisión del instructor").click().run()
    assert at.error[0].value == "Ya pediste la revisión de esta respuesta."


def test_e7b_follows_figma() -> None:
    at = _result("learner_quiz_failed")
    matches_figma(
        at,
        "E7b",
        accepted=(
            "Fundamentos de ML › Tema 3 de 5 · Regresión logística",
            "Pregunta 5 · Explica por qué la regresión lineal no sirve para clasificar "
            "(respuesta corta)",
            "• Más peso en lo que fallaste: cómo mover el umbral de decisión y qué métrica "
            "elegir según el costo del error.",
            "Demo: ver el estado con los 3 intentos agotados",
        ),
    )


def test_e7b_retry_with_new_questions_opens_the_quiz() -> None:
    at = _result("learner_quiz_failed")
    button(at, "Reintentar con preguntas nuevas").click().run()
    no_exception(at)
    assert session_of(at).learner.attempt_id == 9002
    assert "Quiz: Regresión logística" in page_texts(at)


def test_e7b_retry_can_wait_for_new_questions() -> None:
    at = _result("learner_quiz_failed")
    client_of(at)._script = LearnerScript(
        {**client_of(at)._script.docs, "create_attempt": "learner/job_accepted_retry"}
    )
    button(at, "Reintentar con preguntas nuevas").click().run()
    no_exception(at)
    assert any(t.startswith("Preparando preguntas nuevas") for t in page_texts(at))


def test_e7c_exhausted_attempts_from_next_action() -> None:
    at = _result("learner_exhausted")
    no_exception(at)
    texts = page_texts(at)
    assert "Usaste los 3 intentos de este tema" in texts
    assert "Intentos agotados" in texts
    assert "Intento 3" in texts
    assert "40 % · 2 de 5" in texts
    assert "Necesitas 70 % para aprobar." in texts
    assert "Recursos de repaso" in texts


def test_e7c_exhausted_from_the_result() -> None:
    at = _result("learner_exhausted")
    session_of(at).learner.attempt_id = 9003
    at.run()
    assert "Usaste los 3 intentos de este tema" in page_texts(at)


def test_e7_offline() -> None:
    at = _result("learner_offline")
    no_exception(at)
    assert at.error


def test_e6b_submitted_attempt_is_not_answered_again_b026() -> None:
    at = learner_app("learner_path", QUIZ, run=False)
    state = session_of(at).learner
    state.step_id, state.attempt_id = 813, 9002
    client = client_of(at)
    original = client.get_attempt
    client.get_attempt = lambda attempt_id: original(attempt_id).model_copy(  # type: ignore[method-assign]
        update={"status": "graded"}
    )
    at.run()
    no_exception(at)
    texts = page_texts(at)
    assert "Enviar quiz" not in texts
    assert "Siguiente" not in texts
