"""Eventos de uso del aprendiz (`POST /me/events`) para el tiempo en tarea (m27) y la H2.

Cada pantalla medida abre una *visita* (ruta E5, tema E6, quiz E6b/E6c, final E8). La visita manda
su evento de vista una sola vez, aunque Streamlit vuelva a ejecutar la página, y se cierra con un
evento que lleva `payload.seconds` (el tramo de tiempo en esa pantalla):

- al entregar el quiz o la final (`quiz.submit`, `final.submit`);
- al pasar a otra página (`main.py` llama a `close_views_outside` en cada ejecución).

Los tramos no se solapan, así que sumar `payload.seconds` por `topic_id` o por `enrollment_id` da
los minutos por tema y por ruta. Un tramo se recorta a `MAX_SEGMENT_SECONDS` (`capped: true`): la
interfaz no sabe si la persona dejó la pestaña abierta sin estudiar.

**Un fallo al enviar nunca rompe ni frena la pantalla**: la llamada es corta (`EVENTS_TIMEOUT`), el
error va al registro (sin datos personales) y no se muestra. Si la API no respondía (503), el lote
se guarda en la sesión y sale con el siguiente envío (el contrato admite hasta 100 por lote).
"""

import logging
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from typing import Any

from clients.base import ApiError, SmartMentorClient
from clients.models_learner import MAX_EVENTS_PER_BATCH, InteractionEvent
from core.learner_state import OpenView, UsageLog
from core.session import get_session

logger = logging.getLogger(__name__)

MAX_SEGMENT_SECONDS = 3600

ClientFactory = Callable[[], SmartMentorClient]


def _log() -> UsageLog:
    return get_session().learner.usage


def _now() -> datetime:
    return datetime.now(UTC)


def build_event(
    enrollment_id: int,
    event_type: str,
    *,
    topic_id: int | None = None,
    payload: dict[str, Any] | None = None,
    occurred_at: datetime | None = None,
) -> InteractionEvent:
    return InteractionEvent(
        enrollment_id=enrollment_id,
        event_type=event_type,
        topic_id=topic_id,
        occurred_at=occurred_at or _now(),
        payload=payload,
    )


def send(client: SmartMentorClient, events: Sequence[InteractionEvent]) -> None:
    """Envía los eventos (con los pendientes) en un solo lote; nunca lanza."""
    log = _log()
    batch = [*log.pending, *events][-MAX_EVENTS_PER_BATCH:]
    log.pending = []
    if not batch:
        return
    try:
        client.record_events(batch)
    except ApiError as error:
        if error.status == 503:  # sin conexión: se reintenta con el próximo envío
            log.pending = batch
        logger.warning(
            "No se enviaron %d eventos de uso: %s %s (request_id=%s)",
            len(batch),
            error.status,
            error.code,
            error.request_id,
        )
    except Exception:  # la telemetría nunca rompe la pantalla
        logger.exception("Fallo inesperado al enviar %d eventos de uso", len(batch))


def record_once(
    client: SmartMentorClient, marker: str, build: Callable[[], Sequence[InteractionEvent]]
) -> None:
    """Envía los eventos de `build` solo la primera vez que se ve `marker` en la sesión."""
    try:
        log = _log()
        if marker in log.sent:
            return
        log.sent.add(marker)
        events = build()
    except Exception:
        logger.exception("No se pudo preparar el evento de uso %s", marker)
        return
    send(client, events)


def open_view(
    client: SmartMentorClient,
    key: str,
    *,
    enrollment_id: int,
    close_type: str,
    event_type: str | None = None,
    topic_id: int | None = None,
    payload: dict[str, Any] | None = None,
    extra: Callable[[datetime], Sequence[InteractionEvent]] | None = None,
) -> None:
    """Empieza una visita a `key` (pantalla + entidad) si no hay una abierta.

    Manda `event_type` (si se da) y los eventos de `extra` una sola vez por visita: las
    reejecuciones de la misma página no repiten nada.
    """
    try:
        log = _log()
        if key in log.open_views:
            return
        now = _now()
        base = dict(payload or {})
        log.open_views[key] = OpenView(
            page=log.current_page or "",
            close_type=close_type,
            enrollment_id=enrollment_id,
            topic_id=topic_id,
            payload=base,
            started_at=now,
        )
        events: list[InteractionEvent] = []
        if event_type is not None:
            events.append(
                build_event(
                    enrollment_id, event_type, topic_id=topic_id, payload=base, occurred_at=now
                )
            )
        if extra is not None:
            events.extend(extra(now))
    except Exception:
        logger.exception("No se pudo abrir la visita %s", key)
        return
    if events:
        send(client, events)


def _closing(view: OpenView, event_type: str, payload: dict[str, Any] | None) -> InteractionEvent:
    now = _now()
    elapsed = max(round((now - view.started_at).total_seconds()), 0)
    body: dict[str, Any] = {
        **view.payload,
        **(payload or {}),
        "seconds": min(elapsed, MAX_SEGMENT_SECONDS),
        "started_at": view.started_at.isoformat(),
    }
    if elapsed > MAX_SEGMENT_SECONDS:
        body["capped"] = True
    return build_event(
        view.enrollment_id, event_type, topic_id=view.topic_id, payload=body, occurred_at=now
    )


def close_view(
    client: SmartMentorClient,
    key: str,
    *,
    event_type: str | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    """Cierra la visita `key` con su evento (o `event_type`) y los `seconds` transcurridos."""
    try:
        view = _log().open_views.pop(key, None)
        if view is None:
            return
        event = _closing(view, event_type or view.close_type, payload)
    except Exception:
        logger.exception("No se pudo cerrar la visita %s", key)
        return
    send(client, [event])


def close_views_outside(page: str, client_factory: ClientFactory) -> None:
    """Marca `page` como la actual y cierra las visitas abiertas en otra página (ya salió)."""
    try:
        log = _log()
        log.current_page = page
        stale = [key for key, view in log.open_views.items() if view.page != page]
        if not stale:
            return
        views = [log.open_views.pop(key) for key in stale]
        events = [_closing(view, view.close_type, None) for view in views]
        client = client_factory()
    except Exception:
        logger.exception("No se pudieron cerrar las visitas al cambiar a %s", page)
        return
    send(client, events)
