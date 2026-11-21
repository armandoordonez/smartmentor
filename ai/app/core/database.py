"""Async PostgreSQL engine for the ``smartmentor_ai`` user (ADR 0019)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.core.config import Settings


def create_engine(settings: Settings) -> AsyncEngine:
    """Engine with the session time zone fixed (fallback of the database default)."""
    return create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        connect_args={"server_settings": {"timezone": settings.app_timezone}},
    )
