"""Application ports for fail-closed authentication dependencies."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from camera_ai_audit import AuditIntent

from identity_service.domain.auth import (
    LoginSubject,
    MfaFactor,
    RefreshRecord,
    RefreshRotationResult,
    SessionRecord,
)


class AuthRepository(Protocol):
    def login_subject(self, *, tenant_id: UUID, login_digest: bytes) -> LoginSubject | None: ...

    def active_mfa_factor(self, *, user_id: UUID) -> MfaFactor | None: ...

    def create_session(
        self,
        *,
        session: SessionRecord,
        refresh: RefreshRecord,
        audit: AuditIntent,
    ) -> None: ...

    def refresh_record(self, token_hash: bytes) -> RefreshRecord | None: ...

    def session(self, session_id: UUID) -> SessionRecord | None: ...

    def active_session(
        self, *, expected: SessionRecord, observed_at: datetime
    ) -> SessionRecord | None: ...

    def touch_session_activity(
        self,
        *,
        expected: SessionRecord,
        activity_at: datetime,
        inactivity_expires_at: datetime,
    ) -> SessionRecord | None: ...

    def role_codes(self, user_id: UUID) -> frozenset[str]: ...

    def rotate_refresh(
        self,
        *,
        previous: RefreshRecord,
        replacement: RefreshRecord,
        expected_session: SessionRecord,
        rotated_at: datetime,
        inactivity_expires_at: datetime,
    ) -> RefreshRotationResult: ...

    def revoke_family(
        self, *, family_id: UUID, revoked_at: datetime, audit: AuditIntent
    ) -> None: ...

    def revoke_session(
        self,
        *,
        session_id: UUID,
        tenant_id: UUID,
        school_id: UUID | None,
        revoked_at: datetime,
        audit: AuditIntent,
    ) -> bool: ...

    def revoke_user_sessions(
        self, *, user_id: UUID, revoked_at: datetime, audit: AuditIntent
    ) -> int: ...

    def save_mfa_factor(self, *, factor: MfaFactor, audit: AuditIntent) -> None: ...

    def record_audit(self, audit: AuditIntent) -> None: ...


class LoginRateLimiter(Protocol):
    def check(self, *, account_key: bytes, source_key: str, now: datetime) -> int | None: ...

    def failure(self, *, account_key: bytes, source_key: str, now: datetime) -> None: ...

    def success(self, *, account_key: bytes, source_key: str) -> None: ...


class AccessTokenCodec(Protocol):
    def issue(self, *, session: SessionRecord, roles: frozenset[str], now: datetime) -> str: ...

    def verify(self, token: str, *, now: datetime) -> dict[str, object]: ...


class PasswordVerifier(Protocol):
    def verify(self, password_hash: str, password: str) -> bool: ...

    @property
    def dummy_hash(self) -> str: ...


class MfaProtector(Protocol):
    def protect(self, *, factor_id: UUID, tenant_id: UUID, secret: str) -> bytes: ...

    def reveal(self, factor: MfaFactor) -> str: ...


class TotpVerifier(Protocol):
    def verify(self, *, secret: str, code: str, now: datetime) -> bool: ...
