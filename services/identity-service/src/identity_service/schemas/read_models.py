"""Credential-free identity metadata for future authorized internal reads."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from identity_service.domain import (
    AssignmentScopeType,
    PermissionStatus,
    PersonType,
    RoleScopeType,
    RoleStatus,
    UserStatus,
)


class StrictReadModel(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class UserRead(StrictReadModel):
    user_id: UUID
    school_id: UUID | None
    username: str
    person_type: PersonType | None
    person_ref: UUID | None
    status: UserStatus


class RoleRead(StrictReadModel):
    role_id: UUID
    scope_type: RoleScopeType
    code: str
    name: str
    status: RoleStatus
    is_system: bool


class PermissionRead(StrictReadModel):
    permission_id: UUID
    resource: str
    action: str
    requires_object_scope: bool
    requires_audit: bool
    status: PermissionStatus


class RoleAssignmentRead(StrictReadModel):
    role_assignment_id: UUID
    user_id: UUID
    role_id: UUID
    granted_by: UUID
    school_id: UUID | None
    scope_type: AssignmentScopeType
    scope_ref: UUID | None
    valid_from: datetime
    valid_to: datetime | None
    revoked_at: datetime | None


class SessionRead(StrictReadModel):
    session_id: UUID
    user_id: UUID
    expires_at: datetime
    revoked_at: datetime | None
    last_seen_at: datetime | None
