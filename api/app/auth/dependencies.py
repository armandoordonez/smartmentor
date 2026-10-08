"""Autenticación y autorización de las rutas: `get_current_user` y `require_roles`.

Es parte de la raíz de composición: conecta el validador de tokens (core) con el servicio de
autenticación del dominio de identidad y sus repositorios concretos.
"""

from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, OAuth2PasswordBearer

from app.common.exceptions import ForbiddenError, UnauthorizedError
from app.common.repository_impl import SqlAlchemyUnitOfWork
from app.core.config import get_settings
from app.core.database import SessionDep, apply_audit_user
from app.core.security import TokenValidator
from app.domains.identity.authentication import (
    AuthenticationService,
    CurrentUser,
    ExternalIdentity,
)
from app.domains.identity.repository_impl import (
    SqlAlchemyRoleRepository,
    SqlAlchemyUserRepository,
    SqlAlchemyUserRoleRepository,
)

DOCS_LOGIN_SCOPES = {
    "openid": "Identidad OpenID Connect",
    "profile": "Nombre del usuario",
    "email": "Correo del usuario",
}

# Dos formas de entregar el mismo access token, ambas visibles en el botón "Authorize" de Swagger:
#   - pegar un token ya emitido (Postman, curl, el frontend);
#   - iniciar sesión con usuario y contraseña: Swagger pide el token a Keycloak por su cuenta.
# En las dos el token viaja igual: `Authorization: Bearer <access_token>`.
bearer_scheme = HTTPBearer(
    auto_error=False,
    scheme_name="Token (pegar)",
    description="Access token de Keycloak (realm smartmentor), sin la palabra Bearer.",
)


async def _password_login_disabled() -> None:
    return None


_docs_client_id = get_settings().oidc_docs_client_id
password_scheme: Callable[..., Awaitable[str | None]] = (
    OAuth2PasswordBearer(
        tokenUrl=get_settings().oidc_token_url,
        scheme_name="Login (usuario y contraseña)",
        # Keycloak rechaza un scope vacío (invalid_scope): Swagger envía estos, preseleccionados.
        scopes=DOCS_LOGIN_SCOPES,
        description=(
            f"Swagger pide el token a Keycloak con el cliente `{_docs_client_id}` "
            "(solo desarrollo). Escribe el correo y la contraseña de tu usuario del realm."
        ),
        auto_error=False,
    )
    if _docs_client_id
    else _password_login_disabled
)


async def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    login_token: Annotated[str | None, Depends(password_scheme)],
    session: SessionDep,
) -> CurrentUser:
    token = credentials.credentials if credentials is not None else login_token
    if token is None:
        raise UnauthorizedError("A bearer token is required.", code="MISSING_TOKEN")

    validator: TokenValidator = request.app.state.token_validator
    claims = await validator.validate(token)

    # Mientras se resuelve (y quizá se crea) el usuario, la auditoría registra la identidad.
    await apply_audit_user(session, f"identity:{claims.subject}")
    service = AuthenticationService(
        SqlAlchemyUserRepository(session),
        SqlAlchemyRoleRepository(session),
        SqlAlchemyUserRoleRepository(session),
        SqlAlchemyUnitOfWork(session),
        provider=get_settings().oidc_identity_provider,
    )
    user = await service.resolve(
        ExternalIdentity(
            subject=claims.subject,
            email=claims.email,
            email_verified=claims.email_verified,
            full_name=claims.full_name,
        )
    )
    # A partir de aquí, cada cambio de la petición se audita con el id del usuario autenticado.
    await apply_audit_user(session, str(user.id))
    return user


CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]


def require_roles(*allowed: str) -> Callable[..., Awaitable[CurrentUser]]:
    """Dependencia de ruta: exige estar autenticado y tener alguno de los roles indicados."""

    async def guard(user: CurrentUserDep) -> CurrentUser:
        if not user.has_any_role(*allowed):
            raise ForbiddenError(
                "Your role does not allow this operation.", code="INSUFFICIENT_ROLE"
            )
        return user

    return guard
