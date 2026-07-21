from __future__ import annotations

import re
from pathlib import Path

MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "20260722_0001_create_attendance_baseline.py"
)


def test_migration_owns_only_the_three_approved_attendance_tables() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert 'SCHEMA = "attendance"' in source
    for table in ("attendance_records", "attendance_event_links", "attendance_corrections"):
        assert f'"{table}"' in source
    for cross_schema in ("identity.", "school.", "privacy.", "events.", "audit.", "evidence."):
        assert re.search(rf"(?<![a-z_]){re.escape(cross_schema)}", source) is None


def test_migration_contains_idempotency_history_consent_and_retention_guards() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    for marker in (
        "uq_attendance_records_school_student_date",
        "uq_attendance_event_links_normalized_type",
        "decision_confidence",
        "consent_snapshot_status",
        '"blocked"',
        "retention_until",
        "row_version",
        "reject_append_only_change",
        'for table in ("attendance_event_links", "attendance_corrections")',
        "attendance_records_reject_",
        "REVOKE UPDATE, DELETE, TRUNCATE",
        "MANUAL_CORRECTION",
    ):
        assert marker in source


def test_migration_contains_no_media_payload_secret_or_biometric_columns() -> None:
    source = MIGRATION.read_text(encoding="utf-8").casefold()
    for forbidden in (
        "face_image",
        "face_crop",
        "face_embedding",
        "raw_payload",
        "base64",
        "rtsp",
        "access_token",
        "password",
        "media_url",
    ):
        assert forbidden not in source
