"""`Idempotency-Key` de las operaciones que cuestan o entregan (api-v2.md, sección 1).

Misma clave y mismo cuerpo: la misma respuesta durante 24 h. Misma clave con otro cuerpo: 422
`IDEMPOTENCY_KEY_REUSED`. Sin clave: 428 `IDEMPOTENCY_KEY_REQUIRED`. Las respuestas con error no se
guardan, así que un reintento tras un fallo vuelve a ejecutar la operación.

La tienda es un Protocol: la de memoria sirve a un solo proceso (desarrollo y pruebas). El reparto
entre varios procesos necesita una tabla; queda anotado en la bitácora como cambio pedido a la base.
Además, los trabajos de `ai/` tienen su propia `idempotency_key` (ADR 0010), que es la garantía
fuerte contra duplicar un trabajo.
"""

import asyncio
import hashlib
import json
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated, Any, Protocol

from fastapi import Depends, Header, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.common.exceptions import BusinessRuleError, PreconditionRequiredError
from app.core.config import get_settings

REPLAY_HEADER = "Idempotent-Replayed"


@dataclass(frozen=True)
class StoredResponse:
    fingerprint: str
    status_code: int
    body: Any
    headers: dict[str, str]
    expires_at: float


class IdempotencyStore(Protocol):
    async def get(self, key: str) -> StoredResponse | None: ...

    async def put(self, key: str, response: StoredResponse) -> None: ...

    def lock(self, key: str) -> asyncio.Lock: ...


class InMemoryIdempotencyStore:
    def __init__(self) -> None:
        self._items: dict[str, StoredResponse] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    async def get(self, key: str) -> StoredResponse | None:
        found = self._items.get(key)
        if found is not None and found.expires_at <= time.time():
            del self._items[key]
            return None
        return found

    async def put(self, key: str, response: StoredResponse) -> None:
        self._items[key] = response

    def lock(self, key: str) -> asyncio.Lock:
        return self._locks.setdefault(key, asyncio.Lock())


def fingerprint_of(method: str, path: str, body: bytes | str | None) -> str:
    raw = body.encode() if isinstance(body, str) else (body or b"")
    return hashlib.sha256(method.encode() + b"|" + path.encode() + b"|" + raw).hexdigest()


class IdempotencyRunner:
    """Ejecuta una operación una sola vez por (usuario, clave) y repite su respuesta."""

    def __init__(self, store: IdempotencyStore, key: str | None, ttl_seconds: int) -> None:
        self._store = store
        self._key = key
        self._ttl = ttl_seconds

    @property
    def key(self) -> str:
        if not self._key:
            raise PreconditionRequiredError(
                "The Idempotency-Key header (a UUID) is required for this operation."
            )
        try:
            uuid.UUID(self._key)
        except ValueError as exc:
            raise BusinessRuleError(
                "The Idempotency-Key header must be a UUID.", code="VALIDATION_ERROR"
            ) from exc
        return self._key

    async def run(
        self,
        *,
        user_id: int,
        request: Request,
        body: BaseModel | dict[str, Any] | bytes | None,
        action: Callable[[], Awaitable[BaseModel]],
        status_code: int = 202,
        location: Callable[[BaseModel], str | None] | None = None,
        status_of: Callable[[BaseModel], int] | None = None,
    ) -> JSONResponse:
        key = self.key  # valida antes de tocar nada
        if isinstance(body, BaseModel):
            payload: bytes | str | None = body.model_dump_json()
        elif isinstance(body, dict):
            payload = json.dumps(body, sort_keys=True, default=str)
        else:
            payload = body
        fingerprint = fingerprint_of(request.method, request.url.path, payload)
        store_key = f"{user_id}:{key}"
        async with self._store.lock(store_key):
            stored = await self._store.get(store_key)
            if stored is not None:
                if stored.fingerprint != fingerprint:
                    raise BusinessRuleError(
                        "This Idempotency-Key was already used with a different request.",
                        code="IDEMPOTENCY_KEY_REUSED",
                    )
                return JSONResponse(
                    stored.body,
                    status_code=stored.status_code,
                    headers={**stored.headers, REPLAY_HEADER: "true"},
                )
            result = await action()
            if status_of is not None:  # p. ej. 200 calificado al instante o 202 con un trabajo
                status_code = status_of(result)
            headers: dict[str, str] = {}
            target = location(result) if location is not None else None
            if target:
                headers["Location"] = target
            encoded = jsonable_encoder(result)
            await self._store.put(
                store_key,
                StoredResponse(fingerprint, status_code, encoded, headers, time.time() + self._ttl),
            )
            return JSONResponse(encoded, status_code=status_code, headers=headers)


def _store_of(request: Request) -> IdempotencyStore:
    state = request.app.state
    store: IdempotencyStore | None = getattr(state, "idempotency_store", None)
    if store is None:
        store = InMemoryIdempotencyStore()
        state.idempotency_store = store
    return store


def get_idempotency(
    request: Request,
    idempotency_key: Annotated[
        str | None,
        Header(alias="Idempotency-Key", description="UUID que identifica la operación."),
    ] = None,
) -> IdempotencyRunner:
    return IdempotencyRunner(
        _store_of(request), idempotency_key, get_settings().idempotency_ttl_seconds
    )


IdempotencyDep = Annotated[IdempotencyRunner, Depends(get_idempotency)]
