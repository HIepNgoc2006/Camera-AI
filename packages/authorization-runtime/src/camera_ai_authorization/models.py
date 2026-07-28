"""Opaque, immutable inputs and outputs for authorization decisions."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

_STABLE_CODE = re.compile(r"^[a-z][a-z0-9_.:-]{0,95}$")
_ERROR_CODE = re.compile(r"^[A-Z][A-Z0-9_]{2,95}$")
_SERVICE_CODE = re.compile(r"^[a-z][a-z0-9-]{1,62}[a-z0-9]$")
_REQUEST_ID = re.compile(r"^req_[A-Za-z0-9_-]{8,120}$")
_CORRELATION_ID = re.compile(r"^cor_[A-Za-z0-9_-]{8,120}$")


class AuthorizationInputError(ValueError):
    """Stable validation error that never echoes the rejected value."""

    def __init__(self) -> None:
        super().__init__("AUTHZ_REQUEST_INVALID")


def _require(condition: bool) -> None:
    if not condition:
        raise AuthorizationInputError


def _aware(value: datetime) -> None:
    _require(value.tzinfo is not None and value.utcoffset() is not None)


def _uuid(value: UUID | None) -> None:
    if value is not None:
        _require(value.int != 0)


def _code(value: str, pattern: re.Pattern[str] = _STABLE_CODE) -> None:
    _require(pattern.fullmatch(value) is not None)


class ScopeDimension(StrEnum):
    SCHOOL = "school_id"
    CLASS = "class_id"
    GUARDIAN_SUBJECT = "guardian_subject_ref"
    KITCHEN_ZONE = "kitchen_zone_id"


class ConsentState(StrEnum):
    ALLOWED = "allowed"
    BLOCKED = "blocked"
    NOT_REQUIRED = "not_required"
    UNAVAILABLE = "unavailable"


class RetentionState(StrEnum):
    ACTIVE = "active"
    EXPIRED = "expired"
    UNAVAILABLE = "unavailable"


class LegalHoldState(StrEnum):
    NONE = "none"
    ACTIVE = "active"
    RELEASED = "released"
    UNAVAILABLE = "unavailable"


class ResourceState(StrEnum):
    AVAILABLE = "available"
    PENDING = "pending"
    QUARANTINED = "quarantined"
    DELETE_PENDING = "delete_pending"
    DELETED = "deleted"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class ScopeGrant:
    """Current assignment/relationship scope resolved by the owning service."""

    tenant_id: UUID
    school_ids: frozenset[UUID]
    dimension: ScopeDimension
    scope_ids: frozenset[UUID]
    valid_from: datetime
    valid_until: datetime

    def __post_init__(self) -> None:
        _uuid(self.tenant_id)
        _aware(self.valid_from)
        _aware(self.valid_until)
        _require(self.valid_from < self.valid_until)
        _require(1 <= len(self.school_ids) <= 1_000)
        _require(1 <= len(self.scope_ids) <= 1_000)
        for scope_id in self.school_ids | self.scope_ids:
            _uuid(scope_id)

    def is_current(self, now: datetime) -> bool:
        _aware(now)
        return self.valid_from <= now < self.valid_until


@dataclass(frozen=True, slots=True, kw_only=True)
class AuthorizationRequest:
    decision_id: UUID
    request_id: str
    correlation_id: str
    source_service: str
    actor_id: UUID
    actor_authenticated: bool
    actor_permission_codes: frozenset[str]
    permission_code: str
    resource_type: str
    action: str
    resource_id: UUID
    resource_exists: bool
    policy_version: str | None
    tenant_id: UUID
    school_id: UUID
    class_id: UUID | None
    guardian_subject_ref: UUID | None
    kitchen_zone_id: UUID | None
    purpose_code: str
    consent_state: ConsentState
    retention_state: RetentionState
    legal_hold_state: LegalHoldState
    resource_state: ResourceState
    sensitivity: str
    approval_status: str
    dependencies_available: bool
    now: datetime

    def __post_init__(self) -> None:
        for uuid_value in (
            self.decision_id,
            self.actor_id,
            self.resource_id,
            self.tenant_id,
            self.school_id,
            self.class_id,
            self.guardian_subject_ref,
            self.kitchen_zone_id,
        ):
            _uuid(uuid_value)
        _code(self.request_id, _REQUEST_ID)
        _code(self.correlation_id, _CORRELATION_ID)
        _code(self.source_service, _SERVICE_CODE)
        for code_value in (
            self.permission_code,
            self.resource_type,
            self.action,
            self.purpose_code,
            self.sensitivity,
            self.approval_status,
        ):
            _code(code_value)
        if self.policy_version is not None:
            _code(self.policy_version)
        for permission_code in self.actor_permission_codes:
            _code(permission_code)
        _aware(self.now)
        _require(len(self.actor_permission_codes) <= 256)


@dataclass(frozen=True, slots=True)
class AuthorizationDecision:
    allowed: bool
    internal_reason_code: str
    public_error_code: str
    public_http_status: int
    required_permission_code: str
    policy_version: str

    def __post_init__(self) -> None:
        _code(self.internal_reason_code, _ERROR_CODE)
        _code(self.public_error_code, _ERROR_CODE)
        _code(self.required_permission_code)
        _code(self.policy_version)
        _require(self.public_http_status in {0, 404, 503})
        _require(self.allowed == (self.public_http_status == 0))
