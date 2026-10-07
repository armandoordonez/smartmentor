"""Conexión a PostgreSQL con SQLAlchemy asíncrono."""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import event, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session, SessionTransaction

from app.core.config import Settings

AUDIT_USER_KEY = "audit_user_id"


def create_engine(settings: Settings) -> AsyncEngine:
    """Crea el engine fijando la zona horaria de la sesión (respaldo del valor de la base)."""
    return create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        connect_args={"server_settings": {"timezone": settings.app_timezone}},
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


@event.listens_for(Session, "after_begin")
def _propagate_audit_user(
    session: Session, transaction: SessionTransaction, connection: Connection
) -> None:
    """Pasa el usuario que actúa a la base en cada transacción (lo lee audit_row_change())."""
    user_id = session.info.get(AUDIT_USER_KEY)
    if user_id is not None:
        connection.execute(
            text("SELECT set_config('smartmentor.current_user_id', :user_id, true)"),
            {"user_id": user_id},
        )


async def apply_audit_user(session: AsyncSession, user_id: str) -> None:
    """Fija el usuario que actúa para la auditoría, desde ya y en las transacciones siguientes.

    Se guarda en la sesión (lo lee el evento after_begin de cada transacción nueva) y se aplica a
    la transacción en curso, si la hay, para no auditar con un valor anterior.
    """
    session.sync_session.info[AUDIT_USER_KEY] = user_id
    await session.execute(
        text("SELECT set_config('smartmentor.current_user_id', :user_id, true)"),
        {"user_id": user_id},
    )


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Una sesión por petición. Si la petición falla antes del commit, se hace rollback."""
    factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with factory() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]
