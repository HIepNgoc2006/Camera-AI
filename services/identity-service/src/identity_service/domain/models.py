"""Pure identity metadata and invariants with no credential material."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

CODE_PATTERN = re.compile(r"^[a-z][a-z0-9_.:-]{0,63}$")


class DomainValidationError(ValueError):
    """Raised when identity metadata violates a fail-closed invariant."""


class UserStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    LOCKED = "locked"
    DISABLED = "disabled"


class PersonType(StrEnum):
    STUDENT = "student"
    GUARDIAN = "guardian"
    STAFF = "staff"


class RoleScopeType(StrEnum):
    SYSTEM = "system"
    SCHOOL = "school"


class RoleStatus(StrEnum):
    ACTIVE = "active"
    RETIRED = "retired"


class PermissionStatus(StrEnum):
    ACTIVE = "active"
    RETIRED = "retired"


class AssignmentScopeType(StrEnum):
    SCHOOL = "school"
    CLASS = "class"
    ZONE = "zone"
    GLOBAL = "global"


def _require_opaque_id(value: UUID, field: str) -> None:
    if value.int == 0:
        raise DomainValidationError(f"{field} must be a non-zero opaque identifier")


def _normalized_text(value: str, field: str, *, maximum: int = 128) -> str:
    normalized = value.strip()
    if not normalized or len(normalized) > maximum or not all(c.isprintable() for c in normalized):
        raise DomainValidationError(f"{field} must be printable and within its length limit")
    return normalized


def _stable_code(value: str, field: str) -> str:
    normalized = value.strip().lower()
    if CODE_PATTERN.fullmatch(normalized) is None:
        raise DomainValidationError(f"{field} must be a stable lowercase code")
    return normalized


def _require_aware(value: datetime, field: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise DomainValidationError(f"{field} must include a timezone")


@dataclass(frozen=True, slots=True)
class UserAccount:
    """Account metadata; credentials are intentionally owned by a later implementation."""

    user_id: UUID
    username: str
    status: UserStatus
    school_id: UUID | None = None
    person_type: PersonType | None = None
    person_ref: UUID | None = None

    def __post_init__(self) -> None:
        _require_opaque_id(self.user_id, "user_id")
        object.__setattr__(self, "username", _normalized_text(self.username, "username").casefold())
        if self.school_id is not None:
            _require_opaque_id(self.school_id, "school_id")
        if (self.person_type is None) != (self.person_ref is None):
            raise DomainValidationError("person_type and person_ref must be provided together")
        if self.person_ref is not None:
            _require_opaque_id(self.person_ref, "person_ref")


@dataclass(frozen=True, slots=True)
class Role:
    role_id: UUID
    scope_type: RoleScopeType
    code: str
    name: str
    status: RoleStatus = RoleStatus.ACTIVE
    is_system: bool = False

    def __post_init__(self) -> None:
        _require_opaque_id(self.role_id, "role_id")
        object.__setattr__(self, "code", _stable_code(self.code, "role code"))
        object.__setattr__(self, "name", _normalized_text(self.name, "role name"))
        if self.is_system and self.scope_type is not RoleScopeType.SYSTEM:
            raise DomainValidationError("system roles must use system scope")


@dataclass(frozen=True, slots=True)
class Permission:
    permission_id: UUID
    resource: str
    action: str
    requires_object_scope: bool = True
    requires_audit: bool = False
    status: PermissionStatus = PermissionStatus.ACTIVE

    def __post_init__(self) -> None:
        _require_opaque_id(self.permission_id, "permission_id")
        object.__setattr__(self, "resource", _stable_code(self.resource, "permission resource"))
        object.__setattr__(self, "action", _stable_code(self.action, "permission action"))


@dataclass(frozen=True, slots=True)
class RoleAssignment:
    role_assignment_id: UUID
    user_id: UUID
    role_id: UUID
    granted_by: UUID
    scope_type: AssignmentScopeType
    valid_from: datetime
    school_id: UUID | None = None
    scope_ref: UUID | None = None
    valid_to: datetime | None = None
    revoked_at: datetime | None = None

    def __post_init__(self) -> None:
        for id_field, id_value in (
            ("role_assignment_id", self.role_assignment_id),
            ("user_id", self.user_id),
            ("role_id", self.role_id),
            ("granted_by", self.granted_by),
        ):
            _require_opaque_id(id_value, id_field)
        if self.user_id == self.granted_by:
            raise DomainValidationError("self-granted role assignments are forbidden")

        _require_aware(self.valid_from, "valid_from")
        for timestamp_field, timestamp_value in (
            ("valid_to", self.valid_to),
            ("revoked_at", self.revoked_at),
        ):
            if timestamp_value is not None:
                _require_aware(timestamp_value, timestamp_field)
                if timestamp_value < self.valid_from:
                    raise DomainValidationError(f"{timestamp_field} cannot precede valid_from")

        if self.scope_type is AssignmentScopeType.GLOBAL:
            if self.school_id is not None or self.scope_ref is not None:
                raise DomainValidationError(
                    "global assignments cannot carry school or object scope"
                )
            return

        if self.school_id is None or self.scope_ref is None:
            raise DomainValidationError("non-global assignments require school_id and scope_ref")
        _require_opaque_id(self.school_id, "school_id")
        _require_opaque_id(self.scope_ref, "scope_ref")
        if self.scope_type is AssignmentScopeType.SCHOOL and self.scope_ref != self.school_id:
            raise DomainValidationError("school assignment scope_ref must match school_id")


@dataclass(frozen=True, slots=True)
class SessionMetadata:
    """Non-credential session metadata safe for authorized lifecycle decisions."""

    session_id: UUID
    user_id: UUID
    expires_at: datetime
    revoked_at: datetime | None = None
    last_seen_at: datetime | None = None

    def __post_init__(self) -> None:
        _require_opaque_id(self.session_id, "session_id")
        _require_opaque_id(self.user_id, "user_id")
        _require_aware(self.expires_at, "expires_at")
        for field, value in (("revoked_at", self.revoked_at), ("last_seen_at", self.last_seen_at)):
            if value is not None:
                _require_aware(value, field)

    def is_active(self, at: datetime) -> bool:
        """Evaluate lifecycle state without reading or verifying a token."""

        _require_aware(at, "at")
        return self.revoked_at is None and at < self.expires_at
