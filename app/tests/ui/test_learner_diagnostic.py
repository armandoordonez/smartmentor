"""E3, U1a, E4, E4b, E5 y E5b: diagnóstico, resultado, objetivo y ruta."""

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

from clients.base import ApiError
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


def test_e3_dont_know_counts_as_an_answer() -> None:
    at = learner_app("learner_diagnostic", DIAGNOSTIC)
    button(at, "No lo sé").click().run()
    no_exception(at)
    assert not button(at, "Siguiente").disabled


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
    matches_figma(at, "U1a", accepted=("Prototipo: esta pantalla avanza sola a los 2 segundos.",))
    at.run()  # segunda consulta: el trabajo terminó
    no_exception(at)
    assert "Tu punto de partida" in page_texts(at)


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


def test_e4_confirm_goes_to_the_path() -> None:
    at = learner_app("learner_objective", DIAGNOSTIC_RESULT)
    button(at, "Confirmar y ver mi ruta").click().run()
    no_exception(at)
    assert "Regresión logística" in page_texts(at)  # el next_action lleva al tema


def test_e4b_edit_shows_the_three_part_editor() -> None:
    at = learner_app("learner_objective", DIAGNOSTIC_RESULT)
    button(at, "Editar el objetivo").click().run()
    no_exception(at)
    texts = page_texts(at)
    assert "Editar tu objetivo" in texts
    assert "Guardar objetivo" in texts
    assert "Confirmar y ver mi ruta" not in texts


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


def test_e4b_cancel_returns_to_the_summary() -> None:
    at = learner_app("learner_objective", DIAGNOSTIC_RESULT)
    button(at, "Editar el objetivo").click().run()
    button(at, "Cancelar").click().run()
    assert "Confirmar y ver mi ruta" in page_texts(at)


# --- E5 · E5b ----------------------------------------------------------------------------------


def test_e5_follows_figma() -> None:
    at = learner_app("learner_path", PATH)
    matches_figma(
        at,
        "E5",
        accepted=(
            # El API no dice de qué tema es prerrequisito, ni el último puntaje (solo el mejor).
            "Incluido como prerrequisito débil de Regresión logística (64 % en el diagnóstico)",
            "Intento 2 de 3 · último puntaje 60 %",
            # Botón de demostración que no se construye.
            "Demo: ver la variante de ruta fija (grupo de comparación)",
        ),
    )


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


def test_e5_edit_objective_opens_the_editor() -> None:
    at = learner_app("learner_path", PATH)
    button(at, "Editar objetivo").click().run()
    no_exception(at)
    assert "Editar tu objetivo" in page_texts(at)


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
