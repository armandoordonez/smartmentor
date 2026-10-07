import jwt
import pytest
from jwt.exceptions import PyJWKClientConnectionError

from app.common.exceptions import ServiceUnavailableError, UnauthorizedError
from app.core.security import TokenValidator
from tests.auth_helpers import AUDIENCE, ISSUER, KeyPair, StaticKeyResolver, make_token

KEYS = KeyPair()


def validator() -> TokenValidator:
    return TokenValidator(issuer=ISSUER, audience=AUDIENCE, key_resolver=StaticKeyResolver(KEYS))


async def test_valid_token_yields_claims() -> None:
    token = make_token(KEYS, sub="abc", email="ana@example.com", name="Ana")
    claims = await validator().validate(token)
    assert claims.subject == "abc"
    assert claims.email == "ana@example.com"
    assert claims.email_verified is True
    assert claims.full_name == "Ana"


async def test_audience_may_be_a_list() -> None:
    token = make_token(KEYS, audience=["account", AUDIENCE])
    assert (await validator().validate(token)).subject == "user-sub"


@pytest.mark.parametrize(
    "token",
    [
        make_token(KEYS, expires_in=-60),
        make_token(KEYS, issuer="http://otro-emisor/realms/x"),
        make_token(KEYS, audience="account"),
        make_token(KeyPair()),  # firmado con otra llave
        "esto.no.es-un-jwt",
        "",
    ],
    ids=["expirado", "emisor-distinto", "audiencia-distinta", "otra-llave", "basura", "vacio"],
)
async def test_invalid_tokens_are_rejected(token: str) -> None:
    with pytest.raises(UnauthorizedError) as error:
        await validator().validate(token)
    assert error.value.code == "INVALID_TOKEN"


async def test_unsigned_and_symmetric_tokens_are_rejected() -> None:
    payload = {"sub": "x", "iss": ISSUER, "aud": AUDIENCE, "exp": 9999999999}
    unsigned = jwt.encode(payload, key=None, algorithm="none")  # type: ignore[arg-type]
    symmetric = jwt.encode(payload, "secreto-compartido-de-32-bytes-minimo!", algorithm="HS256")
    for token in (unsigned, symmetric):
        with pytest.raises(UnauthorizedError):
            await validator().validate(token)


async def test_token_without_required_claims_is_rejected() -> None:
    token = jwt.encode(
        {"iss": ISSUER, "aud": AUDIENCE, "exp": 9999999999}, KEYS.private_key, algorithm="RS256"
    )
    with pytest.raises(UnauthorizedError):
        await validator().validate(token)  # falta sub


async def test_unreachable_identity_provider_is_a_503_not_a_401() -> None:
    class Unreachable:
        def get_signing_key_from_jwt(self, token: str) -> object:
            raise PyJWKClientConnectionError("sin conexión")

    broken = TokenValidator(issuer=ISSUER, audience=AUDIENCE, key_resolver=Unreachable())
    with pytest.raises(ServiceUnavailableError):
        await broken.validate(make_token(KEYS))
