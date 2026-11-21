"""El indicador «Cargando…» no se anida y no falla sin contexto de Streamlit."""

from contextlib import contextmanager
from typing import Any

import httpx
import pytest
import respx
from streamlit.testing.v1 import AppTest

from clients.api import ApiClient
from components import loading


def test_does_nothing_without_streamlit_context(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("no debe dibujar sin contexto")

    monkeypatch.setattr(loading.st, "spinner", fail)
    with loading.loading_indicator(), loading.loading_indicator():
        pass


def test_nested_calls_draw_a_single_spinner(monkeypatch: pytest.MonkeyPatch) -> None:
    texts: list[str] = []

    @contextmanager
    def fake_spinner(text: str) -> Any:
        texts.append(text)
        yield

    monkeypatch.setattr(loading, "get_script_run_ctx", lambda **_kwargs: object())
    monkeypatch.setattr(loading.st, "spinner", fake_spinner)
    with loading.loading_indicator(), loading.loading_indicator():
        pass
    assert texts == ["Cargando…"]
    with loading.loading_indicator():  # al terminar el primero, el siguiente sí dibuja
        pass
    assert texts == ["Cargando…", "Cargando…"]


def test_depth_is_released_after_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(loading, "get_script_run_ctx", lambda **_kwargs: object())
    monkeypatch.setattr(loading.st, "spinner", lambda _text: _noop())
    with pytest.raises(ValueError, match="boom"), loading.loading_indicator():
        raise ValueError("boom")
    assert loading._depth.get() == 0


@contextmanager
def _noop() -> Any:
    yield


@respx.mock
def test_api_client_works_without_streamlit_context() -> None:
    respx.get("http://api.test/api/v1/me/badges").mock(return_value=httpx.Response(200, json=[]))
    client = ApiClient(
        "http://api.test", lambda: "token", http=httpx.Client(base_url="http://api.test")
    )
    assert client.list_badges() == []


def _slow_script() -> None:
    import streamlit as st

    from components.loading import loading_indicator

    with loading_indicator(), loading_indicator():
        st.write("hecho")


def test_apptest_runs_inside_a_script() -> None:
    app = AppTest.from_function(_slow_script).run()
    assert not app.exception
    assert app.markdown[0].value == "hecho"


def _wait_mode_script() -> None:
    """Dibuja tres peticiones: normal, en modo espera y tras consumir el trabajo."""
    from contextlib import contextmanager

    import streamlit as st

    from components.loading import loading_indicator
    from core import polling
    from core.session import get_session

    drawn: list[str] = []

    @contextmanager
    def fake_spinner(text: str):  # type: ignore[no-untyped-def]
        drawn.append(text)
        yield

    original = st.spinner
    st.spinner = fake_spinner  # type: ignore[assignment]
    try:
        learner = get_session().learner
        with loading_indicator():
            pass
        learner.diagnostic_job_id = "job-1"
        polling.enter_wait_mode("job-1")
        with loading_indicator():
            pass
        learner.diagnostic_job_id = None  # la página consumió el trabajo
        with loading_indicator():
            pass
        polling.enter_wait_mode("job-1")
        learner.quiz_job_id = "job-1"
        polling.leave_wait_mode()  # al navegar a otra pantalla el spinner vuelve
        with loading_indicator():
            pass
    finally:
        st.spinner = original  # type: ignore[assignment]
    st.session_state["drawn"] = drawn


def test_wait_mode_silences_the_spinner_only_while_the_job_is_awaited() -> None:
    app = AppTest.from_function(_wait_mode_script).run()
    assert not app.exception
    # Dibuja la 1.ª (sin espera), calla la 2.ª (espera activa), dibuja la 3.ª (trabajo consumido)
    # y la 4.ª (se salió del modo espera).
    assert app.session_state["drawn"] == ["Cargando…"] * 3


def test_polling_registers_the_wait_mode_probe() -> None:
    from core import polling

    assert loading._quiet_probe is polling.in_wait_mode  # lo registra al importarse
