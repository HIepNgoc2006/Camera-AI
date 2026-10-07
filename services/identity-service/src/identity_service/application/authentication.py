"""Authentication, rotation, revocation and MFA application use cases."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal, Never
from uuid import UUID, uuid4

from camera_ai_audit import AuditIntent, IntentResult

from identity_service.application.errors import AuthenticationError
from identity_service.application.ports import (
    AccessTokenCodec,
    AuthRepository,
    LoginRateLimiter,
    MfaProtector,
    PasswordVerifier,
    TotpVerifier,
)
from identity_service.domain.auth import (
    AuthDomainError,
    MfaFactor,
    MfaState,
    RefreshRecord,
    RefreshRotationResult,
    RefreshState,
    SessionRecord,
)
from identity_service.domain.models import UserStatus
from identity_service.infrastructure.security import LoginLookupHasher

ADMIN_ROLE_CODES = frozenset({"admin", "school_admin", "system_admin"})
MFA_REQUIRED_ROLES = ADMIN_ROLE_CODES | {"bgh"}
IDENTITY_SESSION_SNAPSHOT_VERSION: Literal["identity_session_snapshot_v1"] = (
    "identity_session_snapshot_v1"
)


@dataclass(frozen=True, slots=True)
class TokenPair:
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int
    session_id: UUID
    mfa_verified: bool


@dataclass(frozen=True, slots=True)
class VerifiedAccess:
    user_id: UUID
    session_id: UUID
    tenant_id: UUID
    school_id: UUID | None
    roles: frozenset[str]
    mfa_verified: bool
    issued_at: datetime
    absolute_expires_at: datetime
    inactivity_expires_at: datetime


@dataclass(frozen=True, slots=True)
class IdentitySessionSnapshot:
    policy_version: Literal["identity_session_snapshot_v1"]
    status: Literal["authenticated"]
    session_id: UUID
    actor_id: UUID
    tenant_id: UUID
    school_id: UUID | None
    mfa_state: Literal["verified", "not_required"]
    issued_at: datetime
    absolute_expires_at: datetime
    inactivity_expires_at: datetime


class AuthenticationService:
    """Fail-closed coordinator; credential values never enter audit or logs."""

    def __init__(
        self,
        *,
        repository: AuthRepository,
        limiter: LoginRateLimiter,
        lookup: LoginLookupHasher,
        passwords: PasswordVerifier,
        tokens: AccessTokenCodec,
        mfa: MfaProtector,
        totp: TotpVerifier,
        access_lifetime: timedelta = timedelta(minutes=5),
        session_lifetime: timedelta = timedelta(days=30),
        inactivity_lifetime: timedelta = timedelta(minutes=30),
    ) -> None:
        if (
            access_lifetime <= timedelta(0)
            or session_lifetime <= timedelta(0)
            or inactivity_lifetime <= timedelta(0)
            or inactivity_lifetime > session_lifetime
        ):
            raise ValueError("authentication lifetimes must be positive and bounded")
        self._repository = repository
        self._limiter = limiter
        self._lookup = lookup
        self._passwords = passwords
        self._tokens = tokens
        self._mfa = mfa
        self._totp = totp
        self._access_lifetime = access_lifetime
        self._session_lifetime = session_lifetime
        self._inactivity_lifetime = inactivity_lifetime

    def login(
        self,
        *,
        tenant_id: UUID,
        identifier: str,
        password: str,
        source_key: str,
        request_id: str,
        mfa_code: str | None = None,
        now: datetime | None = None,
    ) -> TokenPair:
        at = _now(now)
        account_key = self._lookup.digest(identifier, tenant_id=tenant_id)
        retry_after = self._checked_limit(account_key=account_key, source_key=source_key, now=at)
        if retry_after is not None:
            self._repository.record_audit(
                _audit(
                    action="AUTH_LOGIN_FAILED",
                    resource_type="user",
                    request_id=request_id,
                    result=IntentResult.DENIED,
                    reason_code="AUTH_RATE_LIMITED",
                    occurred_at=at,
                )
            )
            raise AuthenticationError("AUTH_RATE_LIMITED", retry_after=retry_after)

        subject = self._repository.login_subject(tenant_id=tenant_id, login_digest=account_key)
        candidate_hash = self._passwords.dummy_hash if subject is None else subject.password_hash
        valid_password = self._passwords.verify(candidate_hash, password)
        if subject is None or not valid_password or subject.status is not UserStatus.ACTIVE:
            self._limiter.failure(account_key=account_key, source_key=source_key, now=at)
            self._repository.record_audit(
                _audit(
                    action="AUTH_LOGIN_FAILED",
                    resource_type="user",
                    request_id=request_id,
                    result=IntentResult.DENIED,
                    reason_code="AUTH_CREDENTIAL_INVALID",
                    occurred_at=at,
                )
            )
            raise AuthenticationError("AUTH_CREDENTIAL_INVALID")

        requires_mfa = bool(subject.role_codes & MFA_REQUIRED_ROLES)
        mfa_verified = False
        if requires_mfa:
            factor = self._repository.active_mfa_factor(user_id=subject.user_id)
            if factor is None or mfa_code is None or factor.state is not MfaState.ACTIVE:
                self._failed_mfa(account_key, source_key, request_id, at)
            secret = self._mfa.reveal(factor)
            try:
                if not self._totp.verify(secret=secret, code=mfa_code, now=at):
                    self._failed_mfa(account_key, source_key, request_id, at)
            finally:
                del secret
            mfa_verified = True

        session = SessionRecord(
            session_id=uuid4(),
            family_id=uuid4(),
            user_id=subject.user_id,
            tenant_id=subject.tenant_id,
            school_id=subject.school_id,
            mfa_verified=mfa_verified,
            issued_at=at,
            last_activity_at=at,
            inactivity_expires_at=at + self._inactivity_lifetime,
            expires_at=at + self._session_lifetime,
        )
        raw_refresh = _new_refresh_token()
        refresh = _refresh_record(raw_refresh, session=session, now=at)
        self._repository.create_session(
            session=session,
            refresh=refresh,
            audit=_audit(
                action="AUTH_LOGIN_SUCCEEDED",
                resource_type="session",
                request_id=request_id,
                result=IntentResult.SUCCESS,
                occurred_at=at,
                resource_id=session.session_id,
                school_id=session.school_id,
            ),
        )
        self._limiter.success(account_key=account_key, source_key=source_key)
        return self._pair(session=session, roles=subject.role_codes, refresh=raw_refresh, now=at)

    def refresh(
        self, *, refresh_token: str, request_id: str, now: datetime | None = None
    ) -> TokenPair:
        at = _now(now)
        token_hash = _refresh_hash(refresh_token)
        stored = self._repository.refresh_record(token_hash)
        if stored is None:
            raise AuthenticationError("AUTHENTICATION_REQUIRED")
        session = self._repository.session(stored.session_id)
        if stored.state is RefreshState.ROTATED:
            self._revoke_replayed_family(stored, request_id=request_id, now=at)
        if stored.state is RefreshState.REVOKED:
            raise AuthenticationError("AUTHENTICATION_REQUIRED")
        if session is None or not session.is_active(at) or at >= stored.expires_at:
            raise AuthenticationError("AUTHENTICATION_REQUIRED")

        touched = self._touched_session(session, at=at)
        replacement_raw = _new_refresh_token()
        replacement = _refresh_record(replacement_raw, session=touched, now=at)
        rotation = self._repository.rotate_refresh(
            previous=stored,
            replacement=replacement,
            expected_session=touched,
            rotated_at=at,
            inactivity_expires_at=touched.inactivity_expires_at,
        )
        if rotation is RefreshRotationResult.REPLAYED:
            self._revoke_replayed_family(stored, request_id=request_id, now=at)
        if rotation is RefreshRotationResult.INACTIVE:
            raise AuthenticationError("AUTHENTICATION_REQUIRED")
        roles = self._repository.role_codes(touched.user_id)
        if not roles or (roles & MFA_REQUIRED_ROLES and not touched.mfa_verified):
            self._repository.revoke_family(
                family_id=touched.family_id,
                revoked_at=at,
                audit=_session_revoke_audit(touched.session_id, request_id=request_id, now=at),
            )
            raise AuthenticationError("AUTHENTICATION_REQUIRED")
        return self._pair(session=touched, roles=roles, refresh=replacement_raw, now=at)

    def verify_access(
        self,
        access_token: str,
        *,
        expected_tenant_id: UUID | None = None,
        now: datetime | None = None,
    ) -> VerifiedAccess:
        return self._verified_access(
            access_token,
            expected_tenant_id=expected_tenant_id,
            extend_inactivity=True,
            now=now,
        )

    def _verified_access(
        self,
        access_token: str,
        *,
        expected_tenant_id: UUID | None = None,
        extend_inactivity: bool,
        now: datetime | None = None,
    ) -> VerifiedAccess:
        at = _now(now)
        claims = self._tokens.verify(access_token, now=at)
        try:
            user_id = UUID(str(claims["sub"]))
            session_id = UUID(str(claims["sid"]))
            family_id = UUID(str(claims["fid"]))
            tenant_id = UUID(str(claims["tid"]))
            school_value = claims.get("school_id")
            school_id = None if school_value is None else UUID(str(school_value))
            roles_value = claims["roles"]
            if not isinstance(roles_value, list) or any(
                not isinstance(role, str) for role in roles_value
            ):
                raise ValueError
            roles = frozenset(roles_value)
            mfa_verified = claims["mfa"]
            if not isinstance(mfa_verified, bool):
                raise ValueError
        except (KeyError, TypeError, ValueError):
            raise AuthenticationError("AUTHENTICATION_REQUIRED") from None
        session = self._repository.session(session_id)
        if (
            session is None
            or not session.is_active(at)
            or session.user_id != user_id
            or session.family_id != family_id
            or session.tenant_id != tenant_id
            or session.school_id != school_id
            or session.mfa_verified != mfa_verified
            or (roles & MFA_REQUIRED_ROLES and not mfa_verified)
            or (expected_tenant_id is not None and tenant_id != expected_tenant_id)
        ):
            raise AuthenticationError("AUTHENTICATION_REQUIRED")
        current_roles = self._repository.role_codes(user_id)
        if not current_roles or current_roles != roles:
            raise AuthenticationError("AUTHENTICATION_REQUIRED")
        if extend_inactivity:
            session = self._touched_session(session, at=at)
            persisted = self._repository.touch_session_activity(
                expected=session,
                activity_at=session.last_activity_at,
                inactivity_expires_at=session.inactivity_expires_at,
            )
        else:
            persisted = self._repository.active_session(
                expected=session,
                observed_at=at,
            )
        if persisted is None:
            raise AuthenticationError("AUTHENTICATION_REQUIRED")
        return VerifiedAccess(
            user_id=user_id,
            session_id=session_id,
            tenant_id=tenant_id,
            school_id=school_id,
            roles=roles,
            mfa_verified=mfa_verified,
            issued_at=persisted.issued_at,
            absolute_expires_at=persisted.expires_at,
            inactivity_expires_at=persisted.inactivity_expires_at,
        )

    def session_snapshot(
        self, access_token: str, *, now: datetime | None = None
    ) -> IdentitySessionSnapshot:
        principal = self._verified_access(access_token, extend_inactivity=False, now=now)
        return IdentitySessionSnapshot(
            policy_version=IDENTITY_SESSION_SNAPSHOT_VERSION,
            status="authenticated",
            session_id=principal.session_id,
            actor_id=principal.user_id,
            tenant_id=principal.tenant_id,
            school_id=principal.school_id,
            mfa_state="verified" if principal.mfa_verified else "not_required",
            issued_at=principal.issued_at,
            absolute_expires_at=principal.absolute_expires_at,
            inactivity_expires_at=principal.inactivity_expires_at,
        )

    def logout(self, access_token: str, *, request_id: str, now: datetime | None = None) -> None:
        at = _now(now)
        principal = self.verify_access(access_token, now=at)
        self._repository.revoke_session(
            session_id=principal.session_id,
            tenant_id=principal.tenant_id,
            school_id=principal.school_id,
            revoked_at=at,
            audit=_session_revoke_audit(principal.session_id, request_id=request_id, now=at),
        )

    def logout_all(self, access_token: str, *, request_id: str, now: datetime | None = None) -> int:
        at = _now(now)
        principal = self.verify_access(access_token, now=at)
        return self._repository.revoke_user_sessions(
            user_id=principal.user_id,
            revoked_at=at,
            audit=_session_revoke_audit(principal.session_id, request_id=request_id, now=at),
        )

    def administrative_revoke(
        self,
        access_token: str,
        *,
        session_id: UUID,
        request_id: str,
        now: datetime | None = None,
    ) -> bool:
        at = _now(now)
        principal = self.verify_access(access_token, now=at)
        if not (principal.roles & ADMIN_ROLE_CODES) or not principal.mfa_verified:
            raise AuthenticationError("AUTHZ_DENIED")
        return self._repository.revoke_session(
            session_id=session_id,
            tenant_id=principal.tenant_id,
            school_id=principal.school_id,
            revoked_at=at,
            audit=_session_revoke_audit(session_id, request_id=request_id, now=at),
        )

    def enroll_mfa(
        self,
        access_token: str,
        *,
        secret: str,
        code: str,
        request_id: str,
        now: datetime | None = None,
    ) -> UUID:
        at = _now(now)
        principal = self.verify_access(access_token, now=at)
        if not self._totp.verify(secret=secret, code=code, now=at):
            raise AuthenticationError("AUTH_MFA_VERIFICATION_FAILED")
        factor_id = uuid4()
        factor = MfaFactor(
            factor_id=factor_id,
            user_id=principal.user_id,
            tenant_id=principal.tenant_id,
            secret_ciphertext=self._mfa.protect(
                factor_id=factor_id,
                tenant_id=principal.tenant_id,
                secret=secret,
            ),
            state=MfaState.ACTIVE,
            created_at=at,
            verified_at=at,
        )
        self._repository.save_mfa_factor(
            factor=factor,
            audit=_audit(
                action="MFA_CHANGED",
                resource_type="mfa_factor",
                request_id=request_id,
                result=IntentResult.SUCCESS,
                occurred_at=at,
                resource_id=factor_id,
                school_id=principal.school_id,
                reference_ids=(("mfa_factor_id", factor_id),),
                policy_versions=(("mfa_policy", "mfa_policy_v1"),),
            ),
        )
        return factor_id

    def _checked_limit(self, *, account_key: bytes, source_key: str, now: datetime) -> int | None:
        try:
            return self._limiter.check(account_key=account_key, source_key=source_key, now=now)
        except Exception:
            raise AuthenticationError("AUTH_RATE_LIMIT_UNAVAILABLE") from None

    def _touched_session(self, session: SessionRecord, *, at: datetime) -> SessionRecord:
        try:
            return session.touched(at=at, inactivity_lifetime=self._inactivity_lifetime)
        except AuthDomainError:
            raise AuthenticationError("AUTHENTICATION_REQUIRED") from None

    def _failed_mfa(
        self, account_key: bytes, source_key: str, request_id: str, now: datetime
    ) -> Never:
        self._limiter.failure(account_key=account_key, source_key=source_key, now=now)
        self._repository.record_audit(
            _audit(
                action="AUTH_LOGIN_FAILED",
                resource_type="user",
                request_id=request_id,
                result=IntentResult.DENIED,
                reason_code="AUTH_MFA_REQUIRED",
                occurred_at=now,
            )
        )
        raise AuthenticationError("AUTH_MFA_REQUIRED")

    def _revoke_replayed_family(
        self, stored: RefreshRecord, *, request_id: str, now: datetime
    ) -> None:
        self._repository.revoke_family(
            family_id=stored.family_id,
            revoked_at=now,
            audit=_session_revoke_audit(stored.session_id, request_id=request_id, now=now),
        )
        raise AuthenticationError("AUTH_REFRESH_REUSE_DETECTED")

    def _pair(
        self,
        *,
        session: SessionRecord,
        roles: frozenset[str],
        refresh: str,
        now: datetime,
    ) -> TokenPair:
        return TokenPair(
            access_token=self._tokens.issue(session=session, roles=roles, now=now),
            refresh_token=refresh,
            token_type="Bearer",
            expires_in=int(self._access_lifetime.total_seconds()),
            session_id=session.session_id,
            mfa_verified=session.mfa_verified,
        )


def _now(value: datetime | None) -> datetime:
    current = datetime.now(UTC) if value is None else value
    if current.tzinfo is None or current.utcoffset() is None:
        raise AuthenticationError("AUTH_DEPENDENCY_UNAVAILABLE")
    return current.astimezone(UTC)


def _new_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def _refresh_hash(token: str) -> bytes:
    if not 32 <= len(token) <= 1024 or any(character.isspace() for character in token):
        raise AuthenticationError("AUTHENTICATION_REQUIRED")
    return hashlib.sha256(b"camera-ai|refresh-v1|" + token.encode()).digest()


def _refresh_record(token: str, *, session: SessionRecord, now: datetime) -> RefreshRecord:
    return RefreshRecord(
        refresh_id=uuid4(),
        session_id=session.session_id,
        family_id=session.family_id,
        token_hash=_refresh_hash(token),
        issued_at=now,
        expires_at=session.expires_at,
    )


def _audit(
    *,
    action: str,
    resource_type: str,
    request_id: str,
    result: IntentResult,
    occurred_at: datetime,
    reason_code: str | None = None,
    resource_id: UUID | None = None,
    school_id: UUID | None = None,
    reference_ids: tuple[tuple[str, UUID], ...] = (),
    policy_versions: tuple[tuple[str, str], ...] = (),
) -> AuditIntent:
    return AuditIntent(
        source_service="identity-service",
        source_event_id=uuid4(),
        action=action,
        resource_type=resource_type,
        request_id=request_id,
        result=result,
        occurred_at=occurred_at,
        reason_code=reason_code,
        resource_id=resource_id,
        school_id=school_id,
        reference_ids=reference_ids,
        policy_versions=policy_versions,
    )


def _session_revoke_audit(session_id: UUID, *, request_id: str, now: datetime) -> AuditIntent:
    return _audit(
        action="SESSION_REVOKED",
        resource_type="session",
        request_id=request_id,
        result=IntentResult.SUCCESS,
        occurred_at=now,
        resource_id=session_id,
        reference_ids=(("session_id", session_id),),
        policy_versions=(("session_policy", "session_policy_v1"),),
    )
