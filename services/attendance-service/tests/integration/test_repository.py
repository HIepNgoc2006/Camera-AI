from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from attendance_service.application.service import AttendanceApplicationService
from attendance_service.domain.errors import AttendanceError
from attendance_service.domain.models import (
    AttendanceRole,
    ConsentSnapshot,
    TrustedAttendanceContext,
    TrustedIngestionContext,
)
from attendance_service.infrastructure.repository import SqlAlchemyAttendanceRepository
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError

NOW = datetime(2026, 7, 22, 3, 0, tzinfo=UTC)
SERVICE_ROOT = Path(__file__).resolve().parents[2]
SCHOOL_ID = UUID("00000000-0000-4000-8000-000000000701")
STUDENT_ID = UUID("00000000-0000-4000-8000-000000000702")
CLASS_ID = UUID("00000000-0000-4000-8000-000000000703")
ACTOR_ID = UUID("00000000-0000-4000-8000-000000000704")


class SequenceIdentifierFactory:
    def __init__(self, values: list[UUID]) -> None:
        self._values = iter(values)

    def __call__(self) -> UUID:
        return next(self._values)


def _uuid(suffix: int) -> UUID:
    return UUID(f"00000000-0000-4000-8000-{suffix:012d}")


def _database_uri() -> str:
    raw = os.environ.get("ATTENDANCE_DATABASE_URI", "").strip()
    if not raw:
        pytest.skip("ATTENDANCE_DATABASE_URI is not set for an isolated integration database")
    url = make_url(raw)
    if url.host not in {"127.0.0.1", "localhost"} or not (url.database or "").endswith("_test"):
        pytest.fail("attendance integration database must be loopback and end with _test")
    return raw


def _alembic_config() -> Config:
    return Config(str(SERVICE_ROOT / "alembic.ini"))


def _ingestion_context(consent: ConsentSnapshot) -> TrustedIngestionContext:
    return TrustedIngestionContext(
        school_id=SCHOOL_ID,
        consent_snapshot=consent,
        purpose_code="student_attendance",
        relationship_verified=True,
        minimum_auto_accept_confidence=Decimal("0.8000"),
    )


def _access_context() -> TrustedAttendanceContext:
    return TrustedAttendanceContext(
        school_id=SCHOOL_ID,
        actor_id=ACTOR_ID,
        role=AttendanceRole.BGH,
        assigned_class_ids=frozenset({CLASS_ID}),
        linked_student_ids=frozenset(),
        permission_codes=frozenset({"attendance.read", "attendance.correct", "attendance.review"}),
        relationship_verified=True,
    )


def _event(
    suffix: int,
    *,
    student_id: UUID = STUDENT_ID,
    link_type: str = "check_in",
    confidence: str | None = "0.9000",
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "normalized_event_id": str(_uuid(suffix)),
        "student_id": str(student_id),
        "class_id": str(CLASS_ID),
        "occurred_at": NOW - timedelta(minutes=5),
        "link_type": link_type,
        "decision_confidence": confidence,
        "school_timezone": "Asia/Bangkok",
        "retention_until": NOW + timedelta(days=30),
    }


def _assert_inventory(engine: sa.Engine) -> None:
    inspector = sa.inspect(engine)
    assert set(inspector.get_table_names(schema="attendance")) == {
        "attendance_records",
        "attendance_event_links",
        "attendance_corrections",
    }
    event_columns = {
        column["name"]
        for column in inspector.get_columns("attendance_event_links", schema="attendance")
    }
    assert {"decision_confidence", "consent_snapshot_status"} <= event_columns
    for table in ("attendance_event_links", "attendance_corrections"):
        for foreign_key in inspector.get_foreign_keys(table, schema="attendance"):
            assert foreign_key["referred_schema"] == "attendance"


def test_migration_repository_concurrency_rollback_and_append_only_contract() -> None:
    database_uri = _database_uri()
    engine = sa.create_engine(database_uri, poolclass=sa.pool.NullPool)
    config = _alembic_config()
    upgraded = False
    try:
        command.downgrade(config, "base")
        assert sa.inspect(engine).has_schema("attendance") is False
        command.upgrade(config, "head")
        upgraded = True
        _assert_inventory(engine)

        repository = SqlAlchemyAttendanceRepository(engine)
        service = AttendanceApplicationService(repository, clock=lambda: NOW)
        payload = _event(711)

        def ingest_same_event(_: int) -> tuple[bool, UUID | None]:
            outcome = service.ingest_event(payload, _ingestion_context(ConsentSnapshot.ALLOWED))
            return outcome.duplicate, (
                None if outcome.record is None else outcome.record.attendance_record_id
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            duplicate_results = list(executor.map(ingest_same_event, (1, 2)))
        assert sum(duplicate for duplicate, _ in duplicate_results) == 1
        assert len({record_id for _, record_id in duplicate_results}) == 1

        first = repository.get_record(duplicate_results[0][1], SCHOOL_ID)  # type: ignore[arg-type]
        assert first is not None
        original_version = first.row_version

        blocked = service.ingest_event(
            _event(712, confidence="0.9900"),
            _ingestion_context(ConsentSnapshot.BLOCKED),
        )
        assert blocked.blocked is True
        assert blocked.record is not None
        assert blocked.record.row_version == original_version
        assert blocked.event_link is not None
        assert blocked.event_link.consent_snapshot is ConsentSnapshot.BLOCKED

        absent_student = _uuid(799)
        blocked_without_record = service.ingest_event(
            _event(713, student_id=absent_student),
            _ingestion_context(ConsentSnapshot.BLOCKED),
        )
        assert blocked_without_record.record is None
        with engine.connect() as connection:
            assert (
                connection.scalar(
                    sa.text(
                        "SELECT count(*) FROM attendance.attendance_records "
                        "WHERE student_id = :student_id"
                    ),
                    {"student_id": absent_student},
                )
                == 0
            )

        existing_link_id = blocked.event_link.attendance_event_link_id
        rollback_service = AttendanceApplicationService(
            repository,
            clock=lambda: NOW,
            identifier_factory=SequenceIdentifierFactory([_uuid(720), existing_link_id]),
        )
        with pytest.raises(AttendanceError, match="ATTENDANCE_DUPLICATE_CONFLICT"):
            rollback_service.ingest_event(
                _event(714, student_id=_uuid(721)),
                _ingestion_context(ConsentSnapshot.ALLOWED),
            )
        with engine.connect() as connection:
            assert (
                connection.scalar(sa.text("SELECT count(*) FROM attendance.attendance_records"))
                == 1
            )

        correction_payloads = (
            {
                "schema_version": 1,
                "attendance_record_id": str(first.attendance_record_id),
                "expected_version": original_version,
                "to_status": "late",
                "to_check_in_at": first.first_check_in_at,
                "reason_code": "TIME_ADJUSTMENT",
                "approval_status": "not_required",
                "request_id": "req_aaaaaaaaaaaaaaaa",
            },
            {
                "schema_version": 1,
                "attendance_record_id": str(first.attendance_record_id),
                "expected_version": original_version,
                "to_status": "excused",
                "to_check_in_at": first.first_check_in_at,
                "reason_code": "EXCUSED_ABSENCE",
                "approval_status": "not_required",
                "request_id": "req_bbbbbbbbbbbbbbbb",
            },
        )

        def correct(payload_item: dict[str, object]) -> int | str:
            try:
                return service.correct_record(payload_item, _access_context()).record.row_version
            except AttendanceError as exc:
                return exc.code

        with ThreadPoolExecutor(max_workers=2) as executor:
            correction_results = list(executor.map(correct, correction_payloads))
        assert sum(result == original_version + 1 for result in correction_results) == 1
        assert sum(result == "ATTENDANCE_VERSION_CONFLICT" for result in correction_results) == 1

        with engine.connect() as connection:
            correction_id = connection.scalar(
                sa.text("SELECT attendance_correction_id FROM attendance.attendance_corrections")
            )
        with pytest.raises(DBAPIError), engine.begin() as connection:
            connection.execute(
                sa.text(
                    "UPDATE attendance.attendance_event_links "
                    "SET link_type = 'supporting' WHERE attendance_event_link_id = :link_id"
                ),
                {"link_id": existing_link_id},
            )
        with pytest.raises(DBAPIError), engine.begin() as connection:
            connection.execute(
                sa.text(
                    "UPDATE attendance.attendance_corrections "
                    "SET reason_code = 'MANUAL_CORRECTION' "
                    "WHERE attendance_correction_id = :correction_id"
                ),
                {"correction_id": correction_id},
            )
        with pytest.raises(DBAPIError), engine.begin() as connection:
            connection.execute(
                sa.text(
                    "DELETE FROM attendance.attendance_records "
                    "WHERE attendance_record_id = :record_id"
                ),
                {"record_id": first.attendance_record_id},
            )

        command.downgrade(config, "base")
        upgraded = False
        assert sa.inspect(engine).has_schema("attendance") is False
    finally:
        if upgraded:
            command.downgrade(config, "base")
        engine.dispose()
