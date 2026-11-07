"""Quién es la persona de la sesión: `GET /me`, rol activo y etiquetas visibles.

`GET /me` es la primera llamada tras el login (y dispara el primer ingreso, CU-34): devuelve los
roles de la base de datos, no los del token. El «rol activo» es solo de presentación (CU-35).
"""

from clients.models import Me, Role
from core.container import get_client
from core.labels import role_label
from core.session import AppSession, get_session


def load_me() -> Me:
    """Carga `GET /me` en la sesión (una vez) y fija el rol activo con `default_role`."""
    session = get_session()
    if session.me is None:
        session.me = get_client().get_me()
        session.active_role = session.me.default_role
    return session.me


def refresh_me() -> Me:
    """Vuelve a pedir `GET /me` (después de aceptar autorizaciones o de guardar el perfil)."""
    session = get_session()
    previous = session.active_role
    session.me = get_client().get_me()
    if previous is None or previous not in session.me.roles:
        session.active_role = session.me.default_role
    return session.me


def current_me() -> Me:
    """La persona de la sesión; lanza `RuntimeError` si todavía no entró (bug de la página)."""
    session = get_session()
    if session.me is None:
        msg = "No hay una sesión iniciada"
        raise RuntimeError(msg)
    return session.me


def active_role(session: AppSession | None = None) -> Role:
    current = session or get_session()
    me = current_me()
    return current.active_role or me.default_role


def label_for(role: Role, *, short: bool = False) -> str:
    """Etiqueta visible del rol: la de `GET /me` si llegó, y si no, la del glosario."""
    me = get_session().me
    api_labels = None
    if me is not None:
        api_labels = me.role_short_labels if short else me.role_labels
    return role_label(role, short=short, api_labels=api_labels)
