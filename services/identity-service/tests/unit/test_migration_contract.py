from __future__ import annotations

import re
from pathlib import Path

MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "20260728_0001_create_identity_auth_runtime.py"
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
