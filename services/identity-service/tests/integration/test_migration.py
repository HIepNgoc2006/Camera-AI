from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from camera_ai_audit import AuditIntent, IntentResult
from identity_service.domain.auth import (
    RefreshRecord,
    RefreshRotationResult,
    SessionRecord,
)
from identity_service.infrastructure.repository import PostgresAuthRepository
from identity_service.infrastructure.tables import audit_outbox, refresh_tokens, sessions
from sqlalchemy.engine import make_url

SERVICE_ROOT = Path(__file__).resolve().parents[2]


def _database_uri() -> str:
    raw = os.environ.get("IDENTITY_DATABASE_URI", "").strip()
    if not raw:
        pytest.skip("IDENTITY_DATABASE_URI is not set for an isolated integration database")
    url = make_url(raw)
    if (
        url.drivername != "postgresql+psycopg"
        or url.host not in {"127.0.0.1", "localhost"}
        or url.port != 55432
        or url.database != "Camera_AI_test"
    ):
        pytest.fail(
            "identity integration database must use postgresql+psycopg on "
            "loopback:55432 with exact database Camera_AI_test"
        )
    return raw


def test_identity_migration_applies_and_rolls_back_in_isolated_database() -> None:
    database_uri = _database_uri()
    config = Config(str(SERVICE_ROOT / "alembic.ini"))
    engine = sa.create_engine(database_uri)
    try:
        command.downgrade(config, "base")
        command.upgrade(config, "20260728_0001")
        issued_at = datetime(2030, 1, 1, 12, 0, tzinfo=UTC)
        user_id = UUID("00000000-0000-4000-8000-000000000301")
        tenant_id = UUID("00000000-0000-4000-8000-000000000101")
        session_id = UUID("00000000-0000-4000-8000-000000000501")
        with engine.begin() as connection:
            connection.execute(
                sa.text(
                    "INSERT INTO identity.users "
                    "(user_id, tenant_id, school_id, login_lookup_digest, status, created_at) "
                    "VALUES (:user_id, :tenant_id, NULL, :digest, 'active', :created_at)"
                ),
                {
                    "user_id": user_id,
                    "tenant_id": tenant_id,
                    "digest": b"s" * 32,
                    "created_at": issued_at,
                },
            )
            connection.execute(
                sa.text(
                    "INSERT INTO identity.sessions "
                    "(session_id, family_id, user_id, tenant_id, school_id, mfa_verified, "
                    "issued_at, expires_at, revoked_at) VALUES "
                    "(:session_id, :family_id, :user_id, :tenant_id, NULL, false, "
                    ":issued_at, :expires_at, NULL)"
                ),
                {
                    "session_id": session_id,
                    "family_id": UUID("00000000-0000-4000-8000-000000000502"),
                    "user_id": user_id,
                    "tenant_id": tenant_id,
                    "issued_at": issued_at,
                    "expires_at": issued_at + timedelta(days=30),
                },
            )
        command.upgrade(config, "head")
        with engine.connect() as connection:
            inspector = sa.inspect(connection)
            table_names = set(inspector.get_table_names(schema="identity"))
            session_columns = {
                column["name"] for column in inspector.get_columns("sessions", schema="identity")
            }
            session_checks = {
                constraint["name"]
                for constraint in inspector.get_check_constraints("sessions", schema="identity")
            }
            session_indexes = {
                index["name"] for index in inspector.get_indexes("sessions", schema="identity")
            }
            migrated_activity = connection.execute(
                sa.text(
                    "SELECT last_activity_at, inactivity_expires_at "
                    "FROM identity.sessions WHERE session_id = :session_id"
                ),
                {"session_id": session_id},
            ).one()
        assert table_names == {
            "audit_outbox",
            "credentials",
            "mfa_factors",
            "refresh_tokens",
            "roles",
            "sessions",
            "user_role_assignments",
            "users",
        }
        assert {"last_activity_at", "inactivity_expires_at"} <= session_columns
        assert "ck_identity_sessions_activity_window" in session_checks
        assert "ix_identity_sessions_activity_active" in session_indexes
        assert migrated_activity.last_activity_at == issued_at
        assert migrated_activity.inactivity_expires_at == issued_at

        active_session = SessionRecord(
            session_id=UUID("00000000-0000-4000-8000-000000000601"),
            family_id=UUID("00000000-0000-4000-8000-000000000602"),
            user_id=user_id,
            tenant_id=tenant_id,
            school_id=None,
            mfa_verified=False,
            issued_at=issued_at,
            last_activity_at=issued_at,
            inactivity_expires_at=issued_at + timedelta(minutes=15),
            expires_at=issued_at + timedelta(hours=1),
        )
        previous_refresh = RefreshRecord(
            refresh_id=UUID("00000000-0000-4000-8000-000000000603"),
            session_id=active_session.session_id,
            family_id=active_session.family_id,
            token_hash=b"r" * 32,
            issued_at=issued_at,
            expires_at=active_session.expires_at,
        )
        with engine.begin() as connection:
            connection.execute(
                sessions.insert().values(
                    session_id=active_session.session_id,
                    family_id=active_session.family_id,
                    user_id=active_session.user_id,
                    tenant_id=active_session.tenant_id,
                    school_id=active_session.school_id,
                    mfa_verified=active_session.mfa_verified,
                    issued_at=active_session.issued_at,
                    last_activity_at=active_session.last_activity_at,
                    inactivity_expires_at=active_session.inactivity_expires_at,
                    expires_at=active_session.expires_at,
                    revoked_at=None,
                )
            )
            connection.execute(
                refresh_tokens.insert().values(
                    refresh_id=previous_refresh.refresh_id,
                    session_id=previous_refresh.session_id,
                    family_id=previous_refresh.family_id,
                    token_hash=previous_refresh.token_hash,
                    state=previous_refresh.state.value,
                    issued_at=previous_refresh.issued_at,
                    expires_at=previous_refresh.expires_at,
                    rotated_at=None,
                )
            )

        repository = PostgresAuthRepository(engine)
        activity_at = issued_at + timedelta(minutes=5)
        activity_expiry = issued_at + timedelta(minutes=20)
        touched = repository.touch_session_activity(
            expected=active_session,
            activity_at=activity_at,
            inactivity_expires_at=activity_expiry,
        )
        assert touched is not None
        assert touched.last_activity_at == activity_at
        assert touched.inactivity_expires_at == activity_expiry

        replacement_refresh = RefreshRecord(
            refresh_id=UUID("00000000-0000-4000-8000-000000000604"),
            session_id=active_session.session_id,
            family_id=active_session.family_id,
            token_hash=b"n" * 32,
            issued_at=issued_at + timedelta(minutes=6),
            expires_at=active_session.expires_at,
        )
        rotation = repository.rotate_refresh(
            previous=previous_refresh,
            replacement=replacement_refresh,
            expected_session=touched,
            rotated_at=issued_at + timedelta(minutes=6),
            inactivity_expires_at=issued_at + timedelta(minutes=21),
        )
        assert rotation is RefreshRotationResult.ROTATED
        replay = repository.rotate_refresh(
            previous=previous_refresh,
            replacement=replacement_refresh,
            expected_session=touched,
            rotated_at=issued_at + timedelta(minutes=7),
            inactivity_expires_at=issued_at + timedelta(minutes=22),
        )
        assert replay is RefreshRotationResult.REPLAYED

        revoke_at = issued_at + timedelta(minutes=8)
        audit = AuditIntent(
            source_service="identity-service",
            source_event_id=UUID("00000000-0000-4000-8000-000000000701"),
            action="SESSION_REVOKED",
            resource_type="session",
            request_id="req_scope_test_0001",
            result=IntentResult.SUCCESS,
            occurred_at=revoke_at,
            resource_id=active_session.session_id,
        )
        with engine.connect() as connection:
            audits_before = connection.execute(
                sa.select(sa.func.count()).select_from(audit_outbox)
            ).scalar_one()
        for wrong_tenant, wrong_school in (
            (UUID("00000000-0000-4000-8000-000000000102"), None),
            (tenant_id, UUID("00000000-0000-4000-8000-000000000201")),
        ):
            assert not repository.revoke_session(
                session_id=active_session.session_id,
                tenant_id=wrong_tenant,
                school_id=wrong_school,
                revoked_at=revoke_at,
                audit=audit,
            )
            with engine.connect() as connection:
                assert (
                    connection.execute(
                        sa.select(sessions.c.revoked_at).where(
                            sessions.c.session_id == active_session.session_id
                        )
                    ).scalar_one()
                    is None
                )
                assert (
                    connection.execute(
                        sa.select(refresh_tokens.c.state).where(
                            refresh_tokens.c.refresh_id == replacement_refresh.refresh_id
                        )
                    ).scalar_one()
                    == "active"
                )
                assert (
                    connection.execute(
                        sa.select(sa.func.count()).select_from(audit_outbox)
                    ).scalar_one()
                    == audits_before
                )
        assert repository.revoke_session(
            session_id=active_session.session_id,
            tenant_id=tenant_id,
            school_id=None,
            revoked_at=revoke_at,
            audit=audit,
        )
        with engine.connect() as connection:
            assert (
                connection.execute(
                    sa.select(refresh_tokens.c.state).where(
                        refresh_tokens.c.refresh_id == replacement_refresh.refresh_id
                    )
                ).scalar_one()
                == "revoked"
            )
            assert (
                connection.execute(
                    sa.select(sa.func.count()).select_from(audit_outbox)
                ).scalar_one()
                == audits_before + 1
            )
        assert (
            repository.touch_session_activity(
                expected=active_session,
                activity_at=issued_at + timedelta(minutes=9),
                inactivity_expires_at=issued_at + timedelta(minutes=24),
            )
            is None
        )

        command.downgrade(config, "20260728_0001")
        with engine.connect() as connection:
            active_after_policy_rollback = connection.execute(
                sa.text("SELECT count(*) FROM identity.sessions WHERE revoked_at IS NULL")
            ).scalar_one()
        assert active_after_policy_rollback == 0

        command.downgrade(config, "base")
        with engine.connect() as connection:
            assert "identity" not in sa.inspect(connection).get_schema_names()
    finally:
        try:
            # Leave the isolated test database at the current schema even if an
            # assertion between downgrade and verification fails.
            command.upgrade(config, "head")
        finally:
            engine.dispose()
