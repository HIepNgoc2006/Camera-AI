from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError, IntegrityError
from timekeeping_service.application.service import TimekeepingApplicationService
from timekeeping_service.domain.errors import TimekeepingError
from timekeeping_service.domain.models import (
    ConsentSnapshot,
    TimekeepingRole,
    TrustedIngestionContext,
    TrustedTimekeepingContext,
)
from timekeeping_service.infrastructure.repository import SqlAlchemyTimekeepingRepository

NOW = datetime(2026, 7, 26, 0, 0, tzinfo=UTC)
SERVICE_ROOT = Path(__file__).resolve().parents[2]
SCHOOL_ID = UUID("00000000-0000-4000-8000-000000000901")
STAFF_ID = UUID("00000000-0000-4000-8000-000000000902")
SHIFT_ID = UUID("00000000-0000-4000-8000-000000000903")
ACTOR_ID = UUID("00000000-0000-4000-8000-000000000904")


def _uuid(suffix: int) -> UUID:
    return UUID(f"00000000-0000-4000-8000-{suffix:012d}")


def _database_uri() -> str:
    raw = os.environ.get("TIMEKEEPING_DATABASE_URI", "").strip()
    if not raw:
        pytest.skip("TIMEKEEPING_DATABASE_URI is not set for an isolated integration database")
    url = make_url(raw)
    if url.host not in {"127.0.0.1", "localhost"} or not (url.database or "").endswith("_test"):
        pytest.fail("timekeeping integration database must be loopback and end with _test")
    return raw


def _alembic_config() -> Config:
    return Config(str(SERVICE_ROOT / "alembic.ini"))


def _ingestion_context(consent: ConsentSnapshot) -> TrustedIngestionContext:
    return TrustedIngestionContext(
        school_id=SCHOOL_ID,
        consent_snapshot=consent,
        purpose_code="staff_timekeeping",
        relationship_verified=True,
        biometric_processing=True,
        minimum_auto_accept_confidence=Decimal("0.8000"),
    )


def _access_context() -> TrustedTimekeepingContext:
    return TrustedTimekeepingContext(
        school_id=SCHOOL_ID,
        actor_id=ACTOR_ID,
        actor_staff_id=_uuid(990),
        role=TimekeepingRole.HR,
        authorized_staff_ids=frozenset({STAFF_ID}),
        school_wide_access=False,
        permission_codes=frozenset(
            {"timekeeping.read", "timekeeping.correct", "timekeeping.review"}
        ),
        relationship_verified=True,
    )


def _event(suffix: int, *, confidence: str | None = "0.9000") -> dict[str, object]:
    return {
        "schema_version": 1,
        "normalized_event_id": str(_uuid(suffix)),
        "staff_id": str(STAFF_ID),
        "shift_id": str(SHIFT_ID),
        "occurred_at": datetime(2026, 7, 25, 15, 5, tzinfo=UTC),
        "link_type": "check_in",
        "decision_confidence": confidence,
        "retention_until": NOW + timedelta(days=30),
    }


def _insert_shift_and_assignment(engine: sa.Engine) -> None:
    with engine.begin() as connection:
        connection.execute(
            sa.text(
                """
                INSERT INTO timekeeping.shifts (
                    shift_id, school_id, code, name, timezone,
                    start_local_time, end_local_time, overnight,
                    check_in_grace_minutes, check_out_grace_minutes,
                    status, version, valid_from, valid_to, created_at
                ) VALUES (
                    :shift_id, :school_id, 'NIGHT_01', 'Night shift', 'Asia/Bangkok',
                    '22:00', '06:00', true, 15, 15,
                    'active', 1, :valid_from, NULL, :created_at
                )
                """
            ),
            {
                "shift_id": SHIFT_ID,
                "school_id": SCHOOL_ID,
                "valid_from": NOW - timedelta(days=30),
                "created_at": NOW - timedelta(days=40),
            },
        )
        connection.execute(
            sa.text(
                """
                INSERT INTO timekeeping.staff_shift_assignments (
                    staff_shift_assignment_id, school_id, staff_id, shift_id,
                    valid_from, valid_to, status, created_at, updated_at, row_version
                ) VALUES (
                    :assignment_id, :school_id, :staff_id, :shift_id,
                    :valid_from, NULL, 'active', :created_at, :created_at, 1
                )
                """
            ),
            {
                "assignment_id": _uuid(905),
                "school_id": SCHOOL_ID,
                "staff_id": STAFF_ID,
                "shift_id": SHIFT_ID,
                "valid_from": date(2026, 7, 1),
                "created_at": NOW - timedelta(days=20),
            },
        )


def _assert_inventory(engine: sa.Engine) -> None:
    inspector = sa.inspect(engine)
    assert set(inspector.get_table_names(schema="timekeeping")) == {
        "shifts",
        "staff_shift_assignments",
        "timekeeping_records",
        "timekeeping_event_links",
        "timekeeping_corrections",
    }
    for table in (
        "staff_shift_assignments",
        "timekeeping_records",
        "timekeeping_event_links",
        "timekeeping_corrections",
    ):
        for foreign_key in inspector.get_foreign_keys(table, schema="timekeeping"):
            assert foreign_key["referred_schema"] == "timekeeping"


def test_migration_repository_concurrency_and_append_only_contract() -> None:
    database_uri = _database_uri()
    engine = sa.create_engine(database_uri, poolclass=sa.pool.NullPool)
    config = _alembic_config()
    upgraded = False
    try:
        command.downgrade(config, "base")
        assert sa.inspect(engine).has_schema("timekeeping") is False
        command.upgrade(config, "head")
        upgraded = True
        _assert_inventory(engine)
        _insert_shift_and_assignment(engine)

        with pytest.raises(IntegrityError), engine.begin() as connection:
            connection.execute(
                sa.text(
                    """
                    INSERT INTO timekeeping.shifts (
                        shift_id, school_id, code, name, timezone,
                        start_local_time, end_local_time, overnight,
                        check_in_grace_minutes, check_out_grace_minutes,
                        status, version, valid_from, valid_to, created_at
                    ) VALUES (
                        :shift_id, :school_id, 'NIGHT_01', 'Second active', 'Asia/Bangkok',
                        '22:00', '06:00', true, 15, 15,
                        'active', 2, :valid_from, NULL, :created_at
                    )
                    """
                ),
                {
                    "shift_id": _uuid(906),
                    "school_id": SCHOOL_ID,
                    "valid_from": NOW - timedelta(days=1),
                    "created_at": NOW - timedelta(days=2),
                },
            )
        with pytest.raises(DBAPIError), engine.begin() as connection:
            connection.execute(
                sa.text(
                    "UPDATE timekeeping.shifts SET name = 'Changed' WHERE shift_id = :shift_id"
                ),
                {"shift_id": SHIFT_ID},
            )
        with pytest.raises(DBAPIError), engine.begin() as connection:
            connection.execute(
                sa.text(
                    "UPDATE timekeeping.shifts "
                    "SET status = 'retired', valid_to = :valid_to "
                    "WHERE shift_id = :shift_id"
                ),
                {"shift_id": SHIFT_ID, "valid_to": NOW},
            )
        with pytest.raises(DBAPIError), engine.begin() as connection:
            connection.execute(
                sa.text(
                    """
                    INSERT INTO timekeeping.staff_shift_assignments (
                        staff_shift_assignment_id, school_id, staff_id, shift_id,
                        valid_from, valid_to, status, created_at, updated_at, row_version
                    ) VALUES (
                        :assignment_id, :school_id, :staff_id, :shift_id,
                        :valid_from, :valid_to, 'active', :created_at, :created_at, 1
                    )
                    """
                ),
                {
                    "assignment_id": _uuid(907),
                    "school_id": SCHOOL_ID,
                    "staff_id": STAFF_ID,
                    "shift_id": SHIFT_ID,
                    "valid_from": date(2026, 7, 20),
                    "valid_to": date(2026, 7, 30),
                    "created_at": NOW,
                },
            )

        repository = SqlAlchemyTimekeepingRepository(engine)
        service = TimekeepingApplicationService(repository, clock=lambda: NOW)
        payload = _event(911)

        def ingest_same_event(_: int) -> tuple[bool, UUID | None]:
            outcome = service.ingest_event(
                payload,
                _ingestion_context(ConsentSnapshot.ALLOWED),
            )
            return outcome.duplicate, (
                None if outcome.record is None else outcome.record.timekeeping_record_id
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            duplicate_results = list(executor.map(ingest_same_event, (1, 2)))
        assert sum(duplicate for duplicate, _ in duplicate_results) == 1
        assert len({record_id for _, record_id in duplicate_results}) == 1

        record_id = duplicate_results[0][1]
        assert record_id is not None
        first = repository.get_record(record_id, SCHOOL_ID)
        assert first is not None
        original_version = first.row_version

        blocked = service.ingest_event(
            _event(912, confidence="0.9900"),
            _ingestion_context(ConsentSnapshot.BLOCKED),
        )
        assert blocked.blocked is True
        assert blocked.record is not None
        assert blocked.record.row_version == original_version
        assert blocked.event_link is not None
        assert blocked.event_link.consent_snapshot is ConsentSnapshot.BLOCKED

        correction_payloads = (
            {
                "schema_version": 1,
                "timekeeping_record_id": str(record_id),
                "expected_version": original_version,
                "to_status": "late",
                "to_check_in_at": first.check_in_at,
                "to_check_out_at": first.check_out_at,
                "reason_code": "TIME_ADJUSTMENT",
                "approval_status": "approved",
                "request_id": "req_aaaaaaaaaaaaaaaa",
            },
            {
                "schema_version": 1,
                "timekeeping_record_id": str(record_id),
                "expected_version": original_version,
                "to_status": "absent",
                "to_check_in_at": None,
                "to_check_out_at": None,
                "reason_code": "REVIEW_RESOLUTION",
                "approval_status": "approved",
                "request_id": "req_bbbbbbbbbbbbbbbb",
            },
        )

        def correct(payload_item: dict[str, object]) -> int | str:
            try:
                return service.correct_record(
                    payload_item,
                    _access_context(),
                ).record.row_version
            except TimekeepingError as exc:
                return exc.code

        with ThreadPoolExecutor(max_workers=2) as executor:
            correction_results = list(executor.map(correct, correction_payloads))
        assert sum(result == original_version + 1 for result in correction_results) == 1
        assert sum(result == "TIMEKEEPING_VERSION_CONFLICT" for result in correction_results) == 1

        with engine.connect() as connection:
            link_id = connection.scalar(
                sa.text(
                    "SELECT timekeeping_event_link_id "
                    "FROM timekeeping.timekeeping_event_links LIMIT 1"
                )
            )
            correction_id = connection.scalar(
                sa.text(
                    "SELECT timekeeping_correction_id "
                    "FROM timekeeping.timekeeping_corrections LIMIT 1"
                )
            )
        with pytest.raises(DBAPIError), engine.begin() as connection:
            connection.execute(
                sa.text(
                    "UPDATE timekeeping.timekeeping_event_links "
                    "SET link_type = 'supporting' "
                    "WHERE timekeeping_event_link_id = :link_id"
                ),
                {"link_id": link_id},
            )
        with pytest.raises(DBAPIError), engine.begin() as connection:
            connection.execute(
                sa.text(
                    "UPDATE timekeeping.timekeeping_corrections "
                    "SET reason_code = 'SHIFT_OVERRIDE' "
                    "WHERE timekeeping_correction_id = :correction_id"
                ),
                {"correction_id": correction_id},
            )
        with pytest.raises(DBAPIError), engine.begin() as connection:
            connection.execute(
                sa.text(
                    "DELETE FROM timekeeping.timekeeping_records "
                    "WHERE timekeeping_record_id = :record_id"
                ),
                {"record_id": record_id},
            )

        command.downgrade(config, "base")
        upgraded = False
        assert sa.inspect(engine).has_schema("timekeeping") is False
    finally:
        if upgraded:
            command.downgrade(config, "base")
        engine.dispose()
