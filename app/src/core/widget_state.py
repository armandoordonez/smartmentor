"""Lo que la persona acaba de hacer con los widgets, para renovar el token sin perderlo (B-040).

La renovación del token (`st.login`) lleva el navegador a Keycloak y, al volver, Streamlit abre una
sesión nueva: los valores de los widgets y el clic que provocó la ejecución se pierden. Este módulo
sirve a `main.py` y a `core/renewal.py` para tres cosas:

- `current_interaction`: saber, al inicio de la ejecución, si la trajo una acción de la persona (un
  botón pulsado o un widget cambiado). Con acción, la renovación se aplaza mientras el token
  alcance para la petición en curso.
- `form_values` y `apply_form_values`: guardar los valores de los widgets con `key` de la página
  antes de redirigir y ponerlos de nuevo al volver, para que el formulario no quede vacío.
- `press`: repetir, al volver, el clic en el botón que la renovación interrumpió.

Streamlit no tiene API pública para esto: se leen piezas internas de `SessionState` de la versión
fija (1.67). Si cambian, las funciones fallan sin romper la página: ante la duda, se considera que
hay una acción (se aplaza la renovación), no se guarda nada y no se repite ningún clic.
"""

import logging
from dataclasses import dataclass
from typing import Any

import streamlit as st
from streamlit.errors import StreamlitAPIException
from streamlit.proto.WidgetStates_pb2 import WidgetState
from streamlit.runtime.scriptrunner import get_script_run_ctx

logger = logging.getLogger(__name__)

# Tipos de valor de `WidgetMetadata.value_type` (protocolo de Streamlit).
_TRIGGER_TYPES = frozenset(
    {"trigger_value", "string_trigger_value", "chat_input_value", "json_trigger_value"}
)
# Valores que se pueden volver a poner con `st.session_state[key]`: casillas, textos, listas de
# selección, números y fechas. Quedan fuera los botones, los archivos y las tablas editables.
_DRAFT_TYPES = frozenset(
    {
        "bool_value",
        "int_value",
        "double_value",
        "string_value",
        "int_array_value",
        "double_array_value",
        "string_array_value",
    }
)
_DRAFT_VALUE_TYPES = (str, int, float, bool, list, tuple)


@dataclass(frozen=True)
class PressedButton:
    """Botón con `key` y sin callback que se pulsó en esta ejecución."""

    widget_id: str
    key: str


@dataclass(frozen=True)
class Interaction:
    """Lo que trajo la ejecución actual desde el navegador."""

    pending: bool
    """True si se pulsó un botón o cambió un widget (la persona espera un resultado)."""
    pressed: PressedButton | None = None
    """El único botón pulsado, si se puede repetir tal cual después de renovar."""


NO_INTERACTION = Interaction(pending=False)


def _session_state() -> Any | None:
    """El `SessionState` interno de la ejecución en curso, o None fuera de Streamlit."""
    ctx = get_script_run_ctx(suppress_warning=True)
    if ctx is None:
        return None
    return getattr(ctx.session_state, "_state", None)


def current_interaction() -> Interaction:
    """Botones pulsados y widgets cambiados que trajo esta ejecución (al inicio del guion).

    Una ejecución por `st.rerun`, `st.switch_page` o la carga de la página no trae acción.
    """
    state = _session_state()
    if state is None:
        return NO_INTERACTION
    try:
        return _read_interaction(state)
    except Exception:  # piezas internas de Streamlit: ante la duda, hay acción
        logger.warning("No se pudo leer la interacción de los widgets", exc_info=True)
        return Interaction(pending=True)


def _read_interaction(state: Any) -> Interaction:
    widgets = state._new_widget_state
    keys: dict[str, str] = state._key_id_mapper.id_key_mapping
    pending = False
    pressed: list[PressedButton | None] = []
    for widget_id in list(widgets.states):
        metadata = widgets.widget_metadata.get(widget_id)
        if metadata is None:
            pending = True  # un widget desconocido: se trata como acción
            continue
        if metadata.value_type in _TRIGGER_TYPES:
            if widgets.get(widget_id):
                pending = True
                pressed.append(_replayable(widget_id, keys.get(widget_id), metadata))
        elif state._widget_changed(widget_id):
            pending = True
    only = pressed[0] if len(pressed) == 1 else None
    return Interaction(pending=pending, pressed=only)


def _replayable(widget_id: str, key: str | None, metadata: Any) -> PressedButton | None:
    """Solo un `st.button` con `key` y sin callback se puede repetir pulsándolo de nuevo."""
    if key is None or metadata.value_type != "trigger_value":
        return None
    if getattr(metadata, "callback", None) is not None:
        return None
    if getattr(metadata, "callbacks", None):
        return None
    return PressedButton(widget_id=widget_id, key=key)


def form_values() -> dict[str, Any]:
    """Valores de los widgets con `key` que muestra la página (borrador para después de renovar).

    Si la ejecución trae valores del navegador, son los de la página que la persona ve; si no, los
    de la última ejecución completa (Streamlit borra al terminar los de los widgets que ya no se
    dibujan).
    """
    state = _session_state()
    if state is None:
        return {}
    try:
        return _read_form_values(state)
    except Exception:  # piezas internas de Streamlit: sin borrador
        logger.warning("No se pudieron leer los valores de los widgets", exc_info=True)
        return {}


def _read_form_values(state: Any) -> dict[str, Any]:
    widgets = state._new_widget_state
    keys: dict[str, str] = state._key_id_mapper.id_key_mapping
    shown = set(widgets.states) or {wid for wid in state._old_state if wid in keys}
    values: dict[str, Any] = {}
    for widget_id in sorted(shown):
        key = keys.get(widget_id)
        metadata = widgets.widget_metadata.get(widget_id)
        if key is None or metadata is None or metadata.value_type not in _DRAFT_TYPES:
            continue
        try:
            value = st.session_state[key]
        except KeyError:
            continue
        if value is None or isinstance(value, _DRAFT_VALUE_TYPES):
            values[key] = list(value) if isinstance(value, tuple) else value
    return values


def apply_form_values(values: dict[str, Any]) -> None:
    """Pone el borrador en `st.session_state` antes de que la página dibuje sus widgets."""
    for key, value in values.items():
        try:
            st.session_state[key] = value
        except StreamlitAPIException:
            logger.info("No se pudo restaurar el widget %s", key)


def seed_defaults(defaults: dict[str, Any]) -> None:
    """Valor inicial de widgets con `key` por `st.session_state`, sin pisar lo que ya haya.

    Es la forma de dar un valor inicial a un widget que puede restaurarse (`apply_form_values`):
    el widget se crea sin `value=`/`index=`/`default=` y así Streamlit no avisa de que recibe el
    valor por dos vías (B-053). Un borrador restaurado o lo que la persona ya escribió se respeta.
    """
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def press(widget_id: str) -> bool:
    """Marca el botón como pulsado en esta ejecución, como si llegara el clic del navegador.

    Si el botón no se dibuja en esta ejecución, Streamlit descarta la marca al terminar.
    """
    state = _session_state()
    if state is None:
        return False
    try:
        state._new_widget_state.set_widget_from_proto(WidgetState(id=widget_id, trigger_value=True))
    except Exception:  # piezas internas de Streamlit: no se repite el clic
        logger.warning("No se pudo repetir el clic", exc_info=True)
        return False
    return True
