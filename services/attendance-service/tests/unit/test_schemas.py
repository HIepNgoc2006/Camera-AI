from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from attendance_service.domain.errors import AttendanceError
from attendance_service.schemas.commands import parse_apply_event, parse_correction

NOW = datetime(2026, 7, 22, 3, 0, tzinfo=UTC)


def _event() -> dict[str, object]:
    return {
        "schema_version": 1,
        "normalized_event_id": "00000000-0000-4000-8000-000000000611",
        "student_id": "00000000-0000-4000-8000-000000000612",
        "class_id": "00000000-0000-4000-8000-000000000613",
        "occurred_at": NOW,
        "link_type": "check_in",
        "decision_confidence": "0.9123",
        "school_timezone": "Asia/Bangkok",
        "retention_until": NOW + timedelta(days=30),
    }


def test_normalized_event_schema_accepts_only_minimized_fields() -> None:
    parsed = parse_apply_event(_event())
    assert str(parsed.decision_confidence) == "0.9123"

    for forbidden in ("raw_payload", "face_embedding", "image_base64", "rtsp_url", "token"):
        payload = {**_event(), forbidden: "synthetic-forbidden-value"}
        with pytest.raises(AttendanceError, match="ATTENDANCE_INPUT_INVALID"):
            parse_apply_event(payload)


def test_event_requires_aware_time_valid_timezone_and_retention() -> None:
    for changes in (
        {"occurred_at": datetime(2026, 7, 22, 3, 0)},
        {"school_timezone": "Invalid/Synthetic"},
        {"retention_until": NOW},
    ):
        with pytest.raises(AttendanceError, match="ATTENDANCE_INPUT_INVALID"):
            parse_apply_event({**_event(), **changes})


def test_correction_rejects_free_text_reason_and_missing_approver() -> None:
    base: dict[str, object] = {
        "schema_version": 1,
        "attendance_record_id": "00000000-0000-4000-8000-000000000614",
        "expected_version": 1,
        "to_status": "excused",
        "to_check_in_at": NOW,
        "reason_code": "EXCUSED_ABSENCE",
        "approval_status": "approved",
        "request_id": "req_0123456789abcdef",
    }
    assert parse_correction(base).reason_code == "EXCUSED_ABSENCE"

    for changes in (
        {"reason_code": "Student was sick"},
        {"reason_code": "UNAPPROVED_REASON"},
        {"approver_id": "00000000-0000-4000-8000-000000000615"},
    ):
        with pytest.raises(AttendanceError, match="ATTENDANCE_INPUT_INVALID"):
            parse_correction({**base, **changes})
