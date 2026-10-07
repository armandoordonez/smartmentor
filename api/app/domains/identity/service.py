"""Casos de uso de identidad."""

from app.common.service import CrudService
from app.domains.identity.entities import Role, User, UserRole


class RoleService(CrudService[Role]):
    resource_name = "Role"


class UserService(CrudService[User]):
    resource_name = "User"


class UserRoleService(CrudService[UserRole]):
    resource_name = "User role"
