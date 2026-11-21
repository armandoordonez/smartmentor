"""Utilidades de pruebas para firmar tokens como lo haría Keycloak (RS256)."""

import time
from dataclasses import dataclass
from typing import Any

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

ISSUER = "http://keycloak.test/realms/smartmentor"
AUDIENCE = "smartmentor-api"


@dataclass(frozen=True)
class SigningKey:
    key: Any


class KeyPair:
    """Par de llaves RSA de prueba."""

    def __init__(self) -> None:
        self.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.public_key = self.private_key.public_key()


class StaticKeyResolver:
    """Hace el papel de PyJWKClient: siempre entrega la llave pública de prueba."""

    def __init__(self, keys: KeyPair) -> None:
        self._keys = keys

    def get_signing_key_from_jwt(self, token: str) -> SigningKey:
        return SigningKey(self._keys.public_key)


def make_token(
    keys: KeyPair,
    *,
    sub: str = "user-sub",
    email: str | None = "user@example.com",
    email_verified: bool = True,
    name: str | None = "Usuario de prueba",
    issuer: str = ISSUER,
    audience: str | list[str] = AUDIENCE,
    expires_in: int = 300,
    extra: dict[str, Any] | None = None,
) -> str:
    now = int(time.time())
    payload: dict[str, Any] = {
        "sub": sub,
        "iss": issuer,
        "aud": audience,
        "iat": now,
        "exp": now + expires_in,
        "email_verified": email_verified,
    }
    if email is not None:
        payload["email"] = email
    if name is not None:
        payload["name"] = name
    payload.update(extra or {})
    return jwt.encode(payload, keys.private_key, algorithm="RS256", headers={"kid": "test"})
