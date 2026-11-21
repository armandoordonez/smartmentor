"""``ai_generation_cache`` on PostgreSQL (``task`` holds the prompt id)."""

from __future__ import annotations

import json

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.ports.cache import CachedGeneration


class PostgresGenerationCache:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def get(self, key: str) -> CachedGeneration | None:
        async with self._engine.connect() as conn:
            row = (
                (
                    await conn.execute(
                        text(
                            """
                        SELECT cache_key, task, prompt_version, model, output, created_at
                        FROM ai_generation_cache WHERE cache_key = :key AND active
                        """
                        ),
                        {"key": key},
                    )
                )
                .mappings()
                .first()
            )
        if row is None:
            return None
        output = row["output"]
        return CachedGeneration(
            cache_key=row["cache_key"],
            task=row["task"],
            prompt_version=row["prompt_version"] or "",
            model=row["model"] or "",
            output=json.loads(output) if isinstance(output, str) else output,
            created_at=row["created_at"],
        )

    async def put(self, entry: CachedGeneration) -> None:
        async with self._engine.begin() as conn:
            await conn.execute(
                text(
                    """
                    INSERT INTO ai_generation_cache (cache_key, task, prompt_version, model,
                        output, created_at)
                    VALUES (:key, :task, :version, :model, CAST(:output AS jsonb), :created_at)
                    ON CONFLICT (cache_key) DO NOTHING
                    """
                ),
                {
                    "key": entry.cache_key,
                    "task": entry.task,
                    "version": entry.prompt_version,
                    "model": entry.model,
                    "output": json.dumps(entry.output, ensure_ascii=False),
                    "created_at": entry.created_at,
                },
            )
