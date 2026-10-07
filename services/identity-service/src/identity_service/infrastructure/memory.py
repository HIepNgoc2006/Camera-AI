"""Deterministic in-memory adapters for sanitized local and unit-test profiles."""

from __future__ import annotations

import hmac
from collections import defaultdict
from dataclasses import replace
from datetime import datetime, timedelta
from threading import RLock
from uuid import UUID

from camera_ai_audit import AuditIntent

from identity_service.domain.auth import (
    LoginSubject,
    MfaFactor,
    MfaState,
    RefreshRecord,
    RefreshRotationResult,
    RefreshState,
    SessionRecord,
)
from identity_service.domain.models import UserStatus


class InMemoryAuthRepository:
    """Thread-safe fake repository; never intended for staging or production."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._subjects: dict[tuple[UUID, bytes], LoginSubject] = {}
        self._sessions: dict[UUID, SessionRecord] = {}
        self._refresh: dict[bytes, RefreshRecord] = {}
        self._factors: dict[UUID, MfaFactor] = {}
        self.audit_intents: list[AuditIntent] = []

    def seed_subject(self, *, tenant_id: UUID, login_digest: bytes, subject: LoginSubject) -> None:
        with self._lock:
            self._subjects[(tenant_id, login_digest)] = subject

    def login_subject(self, *, tenant_id: UUID, login_digest: bytes) -> LoginSubject | None:
        with self._lock:
            return self._subjects.get((tenant_id, login_digest))

    def active_mfa_factor(self, *, user_id: UUID) -> MfaFactor | None:
        with self._lock:
            factor = self._factors.get(user_id)
            return factor if factor is not None and factor.state is MfaState.ACTIVE else None

    def create_session(
        self,
        *,
        session: SessionRecord,
        refresh: RefreshRecord,
        audit: AuditIntent,
    ) -> None:
        with self._lock:
            self._sessions[session.session_id] = session
            self._refresh[refresh.token_hash] = refresh
            self.audit_intents.append(audit)

    def refresh_record(self, token_hash: bytes) -> RefreshRecord | None:
        with self._lock:
            for digest, record in self._refresh.items():
                if hmac.compare_digest(digest, token_hash):
                    return record
            return None

    def session(self, session_id: UUID) -> SessionRecord | None:
        with self._lock:
            return self._sessions.get(session_id)

    def active_session(
        self, *, expected: SessionRecord, observed_at: datetime
    ) -> SessionRecord | None:
        with self._lock:
            session = self._sessions.get(expected.session_id)
            return (
                session
                if session is not None
                and _same_session_binding(session, expected)
                and session.is_active(observed_at)
                else None
            )

    def touch_session_activity(
        self,
        *,
        expected: SessionRecord,
        activity_at: datetime,
        inactivity_expires_at: datetime,
    ) -> SessionRecord | None:
        with self._lock:
            session = self._sessions.get(expected.session_id)
            if (
                session is None
                or not _same_session_binding(session, expected)
                or not session.is_active(activity_at)
                or activity_at < session.last_activity_at
                or inactivity_expires_at <= activity_at
                or inactivity_expires_at > session.expires_at
            ):
                return None
            touched = replace(
                session,
                last_activity_at=activity_at,
                inactivity_expires_at=inactivity_expires_at,
            )
            self._sessions[expected.session_id] = touched
            return touched

    def role_codes(self, user_id: UUID) -> frozenset[str]:
        with self._lock:
            for subject in self._subjects.values():
                if subject.user_id == user_id and subject.status is UserStatus.ACTIVE:
                    return subject.role_codes
            return frozenset()

    def rotate_refresh(
        self,
        *,
        previous: RefreshRecord,
        replacement: RefreshRecord,
        expected_session: SessionRecord,
        rotated_at: datetime,
        inactivity_expires_at: datetime,
    ) -> RefreshRotationResult:
        with self._lock:
            if (
                previous.session_id != expected_session.session_id
                or previous.family_id != expected_session.family_id
                or replacement.session_id != expected_session.session_id
                or replacement.family_id != expected_session.family_id
            ):
                return RefreshRotationResult.INACTIVE
            current = self._refresh.get(previous.token_hash)
            if current is not None and current.state is RefreshState.ROTATED:
                return RefreshRotationResult.REPLAYED
            if current is None or current.state is not RefreshState.ACTIVE:
                return RefreshRotationResult.INACTIVE
            session = self._sessions.get(previous.session_id)
            if (
                session is None
                or not _same_session_binding(session, expected_session)
                or not session.is_active(rotated_at)
                or rotated_at < session.last_activity_at
                or inactivity_expires_at <= rotated_at
                or inactivity_expires_at > session.expires_at
            ):
                return RefreshRotationResult.INACTIVE
            self._sessions[session.session_id] = replace(
                session,
                last_activity_at=rotated_at,
                inactivity_expires_at=inactivity_expires_at,
            )
            self._refresh[previous.token_hash] = replace(
                current,
                state=RefreshState.ROTATED,
                rotated_at=rotated_at,
            )
            self._refresh[replacement.token_hash] = replacement
            return RefreshRotationResult.ROTATED

    def revoke_family(self, *, family_id: UUID, revoked_at: datetime, audit: AuditIntent) -> None:
        with self._lock:
            for session_id, session in tuple(self._sessions.items()):
                if session.family_id == family_id and session.revoked_at is None:
                    self._sessions[session_id] = replace(session, revoked_at=revoked_at)
            for digest, record in tuple(self._refresh.items()):
                if record.family_id == family_id and record.state is not RefreshState.REVOKED:
                    self._refresh[digest] = replace(record, state=RefreshState.REVOKED)
            self.audit_intents.append(audit)

    def revoke_session(
        self,
        *,
        session_id: UUID,
        tenant_id: UUID,
        school_id: UUID | None,
        revoked_at: datetime,
        audit: AuditIntent,
    ) -> bool:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None or session.tenant_id != tenant_id or session.school_id != school_id:
                return False
            if session.revoked_at is None:
                self._sessions[session_id] = replace(session, revoked_at=revoked_at)
                for digest, record in tuple(self._refresh.items()):
                    if record.session_id == session_id and record.state is RefreshState.ACTIVE:
                        self._refresh[digest] = replace(record, state=RefreshState.REVOKED)
            self.audit_intents.append(audit)
            return True

    def revoke_user_sessions(
        self, *, user_id: UUID, revoked_at: datetime, audit: AuditIntent
    ) -> int:
        with self._lock:
            session_ids = {
                session_id
                for session_id, session in self._sessions.items()
                if session.user_id == user_id and session.revoked_at is None
            }
            for session_id in session_ids:
                self._sessions[session_id] = replace(
                    self._sessions[session_id], revoked_at=revoked_at
                )
            for digest, record in tuple(self._refresh.items()):
                if record.session_id in session_ids and record.state is RefreshState.ACTIVE:
                    self._refresh[digest] = replace(record, state=RefreshState.REVOKED)
            self.audit_intents.append(audit)
            return len(session_ids)

    def save_mfa_factor(self, *, factor: MfaFactor, audit: AuditIntent) -> None:
        with self._lock:
            previous = self._factors.get(factor.user_id)
            if previous is not None:
                self._factors[factor.user_id] = replace(
                    previous,
                    state=MfaState.REVOKED,
                )
            self._factors[factor.user_id] = factor
            self.audit_intents.append(audit)

    def record_audit(self, audit: AuditIntent) -> None:
        with self._lock:
            self.audit_intents.append(audit)


def _same_session_binding(current: SessionRecord, expected: SessionRecord) -> bool:
    return (
        current.session_id == expected.session_id
        and current.family_id == expected.family_id
        and current.user_id == expected.user_id
        and current.tenant_id == expected.tenant_id
        and current.school_id == expected.school_id
        and current.mfa_verified == expected.mfa_verified
        and current.issued_at == expected.issued_at
        and current.expires_at == expected.expires_at
    )


class InMemoryLoginRateLimiter:
    def __init__(
        self,
        *,
        account_limit: int = 5,
        source_limit: int = 20,
        window: timedelta = timedelta(minutes=5),
    ) -> None:
        self._account_limit = account_limit
        self._source_limit = source_limit
        self._window = window
        self._accounts: dict[bytes, list[datetime]] = defaultdict(list)
        self._sources: dict[str, list[datetime]] = defaultdict(list)
        self._lock = RLock()

    def check(self, *, account_key: bytes, source_key: str, now: datetime) -> int | None:
        with self._lock:
            account = self._active(self._accounts[account_key], now)
            source = self._active(self._sources[source_key], now)
            self._accounts[account_key] = account
            self._sources[source_key] = source
            if len(account) >= self._account_limit or len(source) >= self._source_limit:
                oldest = min((account + source), default=now)
                return max(1, int((oldest + self._window - now).total_seconds()))
            return None

    def failure(self, *, account_key: bytes, source_key: str, now: datetime) -> None:
        with self._lock:
            self._accounts[account_key].append(now)
            self._sources[source_key].append(now)

    def success(self, *, account_key: bytes, source_key: str) -> None:
        with self._lock:
            del source_key
            self._accounts.pop(account_key, None)

    def _active(self, values: list[datetime], now: datetime) -> list[datetime]:
        cutoff = now - self._window
        return [value for value in values if value > cutoff]


class UnavailableAuthRepository:
    def __getattr__(self, _: str) -> object:
        raise RuntimeError("AUTH_DEPENDENCY_UNAVAILABLE")


class UnavailableLoginRateLimiter:
    def check(self, *, account_key: bytes, source_key: str, now: datetime) -> int | None:
        del account_key, source_key, now
        raise RuntimeError("AUTH_RATE_LIMIT_UNAVAILABLE")

    def failure(self, *, account_key: bytes, source_key: str, now: datetime) -> None:
        del account_key, source_key, now
        raise RuntimeError("AUTH_RATE_LIMIT_UNAVAILABLE")

    def success(self, *, account_key: bytes, source_key: str) -> None:
        del account_key, source_key
        raise RuntimeError("AUTH_RATE_LIMIT_UNAVAILABLE")
