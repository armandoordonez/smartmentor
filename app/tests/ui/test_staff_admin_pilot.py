"""AD4, AD4b (piloto), AD5 (cursos e inscripciones) y C4 (catálogo de prompts)."""

from apptest import page_texts
from staff_support import (
    assert_no_exception,
    click,
    staff_app,
    staff_text_reader,  # noqa: F401
)

from services.staff_prompts import PROMPTS

PILOT = "pages/admin/pilot.py"
COURSES = "pages/admin/courses_enrollments.py"
CATALOG = "pages/admin/prompt_catalog.py"


def test_ad4_shows_groups_seed_consents_and_readiness() -> None:
    at = staff_app("admin", page=PILOT)
    assert_no_exception(at)
    texts = page_texts(at)
    for expected in (
        "Configuración del piloto",
        "Ruta y fechas",
        "Asignación al azar",
        "12 aprendices",
        "Semilla del sorteo: 2026 · solo se puede volver a sortear antes de iniciar.",
        "2 pendientes",
        "22 de 24 aprendices aceptaron. Solo ellos entran al análisis (Ley 1581 de 2012).",
        "Verificado",
        "Guardar borrador",
        "Iniciar piloto",
    ):
        assert any(expected in t for t in texts), expected
    assert not next(b for b in at.button if b.label == "Iniciar piloto").disabled


def test_ad4_not_ready_blocks_starting() -> None:
    at = staff_app("admin", scenario="empty", page=PILOT)
    assert_no_exception(at)
    assert next(b for b in at.button if b.label == "Iniciar piloto").disabled
    assert any("Aún no se puede iniciar el piloto" in w.value for w in at.warning)
    assert any("Todavía no se sortearon los grupos" in t for t in page_texts(at))


def test_ad4_randomize_and_start() -> None:
    at = staff_app("admin", page=PILOT)
    at = click(at, "Volver a sortear")
    assert_no_exception(at)
    at = click(at, "Iniciar piloto")
    assert_no_exception(at)
    assert not at.error


def test_ad4_running_pilot_is_locked() -> None:
    at = staff_app("admin", scenario="running", page=PILOT)
    for label in ("Iniciar piloto", "Guardar borrador", "Volver a sortear"):
        assert next(b for b in at.button if b.label == label).disabled


def test_ad4b_fixed_path_preview_is_read_only() -> None:
    at = staff_app("admin", page=PILOT)
    at = click(at, "Vista previa de la ruta fija (solo lectura)")
    texts = page_texts(at)
    assert "Vista previa · ruta fija" in texts and "Solo lectura" in texts
    assert any("Incluido para todos los aprendices del grupo" in t for t in texts)
    assert any("Después de los 5 temas: evaluación final (80 % para el badge)." in t for t in texts)
    at = click(at, "Cerrar")
    assert "Vista previa · ruta fija" not in page_texts(at)


def test_ad4_forbidden() -> None:
    at = staff_app("instructor", scenario="forbidden", page=PILOT)
    assert "403" in page_texts(at, skip_header=False)


def test_ad5_lists_courses_and_enrollments() -> None:
    at = staff_app("admin", page=COURSES)
    assert_no_exception(at)
    texts = page_texts(at)
    for expected in (
        "Cursos, rutas e inscripciones",
        "Sin asignar",
        "Sin ruta",
        "Asignar instructor",
        "Personalizada",
        "Ruta fija",
        "Aceptado",
        "Pendiente",
        "Fundamentos de ML · 2026-2",
        "Durante el piloto, cambiar a un aprendiz de ruta o de grupo lo saca del análisis.",
    ):
        assert any(expected in t for t in texts), expected


def test_ad5_assign_an_instructor() -> None:
    at = staff_app("admin", page=COURSES)
    at = click(at, "Asignar instructor")
    at.selectbox(key="ce-owner").set_value(12).run()
    at = click(at, "Guardar instructor")
    assert_no_exception(at)
    assert not at.error


def test_ad5_withdraw_and_move_enrollment() -> None:
    at = staff_app("admin", page=COURSES)
    at = next(b for b in at.button if b.label == "Retirar").click().run()
    at.text_area(key="ce-note").set_value("Pidió retirarse").run()
    at = click(at, "Retirar")
    assert_no_exception(at)
    at = next(b for b in at.button if b.label == "Cambiar de ruta").click().run()
    at = click(at, "Mover")
    assert_no_exception(at)
    assert not at.error


def test_ad5_enroll_a_learner() -> None:
    at = staff_app("admin", page=COURSES)
    at = click(at, "Inscribir aprendiz")
    at = click(at, "Inscribir")
    assert_no_exception(at)
    assert not at.error


def test_ad5_empty_and_forbidden() -> None:
    at = staff_app("admin", scenario="empty", page=COURSES)
    texts = page_texts(at)
    assert "Todavía no hay cursos." in texts and "Todavía no hay inscripciones." in texts
    at = staff_app("instructor", scenario="forbidden", page=COURSES)
    assert "403" in page_texts(at, skip_header=False)


def test_c4_prompt_catalog() -> None:
    at = staff_app("admin", page=CATALOG)
    assert_no_exception(at)
    texts = page_texts(at)
    assert "Catálogo de prompts y versiones" in texts
    for prompt in PROMPTS:
        assert f"{prompt.prompt_id} v{prompt.version}" in texts
    assert len({p.prompt_id for p in PROMPTS}) == len(PROMPTS)
    at = click(at, "Volver al Log LLM")
    assert "Log LLM y costos" in page_texts(at)
