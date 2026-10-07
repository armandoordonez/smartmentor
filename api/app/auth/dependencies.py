"""Autenticación y autorización de las rutas: `get_current_user` y `require_roles`.

Es parte de la raíz de composición: conecta el validador de tokens (core) con el servicio de
autenticación del dominio de identidad y sus repositorios concretos.
"""

from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

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

bearer_scheme = HTTPBearer(
    auto_error=False,
    description="Access token de Keycloak (realm smartmentor).",
)


async def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    session: SessionDep,
) -> CurrentUser:
    if credentials is None:
        raise UnauthorizedError("A bearer token is required.", code="MISSING_TOKEN")

    validator: TokenValidator = request.app.state.token_validator
    claims = await validator.validate(credentials.credentials)

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
