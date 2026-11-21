"""AD1 a AD3: usuarios y roles, log del LLM y métricas globales."""

from apptest import page_texts
from staff_support import (
    assert_matches_figma,
    assert_no_exception,
    click,
    staff_app,
    staff_text_reader,  # noqa: F401
)

from core.styles import STYLES_DIR

USERS = "pages/admin/users.py"
LOGS = "pages/admin/llm_logs.py"
METRICS = "pages/admin/metrics.py"


def test_admin_home_is_users_and_roles() -> None:
    at = staff_app("admin")
    assert_no_exception(at)
    assert "Usuarios y roles" in page_texts(at)


def test_ad1_matches_figma() -> None:
    at = staff_app("admin", page=USERS)
    assert_matches_figma(
        at,
        "AD1",
        # Las acciones de cada fila son botones separados («Cambiar rol» y «Desactivar»). Los
        # correos de Figma usan @universidad.edu.co; los datos de ejemplo usan un dominio neutro.
        accepted=(
            "elena.ramirez@universidad.edu.co",
            "Cambiar rol · Desactivar",
            "laura.martinez@universidad.edu.co",
            "Cambiar rol · Desactivar",
            "julian.perez@universidad.edu.co",
            "admin@universidad.edu.co",
        ),
    )


def test_ad1_instructor_gets_403() -> None:
    at = staff_app("instructor", scenario="forbidden", page=USERS)
    assert "403" in page_texts(at, skip_header=False)


def test_ad1_assign_several_roles() -> None:
    at = staff_app("admin", page=USERS)
    cambiar = [b for b in at.button if b.label == "Cambiar rol"]
    at = cambiar[0].click().run()
    assert any("Roles de" in t for t in page_texts(at))
    roles = at.multiselect[0]
    roles.set_value(["learner", "instructor"]).run()
    at = click(at, "Guardar roles")
    assert_no_exception(at)
    assert not at.error


def test_ad1_last_admin_is_refused_by_the_api() -> None:
    at = staff_app("admin", scenario="last_admin", page=USERS)
    at = next(b for b in at.button if b.label == "Cambiar rol").click().run()
    at = click(at, "Guardar roles")
    assert any("al menos un administrador" in e.value for e in at.error)
    at = next(b for b in at.button if b.label == "Desactivar").click().run()
    assert any("al menos un administrador" in e.value for e in at.error)


def test_ad1_the_signed_in_admin_cannot_edit_themselves() -> None:
    at = staff_app("admin", page=USERS)
    assert "Solo otro admin puede editar" in page_texts(at)


def test_ad1_create_user() -> None:
    at = staff_app("admin", page=USERS)
    at = click(at, "Crear usuario")
    assert next(b for b in at.button if b.label == "Crear").disabled
    at.text_input(key="u-new-name").set_value("Nuevo").run()
    at.text_input(key="u-new-email").set_value("nuevo@organizacion.example").run()
    at = click(at, "Crear")
    assert_no_exception(at)
    assert not at.error


def test_ad1_empty_and_error() -> None:
    at = staff_app("admin", scenario="empty", page=USERS)
    assert_no_exception(at)
    at = staff_app("admin", scenario="error", page=USERS)
    assert at.error


def test_ad2_matches_figma() -> None:
    at = staff_app("admin", page=LOGS)
    assert_matches_figma(
        at,
        "AD2",
        # Los KPI son `st.metric` (AppTest no los lee; se prueban aparte).
        ignore=(
            "1.284",
            "Llamadas",
            "US$ 4,12",
            "Costo total",
            "11,8 s",
            "Latencia p95",
            "0,9 %",
            "JSON inválido",
        ),
    )


def test_ad2_kpis() -> None:
    at = staff_app("admin", page=LOGS)
    values = {m.label: m.value for m in at.metric}
    assert values == {
        "Llamadas": "1.284",
        "Costo total": "US$ 4,12",
        "Latencia p95": "11,8 s",
        "JSON inválido": "0,9 %",
    }


def test_ad2_catalog_link_is_a_text_button_in_blue_underlined() -> None:
    """V-017: el enlace al catálogo es un botón de texto (`tertiary`) que el CSS pinta azul y
    subrayado, como en Figma."""
    at = staff_app("admin", page=LOGS)
    link = at.button(key="ll-catalog")
    assert link.label == "Ver el catálogo de prompts y versiones (documentación del equipo)"
    assert link.proto.type == "tertiary"
    css = (STYLES_DIR / "components" / "llm_logs.css").read_text(encoding="utf-8")
    assert ".st-key-ll-catalog button" in css
    assert "text-decoration: underline" in css
    assert "color: var(--learner-text)" in css


def test_ad2_empty_forbidden() -> None:
    at = staff_app("admin", scenario="empty", page=LOGS)
    assert any("Todavía no hay llamadas" in t for t in page_texts(at))
    at = staff_app("admin", scenario="forbidden", page=LOGS)
    assert "403" in page_texts(at, skip_header=False)


def test_ad3_matches_figma() -> None:
    at = staff_app("admin", page=METRICS)
    # Diferencias aceptadas (F-013): el piloto se define fuera de la app, así que no hay botón
    # «Configurar piloto» y la insignia dice solo «Valores de ejemplo».
    assert_matches_figma(
        at,
        "AD3",
        accepted=("Valores de ejemplo hasta que corra el piloto", "Configurar piloto"),
    )
    assert "Valores de ejemplo" in page_texts(at)


def test_ad3_empty() -> None:
    at = staff_app("admin", scenario="empty", page=METRICS)
    assert_no_exception(at)
    assert any("Todavía no hay métricas" in t for t in page_texts(at))
