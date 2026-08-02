from __future__ import annotations

import re
from pathlib import Path

MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "20260728_0001_create_identity_auth_runtime.py"
)
SESSION_EXPIRY_MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "20260802_0002_add_session_inactivity_expiry.py"
)


def test_migration_owns_only_identity_schema_and_all_auth_state() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    assert 'SCHEMA = "identity"' in source
    for table in (
        "users",
        "credentials",
        "roles",
        "user_role_assignments",
        "sessions",
        "refresh_tokens",
        "mfa_factors",
        "audit_outbox",
    ):
        assert f'"{table}"' in source
    for cross_schema in (
        "school.",
        "privacy.",
        "camera.",
        "events.",
        "audit.",
        "evidence.",
    ):
        assert re.search(rf"(?<![a-z_]){re.escape(cross_schema)}", source) is None


def test_migration_enforces_hash_encryption_revocation_and_audit_minimization() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    for marker in (
        "encv1_check_constraint",
        "octet_length(token_hash) = 32",
        "password_hash LIKE '$argon2id$%'",
        "uq_identity_refresh_hash",
        "ix_identity_sessions_user_active",
        "payload ?| ARRAY",
        "'refresh_token'",
        "'mfa_secret'",
    ):
        assert marker in source


def test_migration_has_explicit_reverse_order_downgrade() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    downgrade = source.split("def downgrade()", maxsplit=1)[1]
    positions = [
        downgrade.index(f'op.drop_table("{table}"')
        for table in (
            "audit_outbox",
            "mfa_factors",
            "refresh_tokens",
            "sessions",
            "user_role_assignments",
            "roles",
            "credentials",
            "users",
        )
    ]
    assert positions == sorted(positions)


def test_session_expiry_migration_is_fail_closed_and_bounded() -> None:
    source = SESSION_EXPIRY_MIGRATION.read_text(encoding="utf-8")
    assert 'down_revision: str | None = "20260728_0001"' in source
    assert "last_activity_at = issued_at" in source
    assert "inactivity_expires_at = issued_at" in source
    assert "issued_at <= last_activity_at" in source
    assert "last_activity_at <= inactivity_expires_at" in source
    assert "inactivity_expires_at <= expires_at" in source
    assert "ix_identity_sessions_activity_active" in source
    assert "SET revoked_at = COALESCE" in source
    assert 'op.drop_column("sessions", "inactivity_expires_at"' in source
    assert 'op.drop_column("sessions", "last_activity_at"' in source
