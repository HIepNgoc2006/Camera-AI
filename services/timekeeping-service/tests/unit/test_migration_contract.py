from __future__ import annotations

import re
from pathlib import Path

MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "20260725_0001_create_timekeeping_baseline.py"
)


def test_migration_owns_only_the_five_approved_timekeeping_tables() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    assert 'SCHEMA = "timekeeping"' in source
    for table in (
        "shifts",
        "staff_shift_assignments",
        "timekeeping_records",
        "timekeeping_event_links",
        "timekeeping_corrections",
    ):
        assert f'"{table}"' in source
    for cross_schema in (
        "identity.",
        "school.",
        "privacy.",
        "events.",
        "attendance.",
        "audit.",
        "evidence.",
    ):
        assert re.search(rf"(?<![a-z_]){re.escape(cross_schema)}", source) is None


def test_migration_contains_shift_assignment_and_event_invariants() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    for marker in (
        "uq_timekeeping_shifts_school_code_version",
        "uq_timekeeping_shifts_one_active_code",
        "enforce_one_active_shift_version",
        "shifts_require_one_active_version",
        "active shift versions are immutable",
        "enforce_assignment_non_overlap",
        "uq_timekeeping_records_school_staff_date_shift",
        "uq_timekeeping_event_links_normalized_type",
        "consent_snapshot_status",
        "retention_until",
        "row_version",
        "reject_append_only_change",
        "REVOKE UPDATE, DELETE, TRUNCATE",
        "TIME_ADJUSTMENT",
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
        "free_text",
    ):
        assert forbidden not in source
