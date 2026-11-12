"""Ayudas para probar páginas con `AppTest`: entrar con un escenario y leer los textos visibles."""

import re
from collections.abc import Iterator
from typing import Any

from streamlit.testing.v1 import AppTest
from streamlit.testing.v1.element_tree import Block
from support import SRC_DIR

from clients.fixtures import SCENARIOS_BY_KEY, FixturesClient
from core.session import AppSession

MAIN = str(SRC_DIR / "main.py")


def new_app(timeout: float = 30) -> AppTest:
    return AppTest.from_file(MAIN, default_timeout=timeout)


def signed_in(scenario: str = "learner", *, page: str | None = None) -> AppTest:
    """App con la sesión de un escenario ya iniciada (como si hubiera elegido el rol en A1)."""
    at = new_app()
    client = FixturesClient(scenario)
    at.session_state["app_session"] = AppSession(
        me=client.get_me(),
        active_role=SCENARIOS_BY_KEY[scenario].role,
        scenario_key=scenario,
        fixtures_client=client,
    )
    at.run()
    if page is not None:
        at.switch_page(page)
        at.run()
    return at


def session_of(at: AppTest) -> AppSession:
    session = at.session_state["app_session"]
    assert isinstance(session, AppSession)
    return session


def button(at: AppTest, label: str) -> Any:
    """Botón por su texto; falla con un mensaje claro si no existe."""
    for candidate in at.button:
        if candidate.label == label:
            return candidate
    labels = [b.label for b in at.button]
    msg = f"No hay un botón «{label}». Botones: {labels}"
    raise AssertionError(msg)


# --- Textos visibles, en el orden de la pantalla -------------------------------------------------

_BADGE = re.compile(r":[a-z]+-badge\[([^\]]*)\]")
_ICON = re.compile(r":material/[a-z_0-9]+:")
_COLOR = re.compile(r":[a-z]+\[([^\[\]]*)\]")
_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_LINK = re.compile(r"\[((?:\\.|[^\]\\])*)\]\([^)]*\)")
_ESCAPED = re.compile(r"\\(.)")


def plain(text: str) -> str:
    """Quita el Markdown de Streamlit (colores, badges, íconos, negritas, imágenes y enlaces) y
    normaliza espacios. Un enlace queda como su texto, que es lo que se lee en pantalla."""
    text = _IMAGE.sub("", text)
    text = _LINK.sub(lambda m: _ESCAPED.sub(r"\1", m.group(1)), text)
    text = _BADGE.sub(r"\1", text)
    text = _ICON.sub("", text)
    previous = None
    while previous != text:
        previous = text
        text = _COLOR.sub(r"\1", text)
    text = re.sub(r"^#+\s*", "", text.strip())
    text = text.replace("**", "").replace("`", "")
    return re.sub(r"\s+", " ", text).strip()


class _Label:
    """Texto de un contenedor con botón visible (popover)."""

    type = "label"

    def __init__(self, text: str) -> None:
        self.value = text


def _element_texts(element: Any) -> list[str]:
    kind = element.type
    if kind == "label":
        return [element.value]
    if kind in {"markdown", "caption", "title", "header", "subheader", "text"}:
        return [element.value]
    if kind in {"button", "page_link", "link_button"}:
        return [element.label]
    if kind == "checkbox":
        return [element.label]
    if kind in {"text_area", "text_input"}:
        return [element.label, element.value]
    if kind == "selectbox":
        shown = element.options[element.index] if element.index is not None else ""
        return [element.label, shown]
    if kind in {"radio", "segmented_control", "pills", "button_group"}:
        return [element.label, *[str(option) for option in element.options]]
    return []


def _walk(block: Block) -> Iterator[Any]:
    for child in block.children.values():
        if isinstance(child, Block):
            if child.type == "popover":
                yield _Label(child.proto.popover.label)
            yield from _walk(child)
        else:
            yield child


def _blocks(block: Block) -> Iterator[Any]:
    for child in block.children.values():
        yield child
        if isinstance(child, Block):
            yield from _blocks(child)


def _role_container(at: AppTest) -> Block | None:
    """Contenedor `role-<rol>` de `main.py` (barra superior + página); None sin sesión."""
    for child in at.main.children.values():
        if isinstance(child, Block):
            first = next(iter(child.children.values()), None)
            if isinstance(first, Block) and any(
                getattr(e, "type", "") == "popover" for e in _blocks(first)
            ):
                return child
    return None


def page_texts(at: AppTest, *, skip_header: bool = True) -> list[str]:
    """Textos de la página en orden. Con `skip_header` se omite la barra superior."""
    container = _role_container(at)
    elements: list[Any] = []
    if container is None:
        elements = list(_walk(at.main))
    else:
        children = list(container.children.values())
        if skip_header:
            children = children[1:]
        for child in children:
            elements.extend(_walk(child) if isinstance(child, Block) else [child])
    texts: list[str] = []
    for element in elements:
        texts.extend(plain(text) for text in _element_texts(element) if text)
    return [text for text in texts if text]


def header_texts(at: AppTest) -> list[str]:
    container = _role_container(at)
    assert container is not None, "No hay sesión iniciada"
    header = next(iter(container.children.values()))
    assert isinstance(header, Block)
    texts: list[str] = []
    for element in _walk(header):
        texts.extend(plain(text) for text in _element_texts(element) if text)
    return [text for text in texts if text]
