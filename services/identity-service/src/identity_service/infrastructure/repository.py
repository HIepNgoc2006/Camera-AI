"""PostgreSQL authentication repository with transactional audit outbox."""

from __future__ import annotations

from datetime import datetime
from uuid import NAMESPACE_URL, UUID, uuid5

import sqlalchemy as sa
from camera_ai_audit import AuditIntent
from sqlalchemy import Engine

from identity_service.application.errors import AuthenticationError
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
from identity_service.infrastructure.tables import (
    audit_outbox,
    credentials,
    mfa_factors,
    refresh_tokens,
    roles,
    sessions,
    user_role_assignments,
    users,
)


class PostgresAuthRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def login_subject(self, *, tenant_id: UUID, login_digest: bytes) -> LoginSubject | None:
        try:
            with self._engine.connect() as connection:
                active_roles = (
                    sa.select(sa.func.array_agg(roles.c.code))
                    .select_from(
                        user_role_assignments.join(
                            roles, roles.c.role_id == user_role_assignments.c.role_id
                        )
                    )
                    .where(
                        user_role_assignments.c.user_id == users.c.user_id,
                        user_role_assignments.c.revoked_at.is_(None),
                        roles.c.status == "active",
                    )
                    .scalar_subquery()
                )
                row = (
                    connection.execute(
                        sa.select(
                            users.c.user_id,
                            users.c.tenant_id,
                            users.c.school_id,
                            users.c.status,
                            credentials.c.password_hash,
                            active_roles.label("role_codes"),
                        )
                        .select_from(
                            users.join(
                                credentials,
                                credentials.c.user_id == users.c.user_id,
                            )
                        )
                        .where(
                            users.c.tenant_id == tenant_id,
                            users.c.login_lookup_digest == login_digest,
                        )
                    )
                    .mappings()
                    .first()
                )
                if row is None:
                    return None
                role_values = row["role_codes"]
                role_codes = (
                    frozenset()
                    if role_values is None
                    else frozenset(str(code) for code in role_values)
                )
                if not role_codes:
                    return None
                return LoginSubject(
                    user_id=row["user_id"],
                    tenant_id=row["tenant_id"],
                    school_id=row["school_id"],
                    status=UserStatus(str(row["status"])),
                    password_hash=str(row["password_hash"]),
                    role_codes=role_codes,
                )
        except AuthenticationError:
            raise
        except Exception:
            raise AuthenticationError("AUTH_DEPENDENCY_UNAVAILABLE") from None

    def active_mfa_factor(self, *, user_id: UUID) -> MfaFactor | None:
        try:
            with self._engine.connect() as connection:
                row = (
                    connection.execute(
                        sa.select(mfa_factors)
                        .where(
                            mfa_factors.c.user_id == user_id,
                            mfa_factors.c.state == MfaState.ACTIVE.value,
                        )
                        .order_by(mfa_factors.c.verified_at.desc())
                        .limit(1)
                    )
                    .mappings()
                    .first()
                )
                return None if row is None else _mfa(row)
        except Exception:
            raise AuthenticationError("AUTH_DEPENDENCY_UNAVAILABLE") from None

    def create_session(
        self,
        *,
        session: SessionRecord,
        refresh: RefreshRecord,
        audit: AuditIntent,
    ) -> None:
        try:
            with self._engine.begin() as connection:
                connection.execute(sessions.insert().values(**_session_values(session)))
                connection.execute(refresh_tokens.insert().values(**_refresh_values(refresh)))
                _record_audit(connection, audit)
        except Exception:
            raise AuthenticationError("AUTH_DEPENDENCY_UNAVAILABLE") from None

    def refresh_record(self, token_hash: bytes) -> RefreshRecord | None:
        try:
            with self._engine.connect() as connection:
                row = (
                    connection.execute(
                        sa.select(refresh_tokens).where(refresh_tokens.c.token_hash == token_hash)
                    )
                    .mappings()
                    .first()
                )
                return None if row is None else _refresh(row)
        except Exception:
            raise AuthenticationError("AUTH_DEPENDENCY_UNAVAILABLE") from None

    def session(self, session_id: UUID) -> SessionRecord | None:
        try:
            with self._engine.connect() as connection:
                row = (
                    connection.execute(
                        sa.select(sessions).where(sessions.c.session_id == session_id)
                    )
                    .mappings()
                    .first()
                )
                return None if row is None else _session(row)
        except Exception:
            raise AuthenticationError("AUTH_DEPENDENCY_UNAVAILABLE") from None

    def active_session(
        self, *, expected: SessionRecord, observed_at: datetime
    ) -> SessionRecord | None:
        try:
            with self._engine.connect() as connection:
                row = (
                    connection.execute(
                        sa.select(sessions).where(
                            *_session_binding_predicates(expected),
                            sessions.c.revoked_at.is_(None),
                            sessions.c.expires_at > observed_at,
                            sessions.c.inactivity_expires_at > observed_at,
                        )
                    )
                    .mappings()
                    .first()
                )
                return None if row is None else _session(row)
        except Exception:
            raise AuthenticationError("AUTH_DEPENDENCY_UNAVAILABLE") from None

    def touch_session_activity(
        self,
        *,
        expected: SessionRecord,
        activity_at: datetime,
        inactivity_expires_at: datetime,
    ) -> SessionRecord | None:
        if inactivity_expires_at <= activity_at:
            return None
        try:
            with self._engine.begin() as connection:
                row = (
                    connection.execute(
                        sessions.update()
                        .where(
                            *_session_binding_predicates(expected),
                            sessions.c.revoked_at.is_(None),
                            sessions.c.expires_at > activity_at,
                            sessions.c.inactivity_expires_at > activity_at,
                            sessions.c.last_activity_at <= activity_at,
                            sessions.c.expires_at >= inactivity_expires_at,
                        )
                        .values(
                            last_activity_at=activity_at,
                            inactivity_expires_at=inactivity_expires_at,
                        )
                        .returning(*sessions.c)
                    )
                    .mappings()
                    .first()
                )
                return None if row is None else _session(row)
        except Exception:
            raise AuthenticationError("AUTH_DEPENDENCY_UNAVAILABLE") from None

    def role_codes(self, user_id: UUID) -> frozenset[str]:
        try:
            with self._engine.connect() as connection:
                values = connection.execute(
                    sa.select(roles.c.code)
                    .select_from(
                        user_role_assignments.join(
                            roles, roles.c.role_id == user_role_assignments.c.role_id
                        ).join(users, users.c.user_id == user_role_assignments.c.user_id)
                    )
                    .where(
                        user_role_assignments.c.user_id == user_id,
                        user_role_assignments.c.revoked_at.is_(None),
                        roles.c.status == "active",
                        users.c.status == UserStatus.ACTIVE.value,
                    )
                ).scalars()
                return frozenset(str(value) for value in values)
        except Exception:
            raise AuthenticationError("AUTH_DEPENDENCY_UNAVAILABLE") from None

    def rotate_refresh(
        self,
        *,
        previous: RefreshRecord,
        replacement: RefreshRecord,
        expected_session: SessionRecord,
        rotated_at: datetime,
        inactivity_expires_at: datetime,
    ) -> RefreshRotationResult:
        if (
            inactivity_expires_at <= rotated_at
            or previous.session_id != expected_session.session_id
            or previous.family_id != expected_session.family_id
            or replacement.session_id != expected_session.session_id
            or replacement.family_id != expected_session.family_id
        ):
            return RefreshRotationResult.INACTIVE
        try:
            with self._engine.begin() as connection:
                # All revocation paths lock session state before refresh state. Keep
                # that order here to avoid a refresh/logout deadlock.
                session_row = (
                    connection.execute(
                        sa.select(
                            sessions.c.revoked_at,
                            sessions.c.expires_at,
                            sessions.c.inactivity_expires_at,
                            sessions.c.last_activity_at,
                        )
                        .where(*_session_binding_predicates(expected_session))
                        .with_for_update()
                    )
                    .mappings()
                    .first()
                )
                if (
                    session_row is None
                    or session_row["revoked_at"] is not None
                    or session_row["expires_at"] <= rotated_at
                    or session_row["inactivity_expires_at"] <= rotated_at
                    or session_row["last_activity_at"] > rotated_at
                    or session_row["expires_at"] < inactivity_expires_at
                ):
                    return RefreshRotationResult.INACTIVE
                current_state = connection.execute(
                    sa.select(refresh_tokens.c.state)
                    .where(refresh_tokens.c.refresh_id == previous.refresh_id)
                    .with_for_update()
                ).scalar_one_or_none()
                if current_state == RefreshState.ROTATED.value:
                    return RefreshRotationResult.REPLAYED
                if current_state != RefreshState.ACTIVE.value:
                    return RefreshRotationResult.INACTIVE
                connection.execute(
                    sessions.update()
                    .where(sessions.c.session_id == previous.session_id)
                    .values(
                        last_activity_at=rotated_at,
                        inactivity_expires_at=inactivity_expires_at,
                    )
                )
                connection.execute(
                    refresh_tokens.update()
                    .where(refresh_tokens.c.refresh_id == previous.refresh_id)
                    .values(state=RefreshState.ROTATED.value, rotated_at=rotated_at)
                )
                connection.execute(refresh_tokens.insert().values(**_refresh_values(replacement)))
                return RefreshRotationResult.ROTATED
        except Exception:
            raise AuthenticationError("AUTH_DEPENDENCY_UNAVAILABLE") from None

    def revoke_family(self, *, family_id: UUID, revoked_at: datetime, audit: AuditIntent) -> None:
        try:
            with self._engine.begin() as connection:
                connection.execute(
                    sessions.update()
                    .where(sessions.c.family_id == family_id, sessions.c.revoked_at.is_(None))
                    .values(revoked_at=revoked_at)
                )
                connection.execute(
                    refresh_tokens.update()
                    .where(
                        refresh_tokens.c.family_id == family_id,
                        refresh_tokens.c.state != RefreshState.REVOKED.value,
                    )
                    .values(state=RefreshState.REVOKED.value)
                )
                _record_audit(connection, audit)
        except Exception:
            raise AuthenticationError("AUTH_DEPENDENCY_UNAVAILABLE") from None

    def revoke_session(
        self,
        *,
        session_id: UUID,
        tenant_id: UUID,
        school_id: UUID | None,
        revoked_at: datetime,
        audit: AuditIntent,
    ) -> bool:
        try:
            with self._engine.begin() as connection:
                found = connection.execute(
                    sessions.update()
                    .where(
                        sessions.c.session_id == session_id,
                        sessions.c.tenant_id == tenant_id,
                        sessions.c.school_id.is_not_distinct_from(school_id),
                    )
                    .values(revoked_at=sa.func.coalesce(sessions.c.revoked_at, revoked_at))
                )
                if found.rowcount != 1:
                    return False
                connection.execute(
                    refresh_tokens.update()
                    .where(
                        refresh_tokens.c.session_id == session_id,
                        refresh_tokens.c.state == RefreshState.ACTIVE.value,
                    )
                    .values(state=RefreshState.REVOKED.value)
                )
                _record_audit(connection, audit)
                return True
        except Exception:
            raise AuthenticationError("AUTH_DEPENDENCY_UNAVAILABLE") from None

    def revoke_user_sessions(
        self, *, user_id: UUID, revoked_at: datetime, audit: AuditIntent
    ) -> int:
        try:
            with self._engine.begin() as connection:
                session_ids = tuple(
                    connection.execute(
                        sa.select(sessions.c.session_id).where(
                            sessions.c.user_id == user_id,
                            sessions.c.revoked_at.is_(None),
                        )
                    ).scalars()
                )
                if session_ids:
                    connection.execute(
                        sessions.update()
                        .where(sessions.c.session_id.in_(session_ids))
                        .values(revoked_at=revoked_at)
                    )
                    connection.execute(
                        refresh_tokens.update()
                        .where(
                            refresh_tokens.c.session_id.in_(session_ids),
                            refresh_tokens.c.state == RefreshState.ACTIVE.value,
                        )
                        .values(state=RefreshState.REVOKED.value)
                    )
                _record_audit(connection, audit)
                return len(session_ids)
        except Exception:
            raise AuthenticationError("AUTH_DEPENDENCY_UNAVAILABLE") from None

    def save_mfa_factor(self, *, factor: MfaFactor, audit: AuditIntent) -> None:
        try:
            with self._engine.begin() as connection:
                connection.execute(
                    mfa_factors.update()
                    .where(
                        mfa_factors.c.user_id == factor.user_id,
                        mfa_factors.c.state != MfaState.REVOKED.value,
                    )
                    .values(state=MfaState.REVOKED.value)
                )
                connection.execute(
                    mfa_factors.insert().values(
                        factor_id=factor.factor_id,
                        user_id=factor.user_id,
                        tenant_id=factor.tenant_id,
                        secret_ciphertext=factor.secret_ciphertext,
                        state=factor.state.value,
                        created_at=factor.created_at,
                        verified_at=factor.verified_at,
                    )
                )
                _record_audit(connection, audit)
        except Exception:
            raise AuthenticationError("AUTH_DEPENDENCY_UNAVAILABLE") from None

    def record_audit(self, audit: AuditIntent) -> None:
        try:
            with self._engine.begin() as connection:
                _record_audit(connection, audit)
        except Exception:
            raise AuthenticationError("AUTH_DEPENDENCY_UNAVAILABLE") from None


def _record_audit(connection: sa.Connection, audit: AuditIntent) -> None:
    connection.execute(
        audit_outbox.insert().values(
            audit_outbox_id=uuid5(
                NAMESPACE_URL,
                f"camera-ai:audit-outbox:{audit.source_service}:{audit.source_event_id}",
            ),
            source_service=audit.source_service,
            source_event_id=audit.source_event_id,
            school_id=audit.school_id,
            payload=audit.publisher_payload(),
            publish_status="pending",
            attempt_count=0,
            next_attempt_at=audit.occurred_at,
            recorded_at=audit.occurred_at,
            delivered_at=None,
        )
    )


def _session_values(value: SessionRecord) -> dict[str, object]:
    return {
        "session_id": value.session_id,
        "family_id": value.family_id,
        "user_id": value.user_id,
        "tenant_id": value.tenant_id,
        "school_id": value.school_id,
        "mfa_verified": value.mfa_verified,
        "issued_at": value.issued_at,
        "last_activity_at": value.last_activity_at,
        "inactivity_expires_at": value.inactivity_expires_at,
        "expires_at": value.expires_at,
        "revoked_at": value.revoked_at,
    }


def _session_binding_predicates(value: SessionRecord) -> tuple[sa.ColumnElement[bool], ...]:
    return (
        sessions.c.session_id == value.session_id,
        sessions.c.family_id == value.family_id,
        sessions.c.user_id == value.user_id,
        sessions.c.tenant_id == value.tenant_id,
        sessions.c.school_id.is_not_distinct_from(value.school_id),
        sessions.c.mfa_verified == value.mfa_verified,
        sessions.c.issued_at == value.issued_at,
        sessions.c.expires_at == value.expires_at,
    )


def _refresh_values(value: RefreshRecord) -> dict[str, object]:
    return {
        "refresh_id": value.refresh_id,
        "session_id": value.session_id,
        "family_id": value.family_id,
        "token_hash": value.token_hash,
        "state": value.state.value,
        "issued_at": value.issued_at,
        "expires_at": value.expires_at,
        "rotated_at": value.rotated_at,
    }


def _session(row: sa.RowMapping) -> SessionRecord:
    return SessionRecord(
        session_id=row["session_id"],
        family_id=row["family_id"],
        user_id=row["user_id"],
        tenant_id=row["tenant_id"],
        school_id=row["school_id"],
        mfa_verified=bool(row["mfa_verified"]),
        issued_at=row["issued_at"],
        last_activity_at=row["last_activity_at"],
        inactivity_expires_at=row["inactivity_expires_at"],
        expires_at=row["expires_at"],
        revoked_at=row["revoked_at"],
    )


def _refresh(row: sa.RowMapping) -> RefreshRecord:
    return RefreshRecord(
        refresh_id=row["refresh_id"],
        session_id=row["session_id"],
        family_id=row["family_id"],
        token_hash=bytes(row["token_hash"]),
        state=RefreshState(str(row["state"])),
        issued_at=row["issued_at"],
        expires_at=row["expires_at"],
        rotated_at=row["rotated_at"],
    )


def _mfa(row: sa.RowMapping) -> MfaFactor:
    return MfaFactor(
        factor_id=row["factor_id"],
        user_id=row["user_id"],
        tenant_id=row["tenant_id"],
        secret_ciphertext=bytes(row["secret_ciphertext"]),
        state=MfaState(str(row["state"])),
        created_at=row["created_at"],
        verified_at=row["verified_at"],
    )
