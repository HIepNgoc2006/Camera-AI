"""Credential lifecycle records and pure authentication invariants."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import StrEnum
from uuid import UUID

from identity_service.domain.models import UserStatus, _require_aware, _require_opaque_id


class AuthDomainError(ValueError):
    """Stable authentication failure without credential material."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class RefreshState(StrEnum):
    ACTIVE = "active"
    ROTATED = "rotated"
    REVOKED = "revoked"


class RefreshRotationResult(StrEnum):
    ROTATED = "rotated"
    REPLAYED = "replayed"
    INACTIVE = "inactive"


class MfaState(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    REVOKED = "revoked"


@dataclass(frozen=True, slots=True)
class LoginSubject:
    user_id: UUID
    tenant_id: UUID
    school_id: UUID | None
    status: UserStatus
    password_hash: str
    role_codes: frozenset[str]

    def __post_init__(self) -> None:
        _require_opaque_id(self.user_id, "user_id")
        _require_opaque_id(self.tenant_id, "tenant_id")
        if self.school_id is not None:
            _require_opaque_id(self.school_id, "school_id")
        if not self.password_hash.startswith("$argon2id$"):
            raise AuthDomainError("AUTH_CREDENTIAL_INVALID")
        if not self.role_codes or any(not role for role in self.role_codes):
            raise AuthDomainError("AUTH_ROLE_CONTEXT_INVALID")


@dataclass(frozen=True, slots=True)
class SessionRecord:
    session_id: UUID
    family_id: UUID
    user_id: UUID
    tenant_id: UUID
    school_id: UUID | None
    mfa_verified: bool
    issued_at: datetime
    last_activity_at: datetime
    inactivity_expires_at: datetime
    expires_at: datetime
    revoked_at: datetime | None = None

    def __post_init__(self) -> None:
        for field, value in (
            ("session_id", self.session_id),
            ("family_id", self.family_id),
            ("user_id", self.user_id),
            ("tenant_id", self.tenant_id),
        ):
            _require_opaque_id(value, field)
        if self.school_id is not None:
            _require_opaque_id(self.school_id, "school_id")
        _require_aware(self.issued_at, "issued_at")
        _require_aware(self.last_activity_at, "last_activity_at")
        _require_aware(self.inactivity_expires_at, "inactivity_expires_at")
        _require_aware(self.expires_at, "expires_at")
        if self.expires_at <= self.issued_at:
            raise AuthDomainError("AUTH_SESSION_INVALID")
        if not (
            self.issued_at <= self.last_activity_at <= self.inactivity_expires_at <= self.expires_at
        ):
            raise AuthDomainError("AUTH_SESSION_INVALID")
        if self.revoked_at is not None:
            _require_aware(self.revoked_at, "revoked_at")

    def is_active(self, at: datetime) -> bool:
        _require_aware(at, "at")
        return self.revoked_at is None and at < self.inactivity_expires_at and at < self.expires_at

    def touched(self, *, at: datetime, inactivity_lifetime: timedelta) -> SessionRecord:
        _require_aware(at, "at")
        if inactivity_lifetime <= timedelta(0) or not self.is_active(at):
            raise AuthDomainError("AUTH_SESSION_INACTIVE")
        if at < self.last_activity_at:
            raise AuthDomainError("AUTH_SESSION_CLOCK_INVALID")
        inactivity_expires_at = min(at + inactivity_lifetime, self.expires_at)
        if inactivity_expires_at <= at:
            raise AuthDomainError("AUTH_SESSION_INACTIVE")
        return replace(
            self,
            last_activity_at=at,
            inactivity_expires_at=inactivity_expires_at,
        )


@dataclass(frozen=True, slots=True)
class RefreshRecord:
    refresh_id: UUID
    session_id: UUID
    family_id: UUID
    token_hash: bytes
    issued_at: datetime
    expires_at: datetime
    state: RefreshState = RefreshState.ACTIVE
    rotated_at: datetime | None = None

    def __post_init__(self) -> None:
        for field, value in (
            ("refresh_id", self.refresh_id),
            ("session_id", self.session_id),
            ("family_id", self.family_id),
        ):
            _require_opaque_id(value, field)
        if len(self.token_hash) != 32:
            raise AuthDomainError("AUTH_REFRESH_INVALID")
        _require_aware(self.issued_at, "issued_at")
        _require_aware(self.expires_at, "expires_at")
        if self.expires_at <= self.issued_at:
            raise AuthDomainError("AUTH_REFRESH_INVALID")
        if self.rotated_at is not None:
            _require_aware(self.rotated_at, "rotated_at")


@dataclass(frozen=True, slots=True)
class MfaFactor:
    factor_id: UUID
    user_id: UUID
    tenant_id: UUID
    secret_ciphertext: bytes
    state: MfaState
    created_at: datetime
    verified_at: datetime | None = None

    def __post_init__(self) -> None:
        for field, value in (
            ("factor_id", self.factor_id),
            ("user_id", self.user_id),
            ("tenant_id", self.tenant_id),
        ):
            _require_opaque_id(value, field)
        if not self.secret_ciphertext.startswith(b"ENCV1"):
            raise AuthDomainError("AUTH_MFA_STORAGE_INVALID")
        _require_aware(self.created_at, "created_at")
        if self.verified_at is not None:
            _require_aware(self.verified_at, "verified_at")
