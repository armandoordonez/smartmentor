"""Volver a la misma página, con el mismo estado, después de renovar el token (B-030).

La renovación silenciosa (`auth.renew_silently_if_possible`) repite `st.login`: el navegador va a
Keycloak y el callback de Streamlit (`/oauth2callback`) **siempre** redirige a la raíz (`/`). La
página se carga de nuevo, así que Streamlit abre una sesión nueva y `st.session_state` empieza
vacío: la persona caía en su inicio (el catálogo) y perdía el tema, el intento y lo respondido.
Streamlit no permite pasar datos por esa redirección (ni una URL de regreso ni parámetros).

Por eso, justo antes de `st.login`, se **aparca** en memoria del servidor la página actual y la
sesión de la app (`AppSession`: inscripción, tema, intento, hoja de respuestas, claves de
idempotencia), con la identidad de la persona (`sub` del token) como llave. Al volver, la primera
ejecución de la sesión nueva con esa misma identidad la recupera (una sola vez y con vencimiento)
y `main.py` cambia a esa página.

Límites:
- Es memoria del proceso: con varias réplicas de la app detrás de un balanceador sin afinidad, la
  sesión nueva puede caer en otra réplica; entonces solo se pierde el regreso (comportamiento
  anterior: el inicio del rol).
- Una entrada por persona: si dos pestañas renuevan a la vez, la última gana y la otra vuelve al
  inicio.
- Solo la recupera una sesión **nueva** (sin `GET /me` cargado): una pestaña ya abierta de la misma
  persona no se la lleva.
- Un texto que la persona escribía y que el navegador aún no había enviado (sin salir del campo)
  se pierde: el servidor nunca lo recibió.

B-040: también se aparcan los valores de los widgets con `key` de la página (`drafts`, que se ponen
de nuevo al volver para que el formulario no quede vacío) y, si la renovación interrumpió un clic
antes de que la página corriera, ese botón (`click`), que `main.py` repite al volver. Repetirlo no
duplica nada: la página no llegó a ejecutarse con el token vencido, el clic se aparca una sola vez
y las entregas llevan la clave de idempotencia de la sesión aparcada.
"""

import threading
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from core.navigation import page_for_url_path
from core.session import AppSession, PendingClick
from core.widget_state import PressedButton

PARK_TTL_SECONDS = 600


@dataclass(frozen=True)
class Parked:
    """Lo que se aparca antes de `st.login`: la página (archivo) y la sesión de la app."""

    page: str | None
    session: AppSession
    expires_at: float
    drafts: dict[str, Any] = field(default_factory=dict)
    click: PressedButton | None = None


class RenewalStore:
    """Sesiones aparcadas por persona, en memoria del proceso, de un solo uso y con vencimiento."""

    def __init__(self, ttl: float = PARK_TTL_SECONDS) -> None:
        self._ttl = ttl
        self._items: dict[str, Parked] = {}
        self._lock = threading.Lock()

    def park(
        self,
        user_key: str,
        *,
        page: str | None,
        session: AppSession,
        drafts: dict[str, Any] | None = None,
        click: PressedButton | None = None,
        now: float | None = None,
    ) -> None:
        current = time.monotonic() if now is None else now
        with self._lock:
            self._purge(current)
            self._items[user_key] = Parked(
                page, session, current + self._ttl, dict(drafts or {}), click
            )

    def claim(self, user_key: str, *, now: float | None = None) -> Parked | None:
        """La sesión aparcada de la persona, si sigue vigente; se borra al leerla."""
        current = time.monotonic() if now is None else now
        with self._lock:
            self._purge(current)
            return self._items.pop(user_key, None)

    def __len__(self) -> int:
        with self._lock:
            return len(self._items)

    def _purge(self, now: float) -> None:
        expired = [key for key, item in self._items.items() if item.expires_at <= now]
        for key in expired:
            del self._items[key]


STORE = RenewalStore()


def page_from_url(url: str | None) -> str | None:
    """Archivo de la página a partir de la URL del navegador (`st.context.url`), si es una."""
    if not url:
        return None
    segments = [part for part in urlparse(url).path.split("/") if part]
    return page_for_url_path(segments[-1]) if segments else None


def park(
    store: RenewalStore,
    user_key: str | None,
    page: str | None,
    session: AppSession,
    *,
    drafts: dict[str, Any] | None = None,
    click: PressedButton | None = None,
) -> bool:
    """Aparca la sesión antes de redirigir; sin identidad no se aparca (no habría cómo volver).

    `click` solo se pasa si la página no llegó a correr en esta ejecución (B-040).
    """
    if not user_key:
        return False
    store.park(user_key, page=page, session=session, drafts=drafts, click=click)
    return True


def restore(store: RenewalStore, user_key: str | None, current: AppSession) -> AppSession | None:
    """La sesión aparcada para una sesión nueva de la misma persona, con la página a la que vuelve,
    el borrador de sus widgets y el clic que hay que repetir (B-040).

    Devuelve `None` si no hay nada aparcado o si `current` ya tiene a la persona cargada (es una
    pestaña que siguió abierta, no la que volvió de Keycloak).
    """
    if not user_key or current.me is not None:
        return None
    parked = store.claim(user_key)
    if parked is None:
        return None
    session = parked.session
    session.resume_page = parked.page
    session.resume_drafts = dict(parked.drafts)
    session.resume_click = (
        PendingClick(page=parked.page, widget_id=parked.click.widget_id, key=parked.click.key)
        if parked.click is not None and parked.page is not None
        else None
    )
    return session
