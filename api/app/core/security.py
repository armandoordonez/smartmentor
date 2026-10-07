"""Validación de bearer tokens emitidos por Keycloak (OpenID Connect).

La API es un servidor de recursos: no inicia sesiones ni guarda contraseñas. Recibe un access token
(JWT) en `Authorization: Bearer <token>` y comprueba:
  - la firma, con las llaves públicas del proveedor (JWKS), solo con RS256;
  - el emisor (`iss`), la audiencia (`aud`) y la expiración (`exp`).
Quién es el usuario y qué puede hacer lo decide `app/auth` con la base de datos.
Ver ADR 0004 y proyecto/decisiones-pendientes.md (D-03).
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Protocol

import jwt
from jwt import PyJWKClient
from jwt.exceptions import PyJWKClientConnectionError

from app.common.exceptions import ServiceUnavailableError, UnauthorizedError
from app.core.config import Settings

logger = logging.getLogger("app.security")

ALLOWED_ALGORITHMS = ["RS256"]
CLOCK_LEEWAY_SECONDS = 10


@dataclass(frozen=True)
class TokenClaims:
    """Datos del token que la API usa. Los roles del token no se usan: manda `user_roles`."""

    subject: str
    email: str | None
    email_verified: bool
    full_name: str | None


class SigningKeyResolver(Protocol):
    """Lo que necesita el validador de un cliente JWKS (PyJWKClient o un doble de pruebas)."""

    def get_signing_key_from_jwt(self, token: str) -> Any: ...


class TokenValidator:
    def __init__(self, *, issuer: str, audience: str, key_resolver: SigningKeyResolver) -> None:
        self._issuer = issuer
        self._audience = audience
        self._key_resolver = key_resolver

    @classmethod
    def from_settings(cls, settings: Settings) -> "TokenValidator":
        return cls(
            issuer=settings.oidc_issuer_url,
            audience=settings.oidc_audience,
            key_resolver=PyJWKClient(settings.oidc_jwks_url, cache_keys=True, timeout=5),
        )

    async def validate(self, token: str) -> TokenClaims:
        try:
            # PyJWKClient es síncrono (HTTP + caché de llaves): se ejecuta fuera del event loop.
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
            raise ServiceUnavailableError(
                "The identity provider is not reachable.", code="IDENTITY_PROVIDER_UNAVAILABLE"
            ) from exc
        except jwt.PyJWTError as exc:
            # El motivo exacto (firma, audiencia, expiración...) va al log, no al cliente.
            logger.info("token rejected: %s", exc.__class__.__name__)
            raise UnauthorizedError("The token is not valid.", code="INVALID_TOKEN") from exc

        return TokenClaims(
            subject=str(payload["sub"]),
            email=payload.get("email"),
            email_verified=bool(payload.get("email_verified", False)),
            full_name=payload.get("name") or payload.get("preferred_username"),
        )
