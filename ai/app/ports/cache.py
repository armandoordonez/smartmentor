"""``GenerationCache`` port (``ai_generation_cache``, plan 5.4.11).

Key: SHA-256 of model + task + prompt version + system + rendered prompt + schema name (as the
notebook v2). The value is the validated ``...LLM`` output (JSON object). Not used for grading
nor personal content.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol


def cache_key(
    *, model: str, task: str, prompt_version: str, system: str, prompt: str, schema_name: str
) -> str:
    payload = json.dumps(
        [model, task, prompt_version, system, prompt, schema_name], ensure_ascii=False
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class CachedGeneration:
    cache_key: str
    task: str
    prompt_id: str
    prompt_version: str
    model: str
    output: dict[str, Any]
    created_at: datetime


class GenerationCache(Protocol):
    async def get(self, key: str) -> CachedGeneration | None: ...

    async def put(self, entry: CachedGeneration) -> None:
        """Store an entry; an existing key is kept (first writer wins)."""
        ...
