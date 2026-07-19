from __future__ import annotations

import re
from pathlib import Path

MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "20260719_0001_create_consent_baseline.py"
)


def test_migration_owns_only_approved_privacy_baseline_objects() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert 'SCHEMA = "privacy"' in source
    for table in ("purposes", "consents", "consent_events", "consent_audit_outbox"):
        assert f'"{table}"' in source
    for deferred in ("retention_policies", "data_subject_requests"):
        assert deferred not in source
    for cross_schema in ("identity.", "school.", "audit.", "events.", "evidence."):
        assert re.search(rf"(?<![a-z_]){re.escape(cross_schema)}", source) is None


def test_migration_contains_concurrency_history_and_minimization_guards() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    for marker in (
        "row_version",
        "uq_consent_events_idempotency",
        "request_fingerprint",
        "consent_events_reject_update_delete",
        "consents_reject_delete",
        "REVOKE UPDATE, DELETE, TRUNCATE",
        "CONSENT_RESTRICTED",
        "consent_audit_outbox",
    ):
        assert marker in source
    for forbidden in (
        "face_image",
        "face_embedding",
        "raw_payload",
        "signed_url",
        "signature_document",
    ):
        assert forbidden not in source
