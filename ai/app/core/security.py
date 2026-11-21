"""Service-to-service authentication (ADR 0014).

The API obtains a token with *client credentials* (confidential client
``smartmentor-api-service``) whose audience is ``smartmentor-ai``. ``ai/`` validates it with the
same JWKS logic as the API (ADR 0004): RS256 signature, ``iss``, ``aud`` and ``exp``. Without a
token: ``401 MISSING_TOKEN``; with an invalid one: ``401 INVALID_TOKEN``.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Annotated, Any, Protocol

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from jwt.exceptions import PyJWKClientConnectionError

from app.core.errors import ApiError

logger = logging.getLogger("app.security")

ALLOWED_ALGORITHMS = ["RS256"]
CLOCK_LEEWAY_SECONDS = 10


@dataclass(frozen=True)
class ServiceClaims:
    """What ``ai/`` keeps from the token: who called (client id) and the subject."""

    subject: str
    client_id: str | None


class SigningKeyResolver(Protocol):
    """What the validator needs from a JWKS client (``PyJWKClient`` or a test double)."""

    def get_signing_key_from_jwt(self, token: str) -> Any: ...


class ServiceTokenValidator:
    def __init__(self, *, issuer: str, audience: str, key_resolver: SigningKeyResolver) -> None:
        self._issuer = issuer
        self._audience = audience
        self._key_resolver = key_resolver

    @classmethod
    def from_urls(cls, *, issuer: str, jwks_url: str, audience: str) -> ServiceTokenValidator:
        return cls(
            issuer=issuer,
            audience=audience,
            key_resolver=PyJWKClient(jwks_url, cache_keys=True, timeout=5),
        )

    async def validate(self, token: str) -> ServiceClaims:
        try:
            # PyJWKClient is synchronous (HTTP + key cache): run it outside the event loop.
            signing_key = await asyncio.to_thread(
                self._key_resolver.get_signing_key_from_jwt, token
            )
            payload: dict[str, Any] = jwt.decode(
                token,
                signing_key.key,
                algorithms=ALLOWED_ALGORITHMS,
                audience=self._audience,
                issuer=self._issuer,
                leeway=CLOCK_LEEWAY_SECONDS,
                options={"require": ["exp", "iss", "sub", "aud"]},
            )
        except PyJWKClientConnectionError as exc:
            logger.error("identity provider keys are unreachable")
            raise ApiError(
                503,
                "IDENTITY_PROVIDER_UNAVAILABLE",
                "The identity provider is not reachable.",
            ) from exc
        except jwt.PyJWTError as exc:
            # The exact reason (signature, audience, expiry...) goes to the log, not the client.
            logger.info("token rejected: %s", exc.__class__.__name__)
            raise ApiError(401, "INVALID_TOKEN", "The token is not valid.") from exc
        client = payload.get("azp") or payload.get("client_id")
        return ServiceClaims(subject=str(payload["sub"]), client_id=str(client) if client else None)


_bearer = HTTPBearer(auto_error=False)


async def require_service_token(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> ServiceClaims:
    """FastAPI dependency for every ``/v1`` route."""
    if credentials is None or credentials.scheme.lower() != "bearer" or not credentials.credentials:
        raise ApiError(401, "MISSING_TOKEN", "A bearer token is required.")
    validator: ServiceTokenValidator | None = request.app.state.container.token_validator
    if validator is None:
        raise ApiError(
            503,
            "IDENTITY_PROVIDER_UNAVAILABLE",
            "Token validation is not configured (OIDC_ISSUER_URL, OIDC_JWKS_URL).",
        )
    return await validator.validate(credentials.credentials)


ServiceAuth = Annotated[ServiceClaims, Depends(require_service_token)]
