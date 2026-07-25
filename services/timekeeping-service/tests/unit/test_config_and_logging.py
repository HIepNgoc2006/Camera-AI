from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import UUID

import pytest
from timekeeping_service.config import (
    TimekeepingConfigurationError,
    load_database_settings,
)
from timekeeping_service.domain.errors import TimekeepingError
from timekeeping_service.domain.models import (
    ReviewStatus,
    SourceType,
    TimekeepingIngestionOutcome,
    TimekeepingRecord,
    TimekeepingStatus,
)
from timekeeping_service.logging import safe_ingestion_log_fields

NOW = datetime(2026, 7, 26, 0, 0, tzinfo=UTC)


def _uuid(suffix: int) -> UUID:
    return UUID(f"00000000-0000-4000-8000-{suffix:012d}")


def test_config_requires_injected_postgresql_uri_without_echoing_it() -> None:
    with pytest.raises(
        TimekeepingConfigurationError,
        match="TIMEKEEPING_DATABASE_URI is required",
    ):
        load_database_settings({"APP_ENV": "test"})

    scheme = "postgresql+psycopg"
    user_info = "synthetic-user" + ":" + "synthetic-private-value"
    secret_like = f"{scheme}://{user_info}@db.example.invalid/test_db"
    with pytest.raises(TimekeepingConfigurationError) as caught:
        load_database_settings({"APP_ENV": "production", "TIMEKEEPING_DATABASE_URI": secret_like})
    assert secret_like not in str(caught.value)
    assert "synthetic-private-value" not in repr(caught.value)


def test_safe_logs_exclude_all_object_and_event_identifiers() -> None:
    record = TimekeepingRecord(
        timekeeping_record_id=_uuid(1),
        school_id=_uuid(2),
        staff_id=_uuid(3),
        shift_id=_uuid(4),
        work_date=date(2026, 7, 25),
        check_in_at=NOW,
        check_out_at=None,
        status=TimekeepingStatus.PRESENT,
        source_type=SourceType.AI,
        review_status=ReviewStatus.NOT_REQUIRED,
        retention_until=NOW + timedelta(days=30),
        created_at=NOW,
        updated_at=NOW,
        row_version=1,
    )
    fields = safe_ingestion_log_fields(
        TimekeepingIngestionOutcome(record, None, duplicate=False, blocked=False)
    )
    rendered = repr(fields)

    assert fields == {
        "service_name": "timekeeping-service",
        "operation": "ingest_normalized_event",
        "result": "accepted",
        "status": "present",
    }
    for forbidden in (_uuid(1), _uuid(2), _uuid(3), _uuid(4)):
        assert str(forbidden) not in rendered
    for forbidden_text in (
        "raw_payload",
        "face_embedding",
        "base64",
        "rtsp://",
        "token",
        "password",
    ):
        assert forbidden_text not in rendered.casefold()


def test_errors_never_echo_rejected_input() -> None:
    rejected = "synthetic-token-private-value"
    error = TimekeepingError(rejected)
    assert rejected not in str(error)
    assert error.code == "TIMEKEEPING_INPUT_INVALID"
