from __future__ import annotations

import re
from pathlib import Path

MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "20260728_0001_create_evidence_baseline.py"
)


def test_migration_owns_only_evidence_schema_and_never_models_media_or_urls() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    assert 'SCHEMA = "evidence"' in source
    for table in ("evidence_objects", "evidence_links", "audit_outbox"):
        assert f'"{table}"' in source
    for forbidden_column in (
        'sa.Column("image_binary"',
        'sa.Column("video_binary"',
        'sa.Column("image_base64"',
        'sa.Column("signed_url"',
        'sa.Column("object_key",',
    ):
        assert forbidden_column not in source
    for cross_schema in (
        "identity.",
        "school.",
        "privacy.",
        "events.",
        "audit.",
        "attendance.",
    ):
        assert re.search(rf"(?<![a-z_]){re.escape(cross_schema)}", source) is None


def test_migration_enforces_encryption_scope_lifecycle_retention_and_audit_minimization() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    for marker in (
        "encv1_check_constraint",
        "object_key_ciphertext",
        "provider_version_ciphertext",
        "fk_evidence_links_scoped_object",
        "uq_evidence_links_order",
        "ck_evidence_objects_lifecycle",
        "retention_expires_at",
        "legal_hold_state",
        "reconciliation_state",
        "upload_attempt_count",
        "reconciliation_attempt_count",
        "delete_attempt_count",
        "next_reconciliation_at",
        "evidence_objects_reject_delete",
        "evidence_links_reject_delete",
        "payload ?| ARRAY",
        "signed_url",
        "object_key",
    ):
        assert marker in source
