"""E6, E6b, E6c, U1b, U1c, E7, E7b y E7c: tema, quiz y resultado."""

import ast
import re

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
from support import SRC_DIR

from clients.base import ApiError
from clients.models import NextAction, PathDetail
from clients.ops_learner import LearnerScript

GRADE_SCRIPT = LearnerScript({"submit_attempt": "learner/job_accepted_grading"})
RETRY_SCRIPT = LearnerScript({"create_attempt": "learner/job_accepted_retry"})


# Figma promete «menos de 20 segundos», pero preparar preguntas tardó unos 90 s en el recorrido
# del 2026-11-15: la app dice «hasta 2 minutos» (B-060). La nota del prototipo no va en la app.
FIGMA_ESTIMATE = "Tiempo estimado: menos de 20 segundos"
FIGMA_PROTOTYPE_NOTE = "Prototipo: esta pantalla avanza sola a los 2 segundos."


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


def test_e6_open_attempt_continues_instead_of_creating_another() -> None:
    at = learner_app("learner_path", TOPIC, run=False)
    session_of(at).learner.step_id = 813
    client_of(at).echo_next_action(
        NextAction(type="continue_attempt", step_id=813, attempt_id=9002, screen="E6b")
    )
    at.run()
    assert "Empezar quiz" not in page_texts(at)
    button(at, "Continuar quiz").click().run()
    no_exception(at)
    assert session_of(at).learner.attempt_id == 9002
    assert "Quiz: Regresión logística" in page_texts(at)


def test_e6_exhausted_attempts_block_the_quiz() -> None:
    at = _open_topic("learner_exhausted")
    texts = page_texts(at)
    assert "Empezar quiz" not in texts
    assert any("Usaste todos los intentos" in w.value for w in at.warning)


def _topic_without(**fields: object) -> AppTest:
    """E6 con el contenido que diría la API si faltaran la explicación o el video."""
    at = learner_app("learner_path", TOPIC, run=False)
    session_of(at).learner.step_id = 813
    client = client_of(at)
    original = client.get_step_content
    client.get_step_content = lambda *a, **k: original(*a, **k).model_copy(update=fields)  # type: ignore[method-assign]
    at.run()
    no_exception(at)
    return at


def test_e6_without_explanation_says_so_b046() -> None:
    texts = page_texts(_topic_without(explanation=None))
    assert "Este tema todavía no tiene explicación en texto." in " ".join(texts)
    assert "Explicación" not in texts
    assert "Este tema todavía no tiene video." not in " ".join(texts)


def test_e6_without_video_says_so_b046() -> None:
    texts = page_texts(_topic_without(video=None))
    assert "Este tema todavía no tiene video." in " ".join(texts)
    assert "Explicación" in texts
    assert "Este tema todavía no tiene explicación en texto." not in " ".join(texts)


def test_e6_with_all_content_has_no_missing_notices_b046() -> None:
    joined = " ".join(page_texts(_open_topic()))
    assert "todavía no tiene" not in joined


def test_e6_video_and_rating_live_in_a_fragment_b046() -> None:
    """Cada clic en la valoración redibuja solo el fragmento (no pide 3 endpoints otra vez).

    `AppTest` siempre reejecuta todo el guion, así que no puede medir las lecturas de una
    reejecución parcial: se verifica que la página declare el fragmento y que lo use.
    """
    tree = ast.parse((SRC_DIR / "pages/learner/topic.py").read_text(encoding="utf-8"))
    fragments = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and any(ast.unparse(d) == "st.fragment" for d in node.decorator_list)
    ]
    assert [f.name for f in fragments] == ["_video_block"]
    used = {ast.unparse(n.func) for n in ast.walk(fragments[0]) if isinstance(n, ast.Call)}
    assert {"render_video", "render_video_feedback"} <= used
    # Dentro del fragmento no se lee la API salvo para enviar la valoración.
    reads = {c for c in used if c.startswith("client.")}
    assert reads == {"client.send_video_feedback"}


def test_e6_rating_replaces_the_card_with_the_thanks_without_rerun_b046() -> None:
    at = _open_topic()
    sent: list[object] = []
    client_of(at).send_video_feedback = lambda **kw: sent.append(kw)  # type: ignore[method-assign,assignment]
    at.button_group[0].set_value("useful").run()
    button(at, "Enviar calificación").click().run()
    no_exception(at)
    assert len(sent) == 1
    assert any("Gracias" in s.value for s in at.success)
    assert "Enviar calificación" not in page_texts(at)


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
    """La API entrega el tema en modo repaso: explicación y video, «Repaso» y sin quiz."""
    for step_id, note in ((812, "Ya aprobaste este tema."), (811, "Este tema se omitió")):
        at = learner_app("learner_path", TOPIC, run=False)
        session_of(at).learner.step_id = step_id
        at.run()
        no_exception(at)
        texts = page_texts(at)
        assert "Repaso" in texts
        assert "QUIZ DEL TEMA" not in texts
        assert "Empezar quiz" not in texts
        assert "topic-start-quiz" not in {b.key for b in at.button}
        assert any(t.startswith(note) for t in texts)
        button(at, "Volver a mi ruta").click().run()
        assert "Ver otras rutas" in page_texts(at)


def test_e6_review_mode_shows_the_explanation_b025() -> None:
    at = learner_app("learner_path", TOPIC, run=False)
    session_of(at).learner.step_id = 812
    at.run()
    no_exception(at)
    regular = learner_app("learner_path", TOPIC, run=False)
    session_of(regular).learner.step_id = 813
    regular.run()
    # El repaso trae el mismo contenido del tema; solo cambia la tarjeta de la derecha.
    shown = set(page_texts(at))
    assert "Regresión lineal" in shown
    assert len(shown & set(page_texts(regular))) > 3


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
        alerts=True,
    )


def test_e6b_expired_token_while_saving_goes_to_a7_and_keeps_the_answers_b031() -> None:
    """B-031: un 401 dentro del fragmento de la hoja ya no deja el traceback ni bloquea «Siguiente».

    `main.py` atiende el error en una ejecución completa (A7) y las respuestas siguen en la sesión.
    """
    at = _open_quiz()
    client = client_of(at)
    original = client.save_attempt_answers
    fail(at, "save_attempt_answers", ApiError(401, "TOKEN_EXPIRED"))
    at.radio[0].set_value(at.radio[0].options[0]).run()
    button(at, "Siguiente").click().run()
    no_exception(at)
    assert "Tu sesión expiró" in page_texts(at, skip_header=False)
    sheet = session_of(at).learner.sheet
    assert sheet.index == 0
    assert len(sheet.answers) == 1
    # Con la sesión renovada, la hoja vuelve con lo respondido y «Siguiente» funciona.
    client.save_attempt_answers = original  # type: ignore[method-assign]
    at.run()
    no_exception(at)
    assert not button(at, "Siguiente").disabled
    button(at, "Siguiente").click().run()
    no_exception(at)
    assert any("Pregunta 2 de 5" in t for t in page_texts(at))


def test_e6b_role_error_while_saving_shows_a6_b031() -> None:
    at = _open_quiz()
    fail(at, "save_attempt_answers", ApiError(403, "INSUFFICIENT_ROLE"))
    at.radio[0].set_value(at.radio[0].options[0]).run()
    button(at, "Siguiente").click().run()
    no_exception(at)
    assert "No tienes permiso para ver esta página" in page_texts(at, skip_header=False)


def test_e6c_short_answer_shows_the_rubric_and_limit() -> None:
    at = _open_quiz()
    _answer_all(at, 4)
    no_exception(at)
    texts = page_texts(at)
    assert "Pregunta 5 de 5 · Respuesta corta" in texts
    assert "0 / 500 caracteres" not in texts  # un solo contador: el del cuadro (V-036)
    assert "Quiz del tema" in texts
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
    matches_figma(at, "U1c", accepted=(FIGMA_ESTIMATE, FIGMA_PROTOTYPE_NOTE))


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
        accepted=(FIGMA_ESTIMATE, FIGMA_PROTOTYPE_NOTE),
    )
    at.switch_page(QUIZ).run()  # segunda consulta: las preguntas están listas
    no_exception(at)
    assert "Quiz: Regresión logística" in page_texts(at)


def test_u1c_passed_topic_shows_the_result_without_asking_for_its_content() -> None:
    """Al aprobar, el tema queda `passed` y la API ya no entrega su contenido (409)."""
    at = _open_quiz(script=GRADE_SCRIPT)
    _answer_all(at, 5)
    client_of(at)._script = LearnerScript(
        {**client_of(at)._script.docs, "path": "learner/path_all_passed"}
    )
    at.run()  # segunda consulta: terminó y el tema quedó aprobado
    no_exception(at)
    assert "¡Tema aprobado!" in page_texts(at)
    assert not at.error


def _waiting_for(at: AppTest, attempt_id: int, job_id: str) -> None:
    """La inscripción dice `wait_job` (U1c), como la API cuando la persona vuelve a mitad."""
    client_of(at).echo_next_action(
        NextAction(type="wait_job", attempt_id=attempt_id, job_id=job_id, screen="U1c")
    )


def test_u1c_coming_back_while_grading_waits_and_shows_the_result() -> None:
    at = learner_app("learner_path", QUIZ, run=False)
    _waiting_for(at, 9002, "job-grading")
    at.run()
    no_exception(at)
    assert "Calificando tu respuesta corta" in page_texts(at)
    assert session_of(at).learner.attempt_id == 9002
    at.run()  # segunda consulta: terminó
    no_exception(at)
    assert "¡Tema aprobado!" in page_texts(at)


def test_u1c_coming_back_while_the_final_is_graded_goes_to_the_final() -> None:
    script = LearnerScript({"attempt": "learner/attempt_final"})
    at = learner_app("learner_path", QUIZ, script=script, run=False)
    _waiting_for(at, 9100, "job-final-grading")
    at.run()
    no_exception(at)
    assert session_of(at).learner.final_attempt_id == 9100


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


def test_e7_after_the_last_topic_the_button_follows_the_next_action_b046() -> None:
    """Aprobar el último tema no ofrece «Siguiente tema»: lleva a la evaluación final."""
    at = _result("learner_path")
    session_of(at).learner.attempt_id = 9002
    client = client_of(at)
    original = client.get_attempt_result
    client.get_attempt_result = lambda attempt_id: original(attempt_id).model_copy(  # type: ignore[method-assign]
        update={"next_action": NextAction(type="take_final", screen="E8")}
    )
    at.run()
    no_exception(at)
    texts = page_texts(at)
    assert "Presentar evaluación final" in texts
    assert "Siguiente tema" not in texts


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


def test_e7b_next_attempt_badge_and_review_link() -> None:
    at = _result("learner_quiz_failed")
    assert "Intento 2 de 3" in {
        m.group(1) for e in at.markdown if (m := re.fullmatch(r":blue-badge\[(.*)\]", e.value))
    }
    assert at.button(key="request-review-1005").proto.type == "tertiary"


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


def test_e7c_offers_to_continue_when_a_topic_does_not_depend_on_the_exhausted_one_b059() -> None:
    at = _result("learner_exhausted")
    no_exception(at)
    texts = page_texts(at)
    assert any(
        "Mientras tanto, puedes seguir con los temas que no dependen de este" in t for t in texts
    )
    assert "Continuar con Árboles de decisión" in [b.label for b in at.button]
    assert "Volver a mi ruta" in [b.label for b in at.button]


def test_e7c_promises_nothing_when_every_topic_depends_on_the_exhausted_one_b059() -> None:
    """Caso real: los otros temas dependen del agotado y la API los deja «en espera»."""
    at = learner_app("learner_exhausted", QUIZ_RESULT, run=False)
    session_of(at).learner.step_id = 813
    client = client_of(at)
    original = client.get_path

    def all_waiting(enrollment_id: int) -> PathDetail:
        path = original(enrollment_id)
        steps = [
            step if step.step_id == 813 else step.model_copy(update={"status": "on_hold"})
            for step in path.steps
        ]
        return path.model_copy(update={"steps": steps})

    client.get_path = all_waiting  # type: ignore[method-assign]
    at.run()
    no_exception(at)
    texts = page_texts(at)
    assert not any("Mientras tanto" in t or "no dependen de este" in t for t in texts)
    assert any("Tu ruta queda en espera hasta que decida." in t for t in texts)
    assert "Tu instructor ya recibió una alerta" in " ".join(texts)
    assert at.button(key="result-back").label == "Volver a mi ruta"
    assert "result-continue" not in {b.key for b in at.button}
    assert "Puedes seguir" not in {
        m.group(1) for e in at.markdown if (m := re.fullmatch(r":[a-z]+-badge\[(.*)\]", e.value))
    }


def test_e7c_shows_a_single_threshold_text_b059() -> None:
    at = _result("learner_exhausted")
    needs = [t for t in page_texts(at) if t.startswith("Necesitas")]
    assert needs == ["Necesitas 70 % para aprobar."]


def test_e7c_route_rows_have_one_badge_each() -> None:
    at = _result("learner_exhausted")
    found = [
        m.group(1) for e in at.markdown if (m := re.fullmatch(r":[a-z]+-badge\[(.*)\]", e.value))
    ]
    assert found.count("En espera") >= 1
    assert "Puedes seguir" in found
    assert ":red[40 % · 2 de 5]" in [e.value for e in at.markdown]


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


# --- V-034 a V-036 · barra de progreso, aviso, tarjeta y chips -----------------------------------


def test_quiz_shows_the_progress_bar_notice_and_card() -> None:
    at = _open_quiz()
    assert [p.value for p in at.progress] == [20]  # pregunta 1 de 5
    assert any("Quiz del tema · Sin ayuda de IA" in w.value for w in at.warning)
    assert at.get_by_key("card-quiz-quiz")
    assert "Tutor IA desactivado durante el quiz" in page_texts(at)
    _answer_all(at, 1)
    assert [p.value for p in at.progress] == [40]


def test_quiz_short_answer_has_one_counter_and_a_rubric_box() -> None:
    at = _open_quiz()
    _answer_all(at, 4)
    assert [p.value for p in at.progress] == [100]
    assert at.get_by_key("card-rubric-quiz")
    assert not any("caracteres" in c.value for c in at.caption)
    assert not any(t.startswith("Quiz: ") for t in page_texts(at))


# --- B-052 · número de criterios en U1c ------------------------------------------------------


def _quiz_with_summary(summary: str | None) -> AppTest:
    at = _open_quiz(script=GRADE_SCRIPT)
    client = client_of(at)
    original = client.get_attempt

    def attempt(attempt_id: int):  # type: ignore[no-untyped-def]
        doc = original(attempt_id)
        items = [
            i.model_copy(update={"rubric_summary": summary}) if i.item_type == "short_answer" else i
            for i in doc.items
        ]
        return doc.model_copy(update={"items": items})

    client.get_attempt = attempt  # type: ignore[method-assign]
    _answer_all(at, 5)
    return at


def test_u1c_names_the_real_number_of_criteria_b052() -> None:
    at = _quiz_with_summary("Se califica con una rúbrica de 2 criterios: (1) a y (2) b.")
    no_exception(at)
    texts = page_texts(at)
    assert "En curso · Aplicar la rúbrica de 2 criterios a tu respuesta corta" in texts
    assert not any("de 3 criterios" in t for t in texts)


def test_u1c_without_the_criteria_count_has_no_number_b052() -> None:
    at = _quiz_with_summary(None)
    no_exception(at)
    assert "En curso · Aplicar la rúbrica a tu respuesta corta" in page_texts(at)


def test_grading_screen_reads_the_attempt_once_per_attempt_b052() -> None:
    """La pantalla de espera se repite cada 2 s: la rúbrica no suma una consulta por sondeo."""

    def app() -> None:
        import streamlit as st

        from clients.fixtures import FixturesClient
        from core.learner_flow import grading_screen

        client = FixturesClient()
        original = client.get_attempt

        def counting(attempt_id: int):  # type: ignore[no-untyped-def]
            st.session_state.setdefault("calls", []).append(attempt_id)
            return original(attempt_id)

        client.get_attempt = counting  # type: ignore[method-assign]
        for _ in range(3):  # tres sondeos seguidos del mismo intento
            grading_screen(client, key="g", attempt_id=1, error_message="x")

    at = AppTest.from_function(app).run()
    assert not at.exception
    assert len(at.session_state["calls"]) == 1


# --- B-060 · U1b desde el clic en «Reintentar con preguntas nuevas» ------------------------------


def _record_create_attempt(at: AppTest) -> list[dict[str, object]]:
    """Envuelve `create_attempt` para ver qué había en la sesión mientras se pedía el intento."""
    from core import polling

    client = client_of(at)
    original = client.create_attempt
    calls: list[dict[str, object]] = []

    def spy(*args: object, **kwargs: object) -> object:
        learner = session_of(at).learner
        calls.append(
            {
                "key": kwargs.get("idempotency_key"),
                "pending": learner.pending_attempt,
                "quiet": polling.in_wait_mode(),
            }
        )
        return original(*args, **kwargs)  # type: ignore[arg-type]

    client.create_attempt = spy  # type: ignore[method-assign]
    return calls


def test_e7b_retry_asks_for_the_attempt_from_the_quiz_with_u1b_on_screen_b060() -> None:
    at = _result("learner_quiz_failed")
    calls = _record_create_attempt(at)
    button(at, "Reintentar con preguntas nuevas").click().run()
    no_exception(at)
    assert len(calls) == 1
    call = calls[0]
    # Se pide con U1b en pantalla (el reintento sigue pendiente) y sin «Cargando…» encima.
    assert call["pending"] is not None
    assert call["quiet"] is True
    learner = session_of(at).learner
    assert learner.pending_attempt is None
    assert learner.attempt_id == 9002
    assert "Quiz: Regresión logística" in page_texts(at)


def test_e7b_retry_keeps_the_same_idempotency_key_b060() -> None:
    """La clave sigue siendo la del intento (`attempt-<inscripción>-<tema>-<usados>`)."""
    at = _result("learner_quiz_failed")
    calls = _record_create_attempt(at)
    button(at, "Reintentar con preguntas nuevas").click().run()
    keys = session_of(at).idempotency_keys
    names = [name for name in keys if name.startswith("attempt-") and name.endswith("-813-1")]
    assert len(names) == 1
    assert calls[0]["key"] == keys[names[0]]


def test_e7b_retry_that_needs_new_questions_shows_u1b_with_the_new_estimate_b060() -> None:
    at = _result("learner_quiz_failed")
    client_of(at)._script = LearnerScript(
        {**client_of(at)._script.docs, "create_attempt": "learner/job_accepted_retry"}
    )
    button(at, "Reintentar con preguntas nuevas").click().run()
    no_exception(at)
    texts = page_texts(at)
    assert "Preparando preguntas nuevas para tu intento 2" in texts
    assert "Tiempo estimado: hasta 2 minutos" in texts
    assert "Tiempo estimado: menos de 20 segundos" not in texts


def test_e7b_retry_with_an_open_attempt_follows_the_api_b060() -> None:
    at = _result("learner_quiz_failed")
    fail(at, "create_attempt", ApiError(409, "ATTEMPT_IN_PROGRESS", "open"))
    button(at, "Reintentar con preguntas nuevas").click().run()
    no_exception(at)
    assert session_of(at).learner.pending_attempt is None


def test_e7b_retry_error_is_shown_and_forgets_the_pending_attempt_b060() -> None:
    at = _result("learner_quiz_failed")
    fail(at, "create_attempt", ApiError(409, "MAX_ATTEMPTS_EXCEEDED", "no more"))
    button(at, "Reintentar con preguntas nuevas").click().run()
    no_exception(at)
    assert session_of(at).learner.pending_attempt is None
    assert at.error
