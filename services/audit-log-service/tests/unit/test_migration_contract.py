from __future__ import annotations

from pathlib import Path

MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "20260718_0001_create_audit_schema.py"
)


def test_migration_owns_only_the_approved_audit_table() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert '"audit_events"' in source
    assert 'SCHEMA = "audit"' in source
    for cross_schema in ("identity.", "school.", "privacy.", "events.", "evidence."):
        assert cross_schema not in source
    for forbidden in ("face_image", "face_embedding", "raw_payload", "signed_url"):
        assert forbidden not in source


def test_migration_contains_append_only_and_integrity_guards() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    for marker in (
        "uq_audit_events_source_identity",
        "audit_events_reject_update_delete",
        "audit_events_reject_truncate",
        "previous_event_hash",
        "event_hash",
        "integrity_partition",
        "ck_audit_events_changes",
        "REVOKE UPDATE, DELETE, TRUNCATE",
    ):
        assert marker in source
