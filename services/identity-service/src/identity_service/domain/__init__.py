"""Framework-free identity domain models."""

from identity_service.domain.models import (
    AssignmentScopeType,
    DomainValidationError,
    Permission,
    PermissionStatus,
    PersonType,
    Role,
    RoleAssignment,
    RoleScopeType,
    RoleStatus,
    SessionMetadata,
    UserAccount,
    UserStatus,
)

__all__ = [
    "AssignmentScopeType",
    "DomainValidationError",
    "Permission",
    "PermissionStatus",
    "PersonType",
    "Role",
    "RoleAssignment",
    "RoleScopeType",
    "RoleStatus",
    "SessionMetadata",
    "UserAccount",
    "UserStatus",
]
