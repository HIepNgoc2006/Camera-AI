from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from timekeeping_service.domain.errors import TimekeepingError
from timekeeping_service.schemas.commands import parse_apply_event, parse_correction

NOW = datetime(2026, 7, 26, 0, 0, tzinfo=UTC)


def _event() -> dict[str, object]:
    return {
        "schema_version": 1,
        "normalized_event_id": "00000000-0000-4000-8000-000000000841",
        "staff_id": "00000000-0000-4000-8000-000000000842",
        "shift_id": "00000000-0000-4000-8000-000000000843",
        "occurred_at": NOW - timedelta(minutes=5),
        "link_type": "check_in",
        "decision_confidence": "0.9000",
        "retention_until": NOW + timedelta(days=30),
    }


def test_strict_event_accepts_only_versioned_minimized_contract() -> None:
    parsed = parse_apply_event(_event())
    assert parsed.schema_version == 1
    assert parsed.link_type.value == "check_in"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema_version", 2),
        ("link_type", "rejected"),
        ("decision_confidence", "1.1000"),
        ("occurred_at", datetime(2026, 7, 25, 23, 55)),
    ],
)
def test_event_rejects_invalid_contract(field: str, value: object) -> None:
    payload = _event()
    payload[field] = value
    with pytest.raises(TimekeepingError, match="TIMEKEEPING_INPUT_INVALID"):
        parse_apply_event(payload)


def test_event_rejects_unknown_raw_or_media_fields() -> None:
    payload = _event()
    payload["raw_payload"] = {"unexpected": True}
    with pytest.raises(TimekeepingError, match="TIMEKEEPING_INPUT_INVALID"):
        parse_apply_event(payload)


def test_correction_rejects_free_text_reason_and_bad_time_order() -> None:
    payload: dict[str, object] = {
        "schema_version": 1,
        "timekeeping_record_id": "00000000-0000-4000-8000-000000000844",
        "expected_version": 1,
        "to_status": "present",
        "to_check_in_at": NOW,
        "to_check_out_at": NOW - timedelta(minutes=1),
        "reason_code": "employee said this was wrong",
        "approval_status": "pending",
        "request_id": "req_0123456789abcdef",
    }
    with pytest.raises(TimekeepingError, match="TIMEKEEPING_INPUT_INVALID"):
        parse_correction(payload)
