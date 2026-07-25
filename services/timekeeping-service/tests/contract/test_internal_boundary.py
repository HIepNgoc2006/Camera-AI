from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from timekeeping_service.domain.errors import TimekeepingError
from timekeeping_service.infrastructure.tables import (
    shifts,
    staff_shift_assignments,
    timekeeping_corrections,
    timekeeping_event_links,
    timekeeping_records,
)
from timekeeping_service.schemas.commands import parse_apply_event

NOW = datetime(2026, 7, 26, 0, 0, tzinfo=UTC)


def _event() -> dict[str, object]:
    return {
        "schema_version": 1,
        "normalized_event_id": "00000000-0000-4000-8000-000000000861",
        "staff_id": "00000000-0000-4000-8000-000000000862",
        "shift_id": "00000000-0000-4000-8000-000000000863",
        "occurred_at": NOW - timedelta(minutes=1),
        "link_type": "check_in",
        "decision_confidence": "0.9000",
        "retention_until": NOW + timedelta(days=30),
    }


def test_internal_command_rejects_producer_identity_and_raw_event_fields() -> None:
    for forbidden in (
        "producer_staff_id",
        "subject_ref",
        "raw_ansvis_payload",
        "face_crop",
        "media_url",
        "school_id",
        "consent_status",
    ):
        with pytest.raises(TimekeepingError, match="TIMEKEEPING_INPUT_INVALID"):
            parse_apply_event({**_event(), forbidden: "synthetic-forbidden-value"})


def test_table_contract_owns_only_timekeeping_local_foreign_keys_and_columns() -> None:
    tables = (
        shifts,
        staff_shift_assignments,
        timekeeping_records,
        timekeeping_event_links,
        timekeeping_corrections,
    )
    assert {table.name for table in tables} == {
        "shifts",
        "staff_shift_assignments",
        "timekeeping_records",
        "timekeeping_event_links",
        "timekeeping_corrections",
    }
    for table in tables:
        for foreign_key in table.foreign_keys:
            assert foreign_key.target_fullname.startswith("timekeeping.")
    all_columns = {column.name for table in tables for column in table.columns}
    assert not all_columns & {
        "raw_payload",
        "face_image",
        "face_crop",
        "face_embedding",
        "media_url",
        "token",
        "password",
        "free_text",
    }
