from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from attendance_service.domain.errors import AttendanceError
from attendance_service.infrastructure.tables import (
    attendance_corrections,
    attendance_event_links,
    attendance_records,
)
from attendance_service.schemas.commands import parse_apply_event

NOW = datetime(2026, 7, 22, 3, 0, tzinfo=UTC)


def _event() -> dict[str, object]:
    return {
        "schema_version": 1,
        "normalized_event_id": "00000000-0000-4000-8000-000000000801",
        "student_id": "00000000-0000-4000-8000-000000000802",
        "class_id": "00000000-0000-4000-8000-000000000803",
        "occurred_at": NOW - timedelta(minutes=1),
        "link_type": "check_in",
        "decision_confidence": "0.9000",
        "school_timezone": "Asia/Bangkok",
        "retention_until": NOW + timedelta(days=30),
    }


def test_internal_command_rejects_producer_identity_and_raw_event_fields() -> None:
    for forbidden in (
        "producer_subject_id",
        "subject_ref",
        "raw_ansvis_payload",
        "face_crop",
        "media_url",
    ):
        with pytest.raises(AttendanceError, match="ATTENDANCE_INPUT_INVALID"):
            parse_apply_event({**_event(), forbidden: "synthetic-forbidden-value"})


def test_table_contract_owns_only_attendance_local_foreign_keys_and_minimized_columns() -> None:
    assert {
        table.name for table in (attendance_records, attendance_event_links, attendance_corrections)
    } == {
        "attendance_records",
        "attendance_event_links",
        "attendance_corrections",
    }
    for table in (attendance_event_links, attendance_corrections):
        for foreign_key in table.foreign_keys:
            assert foreign_key.target_fullname.startswith("attendance.attendance_records.")
    all_columns = {
        column.name
        for table in (attendance_records, attendance_event_links, attendance_corrections)
        for column in table.columns
    }
    assert not all_columns & {
        "raw_payload",
        "face_image",
        "face_crop",
        "face_embedding",
        "media_url",
        "token",
        "password",
    }
