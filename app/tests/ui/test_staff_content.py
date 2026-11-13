"""D5 a D5f: revisión de contenido, anotación, calificación humana, videos y calidad."""

from apptest import page_texts
from staff_support import (
    assert_matches_figma,
    assert_no_exception,
    click,
    staff_app,
    staff_text_reader,  # noqa: F401  (fixture autouse)
    with_state,
)
from streamlit.testing.v1 import AppTest

REVIEW = "pages/instructor/content_review.py"
ANNOTATION = "pages/instructor/item_annotation.py"
GRADING = "pages/instructor/short_answer_grading.py"
VIDEOS = "pages/instructor/topic_videos.py"
QUALITY = "pages/instructor/video_quality.py"


def _open(page: str, scenario: str = "default", **state: int | None) -> AppTest:
    at = staff_app(scenario=scenario)
    with_state(at, course_id=1, topic_id=103, path_id=11, **state).switch_page(page).run()
    return at


def test_d5_lists_resources_and_questions() -> None:
    at = _open(REVIEW)
    assert_no_exception(at)
    texts = page_texts(at)
    for expected in (
        "Revisión de contenido generado con IA",
        "Recursos (3)",
        "Banco de preguntas del tema",
        "Preguntas (3)",
        "Texto: explicación v1.3",
        "Apuntes unidad 3 · ISLR cap. 4",
        "0,86",
        "Video: Regresión logística (11 min)",
        "YouTube · relevancia 94 %",
        "¿Qué valores devuelve la función sigmoide?",
        "Opción múltiple",
        "Respuesta corta",
        "Anotar preguntas con la rúbrica",
        "Calificar respuestas cortas",
    ):
        assert any(expected in t for t in texts), expected


def test_d5_matches_figma_with_documented_differences() -> None:
    at = _open(REVIEW)
    assert_matches_figma(
        at,
        "D5",
        accepted=(
            # «Recursos (3)» y «Preguntas (12)» son contadores; el total de preguntas sale de los
            # datos.
            "Preguntas (12)",
            # Las acciones de cada fila son botones separados, no un solo texto.
            "Editar · Regenerar",
            "Aprobar · Editar",
            "Aprobar · Reemplazar",
            "Editar · Retirar",
            "Aprobar · Editar",
            "Aprobar · Editar",
        ),
    )


def test_d5_approve_and_retire_call_the_api() -> None:
    at = _open(REVIEW)
    approve = [b for b in at.button if b.label == "Aprobar"]
    assert approve
    approve[0].click().run()
    assert_no_exception(at)
    assert not at.error


def test_d5_invalid_transition_shows_a_message() -> None:
    at = _open(REVIEW, "forbidden")
    assert "403" in page_texts(at, skip_header=False)


def test_d5d_edit_text_resource() -> None:
    at = _open(REVIEW)
    edit = next(b for b in at.button if b.label == "Editar" and b.key.startswith("resources-1"))
    at = edit.click().run()
    texts = page_texts(at)
    assert "Editar la explicación del tema" in texts
    assert "Fidelidad 0,86" in texts
    assert any("queda como versión 1.4 (editada por instructor)" in t for t in texts)
    at = click(at, "Guardar y aprobar")
    assert_no_exception(at)
    assert "Editar la explicación del tema" not in page_texts(at)


def test_d5_regenerating_twice_asks_for_two_regenerations_b029() -> None:
    at = _open(REVIEW)
    client = at.session_state["app_session"].fixtures_client
    original = client.regenerate_resource
    keys: list[str] = []

    def spy(resource_id: int, *, idempotency_key: str) -> object:
        keys.append(idempotency_key)
        return original(resource_id, idempotency_key=idempotency_key)

    client.regenerate_resource = spy
    for _ in range(2):
        regen = next(b for b in at.button if b.label == "Regenerar")
        at = regen.click().run()
        assert_no_exception(at)
        assert any(s.value.startswith("Regenerando «") for s in at.success)
    assert len(keys) == 2
    assert keys[0] != keys[1]


def test_d5_edit_question_returns_to_review() -> None:
    at = _open(REVIEW)
    edit = next(b for b in at.button if b.label == "Editar" and b.key.startswith("items-700"))
    at = edit.click().run()
    assert "Editar pregunta" in page_texts(at)
    at = click(at, "Guardar")
    assert_no_exception(at)


def test_d5b_blind_annotation() -> None:
    at = _open(ANNOTATION)
    assert_no_exception(at)
    texts = page_texts(at)
    assert "Evaluador 1 de 2" in texts
    assert "23 de 60 anotadas" in texts
    assert any("Anotación ciega" in t for t in texts)
    save = next(b for b in at.button if b.label == "Guardar y siguiente")
    assert save.disabled


def test_d5b_complete_annotation_enables_saving() -> None:
    at = _open(ANNOTATION)
    for group in at.get("button_group"):
        group.set_value("Sí" if group.label != "Veredicto" else "Válida")
    at.run()
    at = click(at, "Guardar y siguiente")
    assert_no_exception(at)
    assert not at.error


def test_d5b_empty_queue_and_unassigned_evaluator() -> None:
    at = _open(ANNOTATION, "empty")
    assert any("No tienes preguntas pendientes" in t for t in page_texts(at))
    at = _open(ANNOTATION, "forbidden")
    assert "403" in page_texts(at, skip_header=False)


def test_d5c_human_grading_hides_the_llm_grade_until_saved() -> None:
    at = _open(GRADING)
    assert_no_exception(at)
    texts = page_texts(at)
    assert "Respuesta #A-0417 · Regresión logística" in texts
    assert "Muestra aleatoria · 12 de 30" in " ".join(texts)
    assert "Guarda tu calificación para ver la nota del LLM." in texts
    assert next(b for b in at.button if b.label == "Guardar y siguiente").disabled
    for group in at.get("button_group"):
        if group.label != "Cola":
            group.set_value("Cumple")
    at.run()
    assert "Tu nota: 3 de 3" in page_texts(at)
    at = click(at, "Guardar y siguiente")
    texts = page_texts(at)
    # Como la API, la cola ya no trae la respuesta calificada; la pantalla la sigue mostrando
    # con la nota del LLM hasta «Siguiente».
    assert "Respuesta #A-0417 · Regresión logística" in texts
    assert "Muestra aleatoria · 13 de 30" in " ".join(texts)
    assert "Coincide con tu nota" in texts
    assert any("Relaciona el umbral con el costo" in t for t in texts)
    assert "Siguiente" in [b.label for b in at.button]
    at = click(at, "Siguiente")
    assert any("No hay respuestas pendientes" in t for t in page_texts(at))


def test_d5c_empty_queue() -> None:
    at = _open(GRADING, "empty")
    assert any("No hay respuestas pendientes" in t for t in page_texts(at))


def test_d5e_matches_figma() -> None:
    at = _open(VIDEOS)
    assert_matches_figma(
        at,
        "D5e",
        # El triángulo de «reproducir» es un ícono de Material, no texto.
        accepted=("▶", "▶", "▶"),
    )


def test_d5e_videos_open_on_youtube_with_their_thumbnail() -> None:
    at = _open(VIDEOS)
    assert_no_exception(at)
    texts = " ".join(m.value for m in at.markdown)
    # Candidato en uso: portada y título enlazados a YouTube.
    assert "https://i.ytimg.com/vi/EXAMPLE0001/mqdefault.jpg" in texts
    assert (
        "[Regresión logística explicada paso a paso](https://www.youtube.com/watch?v=EXAMPLE0001)"
        in texts
    )
    # Video de respaldo: el título también abre el video.
    assert "(https://www.youtube.com/watch?v=EXAMPLE0004)" in texts


def test_d5e_use_this_video_and_pertinence() -> None:
    at = _open(VIDEOS)
    at = click(at, "Usar este")
    assert_no_exception(at)
    at.get("button_group")[0].set_value("No pertinente").run()
    assert_no_exception(at)
    assert not at.error


def test_d5e_add_backup_video_from_a_link() -> None:
    at = _open(VIDEOS)
    at.text_input(key="vid-link").set_value("https://www.youtube.com/watch?v=EXAMPLE0009").run()
    at = click(at, "Agregar")
    assert_no_exception(at)
    at.text_input(key="vid-link").set_value("no es un enlace").run()
    assert any("No reconocemos ese enlace" in t for t in page_texts(at))
    assert next(b for b in at.button if b.label == "Agregar").disabled


def test_d5f_quality_table_and_decision() -> None:
    at = _open(QUALITY)
    assert_no_exception(at)
    texts = page_texts(at)
    for expected in (
        "Calidad de los videos según los aprendices",
        "Recomendado",
        "En revisión",
        "Midiendo",
        "6 de 10 notas",
        "4,5 · 21 notas",
        "+11 pts",
        "T4 · Qué dicen los aprendices",
        "Audio bajo · 7",
        "Reemplazar por el video de respaldo",
        "Guardar decisión",
    ):
        assert any(expected in t for t in texts), expected
    assert next(b for b in at.button if b.label == "Guardar decisión").disabled
    at.radio[0].set_value("Retirar el video del tema").run()
    at = click(at, "Guardar decisión")
    assert_no_exception(at)
