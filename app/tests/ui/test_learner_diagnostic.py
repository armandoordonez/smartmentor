"""E3, U1a, E4, E4b, E5 y E5b: diagnóstico, resultado, objetivo y ruta."""

from typing import Any

from apptest import button, page_texts, session_of
from learner_support import (
    DIAGNOSTIC,
    DIAGNOSTIC_RESULT,
    PATH,
    client_of,
    fail,
    learner_app,
    matches_figma,
    no_exception,
)
from streamlit.testing.v1 import AppTest

from clients.base import ApiError
from clients.models import Enrollment
from clients.ops_learner import LearnerScript


def test_e3_follows_figma() -> None:
    at = learner_app("learner_diagnostic", DIAGNOSTIC)
    matches_figma(
        at,
        "E3",
        accepted=(
            # La marca del curso sale del nombre completo de la ruta.
            "PASO 3 DE 4 · DIAGNÓSTICO · FUNDAMENTOS DE ML · Pregunta 4 de 15",
            # Nota del prototipo que no se construye.
            "(Prototipo) «Siguiente» simula terminar las 15 preguntas y pasa al cálculo del nivel.",
        ),
    )


def test_e3_resumes_at_the_first_unanswered_question() -> None:
    at = learner_app("learner_diagnostic", DIAGNOSTIC)
    texts = page_texts(at)
    assert any("Pregunta 4 de 15" in t for t in texts)
    assert "Tema · Regresión lineal · Bloom · Aplicar" in texts


def test_e3_failed_scoring_reopens_the_diagnostic_to_send_it_again() -> None:
    """Si el cálculo falla, la API deja el diagnóstico en `scoring_failed` y pide continuarlo."""
    script = LearnerScript({"diagnostic": "learner/diagnostic_scoring_failed"})
    at = learner_app("learner_diagnostic", DIAGNOSTIC, script=script)
    no_exception(at)
    assert not at.error
    assert any("Pregunta 4 de 15" in t for t in page_texts(at))


def test_e4_without_a_proposed_objective_opens_the_editor() -> None:
    at = learner_app("learner_objective", DIAGNOSTIC_RESULT, run=False)
    client = client_of(at)
    result = client.get_diagnostic_result(1)
    client.get_diagnostic_result = lambda _e: result.model_copy(  # type: ignore[method-assign]
        update={"proposed_objective": None}
    )
    at.run()
    no_exception(at)
    assert "Confirmar y ver mi ruta" not in page_texts(at)
    assert "Verbo de Bloom" in [s.label for s in at.selectbox]


def test_e3_next_is_disabled_until_the_question_is_answered() -> None:
    at = learner_app("learner_diagnostic", DIAGNOSTIC)
    assert button(at, "Siguiente").disabled
    at.radio[0].set_value(at.radio[0].options[0]).run()
    assert not button(at, "Siguiente").disabled


def test_e3_next_saves_partial_answers() -> None:
    at = learner_app("learner_diagnostic", DIAGNOSTIC)
    saved: list[int] = []
    client = client_of(at)
    original = client.save_diagnostic_answers

    def spy(enrollment_id: int, answers: object) -> int:
        count = original(enrollment_id, answers)  # type: ignore[arg-type]
        saved.append(count)
        return count

    client.save_diagnostic_answers = spy  # type: ignore[method-assign]
    at.radio[0].set_value(at.radio[0].options[1]).run()
    button(at, "Siguiente").click().run()
    no_exception(at)
    assert saved == [4]
    assert any("Pregunta 5 de 15" in t for t in page_texts(at))


def test_e3_dont_know_counts_as_an_answer_and_moves_on() -> None:
    """B-019: «No lo sé» guarda y pasa a la siguiente pregunta; al volver, se ve lo elegido."""
    at = learner_app("learner_diagnostic", DIAGNOSTIC)
    assert any("Pregunta 4 de 15" in t for t in page_texts(at))
    button(at, "No lo sé").click().run()
    no_exception(at)
    assert any("Pregunta 5 de 15" in t for t in page_texts(at))
    button(at, "Anterior").click().run()
    assert any("Pregunta 4 de 15" in t for t in page_texts(at))
    assert any(t.startswith("Respondiste «No lo sé».") for t in page_texts(at))
    assert not button(at, "Siguiente").disabled


def test_e3_expired_token_in_dont_know_goes_to_a7_and_keeps_the_answer_b031() -> None:
    """B-031 en la hoja con `rerun_scope="fragment"` (E3): «No lo sé» con el token vencido."""
    at = learner_app("learner_diagnostic", DIAGNOSTIC)
    client = client_of(at)
    original = client.save_diagnostic_answers
    fail(at, "save_diagnostic_answers", ApiError(401, "TOKEN_EXPIRED"))
    button(at, "No lo sé").click().run()
    no_exception(at)
    assert "Tu sesión expiró" in page_texts(at, skip_header=False)
    assert any(a.dont_know for a in session_of(at).learner.sheet.answers.values())
    client.save_diagnostic_answers = original  # type: ignore[method-assign]
    at.run()
    no_exception(at)
    assert any("Pregunta 4 de 15" in t for t in page_texts(at))
    assert any(t.startswith("Respondiste «No lo sé».") for t in page_texts(at))


def test_e3_back_goes_to_the_previous_question() -> None:
    at = learner_app("learner_diagnostic", DIAGNOSTIC)
    button(at, "Anterior").click().run()
    assert any("Pregunta 3 de 15" in t for t in page_texts(at))


def test_e3_last_question_submits_and_waits_for_the_job() -> None:
    script = LearnerScript({"diagnostic": "learner/diagnostic_last"})
    at = learner_app("learner_diagnostic", DIAGNOSTIC, script=script)
    assert any("Pregunta 15 de 15" in t for t in page_texts(at))
    at.radio[0].set_value(at.radio[0].options[0]).run()
    button(at, "Enviar diagnóstico").click().run()
    no_exception(at)
    assert session_of(at).learner.diagnostic_job_id == "job-diagnostic"
    assert "Calculando tu nivel y proponiendo tu objetivo" in page_texts(at)


def test_u1a_follows_figma_and_finishes_on_the_second_poll() -> None:
    at = learner_app("learner_calculating", DIAGNOSTIC)
    # Figma dice «menos de 20 segundos»; la app dice «hasta 2 minutos» (B-060).
    matches_figma(
        at,
        "U1a",
        accepted=(
            "Tiempo estimado: menos de 20 segundos",
            "Prototipo: esta pantalla avanza sola a los 2 segundos.",
        ),
    )
    at.run()  # segunda consulta: el trabajo terminó
    no_exception(at)
    assert "Tu punto de partida" in page_texts(at)


def test_u1a_reads_after_the_job_finishes_do_not_draw_the_spinner_t054() -> None:
    """Al terminar el trabajo, releer la inscripción corre en modo espera (sin «Cargando…»)."""
    from core import polling

    at = learner_app("learner_calculating", DIAGNOSTIC)
    client = client_of(at)
    seen: list[bool] = []
    for name in ("get_enrollment", "list_enrollments"):
        original = getattr(client, name)

        def spy(*args: object, _original: Any = original, **kwargs: object) -> Any:
            seen.append(polling.in_wait_mode())
            return _original(*args, **kwargs)

        setattr(client, name, spy)
    at.run()  # segunda consulta: el trabajo terminó
    no_exception(at)
    assert seen
    assert seen[0]  # la lectura del arranque ya ocurre con el sondeo activo
    assert polling.WAIT_MODE_KEY not in at.session_state  # al navegar a otra pantalla se apaga


def test_u1a_error_keeps_the_progress_and_offers_retry() -> None:
    at = learner_app("learner_calculating_error", DIAGNOSTIC)
    at.run()
    no_exception(at)
    assert any("Tu avance está guardado" in e.value for e in at.error)
    assert [b.label for b in at.button if b.key and b.key.startswith("loading-")] == [
        "Reintentar",
        "Volver a mi ruta",
    ]
    at.button(key="loading-retry-diagnostic").click().run()
    no_exception(at)
    assert "Calculando tu nivel y proponiendo tu objetivo" in page_texts(at)


def test_e3_offline_shows_a_friendly_error() -> None:
    at = learner_app("learner_offline", DIAGNOSTIC)
    no_exception(at)
    assert at.error
    assert "no está disponible" in at.error[0].value


# --- E4 · E4b ----------------------------------------------------------------------------------


def test_e4_follows_figma() -> None:
    at = learner_app("learner_objective", DIAGNOSTIC_RESULT)
    matches_figma(at, "E4")


def _assert_on_the_path(at: AppTest) -> None:
    """E5 (la ruta), no E6 (el tema): tiene la tarjeta de la evaluación final y «Continuar tema»."""
    no_exception(at)
    assert at.get_by_key("path-continue")
    assert at.get_by_key("card-final")
    assert "Evaluación final" in page_texts(at)
    assert session_of(at).learner.step_id == 813  # el `next_action` queda recordado


def test_e4_confirm_goes_to_the_path_b044() -> None:
    at = learner_app("learner_objective", DIAGNOSTIC_RESULT)
    button(at, "Confirmar y ver mi ruta").click().run()
    _assert_on_the_path(at)
    # El botón principal de E5 sigue llevando al primer tema.
    button(at, "Continuar tema").click().run()
    no_exception(at)
    assert any("Tema " in t and " de " in t for t in page_texts(at))
    assert "Empezar quiz" in page_texts(at)


def test_e4b_save_goes_to_the_path_b044() -> None:
    at = learner_app("learner_objective", DIAGNOSTIC_RESULT)
    button(at, "Editar el objetivo").click().run()
    at.text_input(key="objective-criterion").set_value("con 85 % en la final").run()
    button(at, "Guardar objetivo").click().run()
    _assert_on_the_path(at)
    assert not session_of(at).learner.edit_objective


def test_e4b_edit_shows_the_three_part_editor() -> None:
    at = learner_app("learner_objective", DIAGNOSTIC_RESULT)
    button(at, "Editar el objetivo").click().run()
    no_exception(at)
    # V-041: el editor es una ventana modal (`st.dialog`) sobre el resumen, que sigue debajo.
    assert button(at, "Guardar objetivo")
    assert "Confirmar y ver mi ruta" in page_texts(at)
    assert any("El 80 % para obtener el badge" in s.value for s in at.success)


def test_e4b_save_sends_the_edited_objective() -> None:
    at = learner_app("learner_objective", DIAGNOSTIC_RESULT)
    sent = []
    client = client_of(at)
    original = client.set_objective

    def spy(enrollment_id: int, objective: object) -> object:
        sent.append(objective)
        return original(enrollment_id, objective)  # type: ignore[arg-type]

    client.set_objective = spy  # type: ignore[method-assign]
    button(at, "Editar el objetivo").click().run()
    at.text_input(key="objective-criterion").set_value("con 85 % en la final").run()
    button(at, "Guardar objetivo").click().run()
    no_exception(at)
    assert sent[0].origin == "learner_edited"
    assert sent[0].criterion == "con 85 % en la final"


def test_e4b_not_measurable_objective_shows_the_api_message() -> None:
    at = learner_app("learner_objective", DIAGNOSTIC_RESULT)
    fail(at, "set_objective", ApiError(422, "OBJECTIVE_NOT_MEASURABLE"))
    button(at, "Editar el objetivo").click().run()
    button(at, "Guardar objetivo").click().run()
    no_exception(at)
    assert at.error[0].value == "Agrega cómo sabrás que lo lograste."


def test_e4b_invalid_bloom_verb_shows_a_friendly_message() -> None:
    at = learner_app("learner_objective", DIAGNOSTIC_RESULT)
    fail(at, "set_objective", ApiError(422, "INVALID_BLOOM_VERB"))
    button(at, "Editar el objetivo").click().run()
    button(at, "Guardar objetivo").click().run()
    no_exception(at)
    assert "verbo de la lista" in at.error[0].value


def test_e4b_offers_the_bloom_verbs_of_the_api_and_drops_the_false_note() -> None:
    at = learner_app("learner_objective", DIAGNOSTIC_RESULT)
    button(at, "Editar el objetivo").click().run()
    options = at.selectbox(key="objective-verb").options
    assert {"Aplicar", "Construir", "Implementar", "Diseñar"} <= set(options)
    assert not any("Guardar se desactiva" in t for t in page_texts(at))


def test_e4b_back_to_the_proposal_brings_the_stored_proposal_not_the_edit() -> None:
    """B-033: el objetivo editado ya no sobrescribe la propuesta de la IA."""
    at = learner_app("learner_objective", DIAGNOSTIC_RESULT)
    client = client_of(at)
    proposal = client.get_diagnostic_result(1).proposed_objective
    assert proposal is not None
    edited = proposal.model_copy(
        update={"criterion": "con al menos 95 % en la evaluación final", "origin": "learner_edited"}
    )
    original = client.get_enrollment

    def with_edited_objective(enrollment_id: int) -> Enrollment:
        return original(enrollment_id).model_copy(update={"objective": edited})

    client.get_enrollment = with_edited_objective  # type: ignore[method-assign]
    button(at, "Editar el objetivo").click().run()
    assert at.text_input(key="objective-criterion").value == edited.criterion
    button(at, "Volver a la propuesta de la IA").click().run()
    no_exception(at)
    assert at.text_input(key="objective-criterion").value == proposal.criterion


def test_e4b_cancel_returns_to_the_summary() -> None:
    at = learner_app("learner_objective", DIAGNOSTIC_RESULT)
    button(at, "Editar el objetivo").click().run()
    button(at, "Cancelar").click().run()
    assert "Confirmar y ver mi ruta" in page_texts(at)


def test_e4b_cancel_discards_the_edit_when_reopening_the_editor() -> None:
    """E4 termina en `st.stop()`: Streamlit 1.67 conserva el texto de los campos aunque no se
    dibujen, así que sin limpiarlos lo cancelado volvía a aparecer al editar otra vez."""
    at = learner_app("learner_objective", DIAGNOSTIC_RESULT)
    button(at, "Editar el objetivo").click().run()
    original = at.text_input(key="objective-criterion").value
    at.text_input(key="objective-criterion").set_value("texto descartado").run()
    button(at, "Cancelar").click().run()
    button(at, "Editar el objetivo").click().run()
    no_exception(at)
    assert at.text_input(key="objective-criterion").value == original
    assert original != "texto descartado"


# --- E5 · E5b ----------------------------------------------------------------------------------


def test_e5_follows_figma() -> None:
    at = learner_app("learner_path", PATH)
    matches_figma(
        at,
        "E5",
        accepted=(
            # Con la ruta confirmada el objetivo no se edita (B-032): va una nota en su lugar.
            "Editar objetivo",
            # El API no dice de qué tema es prerrequisito, ni el último puntaje (solo el mejor).
            "Incluido como prerrequisito débil de Regresión logística (64 % en el diagnóstico)",
            "Intento 2 de 3 · último puntaje 60 %",
            # Botón de demostración que no se construye.
            "Demo: ver la variante de ruta fija (grupo de comparación)",
        ),
    )


def test_e5_passed_and_skipped_topics_open_for_review_b025() -> None:
    """La API entrega un tema aprobado u omitido en modo repaso: E5 los deja abrir."""
    at = learner_app("learner_path", PATH)
    keys = {b.key for b in at.button}
    assert "open-step-811" in keys  # omitido
    assert "open-step-812" in keys  # aprobado
    assert "open-step-813" in keys  # en curso


def test_e5_skipped_topic_opens_in_review_mode_b025() -> None:
    at = learner_app("learner_path", PATH)
    at.button(key="open-step-811").click().run()
    no_exception(at)
    assert session_of(at).learner.step_id == 811
    texts = page_texts(at)
    assert "Repaso" in texts
    assert "Empezar quiz" not in texts


def test_e5_open_step_goes_to_the_topic() -> None:
    at = learner_app("learner_path", PATH)
    at.button(key="open-step-814").click().run()
    no_exception(at)
    assert session_of(at).learner.step_id == 814
    assert any("Tema 4 de 5" in t for t in page_texts(at))


def test_e5_continue_follows_next_action() -> None:
    at = learner_app("learner_path", PATH)
    button(at, "Continuar tema").click().run()
    no_exception(at)
    assert session_of(at).learner.step_id == 813
    assert "Regresión logística" in page_texts(at)


def test_e5_confirmed_path_does_not_offer_to_edit_the_objective() -> None:
    """Con la ruta confirmada la API rechaza el objetivo (409): E5 no ofrece editarlo (B-032)."""
    at = learner_app("learner_path", PATH)
    no_exception(at)
    assert "path-edit-objective" not in {b.key for b in at.button}
    texts = page_texts(at)
    assert "El objetivo quedó fijado al confirmar tu ruta" in texts
    assert "El objetivo se fija al confirmar la ruta" not in texts
    assert "TU OBJETIVO · PROPUESTO CON IA Y CONFIRMADO POR TI" in texts


def test_e5_pending_objective_still_opens_the_editor() -> None:
    at = learner_app("learner_path", PATH, run=False)
    for enrollment in client_of(at)._enrollments:
        enrollment.status = "objective_pending"
    at.run()
    texts = page_texts(at)
    # B-051: sin confirmar la ruta no se dice «confirmado por ti» ni que ya quedó fijado.
    assert "El objetivo se fija al confirmar la ruta" in texts
    assert "El objetivo quedó fijado al confirmar tu ruta" not in texts
    assert "TU OBJETIVO · PROPUESTO CON IA, SIN CONFIRMAR" in texts
    assert not any("CONFIRMADO POR TI" in t for t in texts)
    button(at, "Editar objetivo").click().run()
    no_exception(at)
    assert button(at, "Guardar objetivo")


def test_e5b_fixed_path_follows_figma() -> None:
    at = learner_app("learner_fixed_path", PATH)
    matches_figma(
        at,
        "E5b",
        accepted=(
            "Fundamentos de ML › Mi ruta",
            "Continuar con Regresión logística",
        )[:1],
    )


def test_e5_offline() -> None:
    at = learner_app("learner_offline", PATH)
    no_exception(at)
    assert at.error


def test_e4b_keeps_a_proposed_verb_outside_the_list() -> None:
    """B-020: la IA propuso «Construir»; al editar, el verbo no se pierde."""
    at = learner_app("learner_objective", DIAGNOSTIC_RESULT, run=False)
    client = client_of(at)
    result = client.get_diagnostic_result(1)
    assert result.proposed_objective is not None
    proposal = result.proposed_objective.model_copy(update={"bloom_verb": "Construir"})
    client.get_diagnostic_result = lambda _e: result.model_copy(  # type: ignore[method-assign]
        update={"proposed_objective": proposal}
    )
    at.run()
    button(at, "Editar el objetivo").click().run()
    no_exception(at)
    verb = next(s for s in at.selectbox if s.label == "Verbo de Bloom")
    assert verb.value == "Construir"


# --- B-039 · E5 y E4b ----------------------------------------------------------------------------


def test_e5_continue_says_final_assessment_when_it_comes_next_b039() -> None:
    at = learner_app("learner_final_ready", PATH)
    no_exception(at)
    assert {b.key: b.label for b in at.button}["path-continue"] == "Presentar evaluación final"


def test_e5_continue_says_badge_when_the_survey_is_pending_b045() -> None:
    """Con la encuesta pendiente «Continuar» lleva a E10, que la ofrece como tarjeta (B-045)."""
    at = learner_app("learner_completed", PATH)
    no_exception(at)
    assert {b.key: b.label for b in at.button}["path-continue"] == "Ver badge"


def test_e5_does_not_show_zero_savings_with_skipped_topics_b039() -> None:
    at = learner_app("learner_path", PATH, run=False)
    client = client_of(at)
    path = client.get_path(1)
    savings = path.savings.model_copy(update={"skipped_minutes": 0})
    client.get_path = lambda _e: path.model_copy(update={"savings": savings})  # type: ignore[method-assign]
    at.run()
    no_exception(at)
    texts = page_texts(at)
    assert not any("ahorro 0 min" in t for t in texts)
    assert any("1 omitido por tu diagnóstico" in t for t in texts)


def test_e4b_verb_selector_placeholder_is_in_spanish_b039() -> None:
    at = learner_app("learner_objective", DIAGNOSTIC_RESULT)
    button(at, "Editar el objetivo").click().run()
    verb = next(s for s in at.selectbox if s.label == "Verbo de Bloom")
    assert verb.placeholder == "Elige un verbo"
