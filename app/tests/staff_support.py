"""Ayudas de las pruebas de las páginas del instructor y del administrador."""

import apptest
import pytest
from apptest import new_app, page_texts
from figma_compare import figma_texts, missing_in_order
from streamlit.testing.v1 import AppTest

from clients.fixtures import SCENARIOS_BY_KEY, FixturesClient
from core.session import AppSession

_original_element_texts = apptest._element_texts


def _with_status_boxes(element: object) -> list[str]:
    """Agrega a la lectura de textos los avisos (`st.warning`, `st.info`, `st.error`...)."""
    if getattr(element, "type", "") in {"warning", "info", "error", "success"}:
        return [str(getattr(element, "value", ""))]
    result: list[str] = _original_element_texts(element)
    return result


@pytest.fixture(autouse=True)
def staff_text_reader(monkeypatch: pytest.MonkeyPatch) -> None:
    """Las pruebas de estas páginas leen también los avisos; las demás no se ven afectadas."""
    monkeypatch.setattr(apptest, "_element_texts", _with_status_boxes)


def staff_app(
    role: str = "instructor", scenario: str = "default", *, page: str | None = None
) -> AppTest:
    """App con la sesión de un instructor o administrador y un escenario de datos de `staff/`."""
    at = new_app()
    client = FixturesClient(role)
    client.staff_scenario = scenario
    at.session_state["app_session"] = AppSession(
        me=client.get_me(),
        active_role=SCENARIOS_BY_KEY[role].role,
        scenario_key=role,
        fixtures_client=client,
    )
    at.run()
    if page is not None:
        at.switch_page(page)
        at.run()
    return at


def with_state(at: AppTest, **values: int | str | None) -> AppTest:
    """Fija el curso, la ruta o la inscripción elegidos, como si se vinieran de otra página."""
    from core.staff_state import StaffState

    at.session_state["staff_state"] = StaffState(**values)  # type: ignore[arg-type]
    return at


def assert_no_exception(at: AppTest) -> None:
    assert [e.value for e in at.exception] == []


def assert_matches_figma(
    at: AppTest,
    screen: str,
    *,
    accepted: tuple[str, ...] = (),
    ignore: tuple[str, ...] = (),
) -> None:
    """Todos los textos del frame aparecen en orden, salvo los aceptados (con su motivo).

    `ignore` quita del frame textos que el lector de `AppTest` no ve (las métricas) o que son tan
    cortos que coincidirían con cualquier cosa (un «6» está dentro de «2026»).
    """
    assert_no_exception(at)
    expected = [text for text in figma_texts(screen) if text not in ignore]
    missing = missing_in_order(expected, page_texts(at))
    assert missing == list(accepted), f"{screen}: faltan o desordenados {missing}"


def click(at: AppTest, label: str) -> AppTest:
    """Pulsa el botón con ese texto y ejecuta."""
    for candidate in at.button:
        if candidate.label == label:
            return candidate.click().run()
    labels = [b.label for b in at.button]
    msg = f"No hay un botón «{label}». Botones: {labels}"
    raise AssertionError(msg)
