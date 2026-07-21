from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from attendance_service.application.service import AttendanceApplicationService
from attendance_service.domain.models import (
    AttendanceCorrectionOutcome,
    AttendanceCorrectionRequest,
    AttendanceEventLink,
    AttendanceIngestionOutcome,
    AttendanceIngestionRequest,
    AttendanceRecord,
    AttendanceStatus,
    ConsentSnapshot,
    LinkType,
    ReviewStatus,
    SourceType,
    TrustedAttendanceContext,
    TrustedIngestionContext,
)

NOW = datetime(2026, 7, 22, 3, 0, tzinfo=UTC)
SCHOOL_ID = UUID("00000000-0000-4000-8000-000000000621")


class SequenceIdentifierFactory:
    def __init__(self) -> None:
        self._value = 630

    def __call__(self) -> UUID:
        self._value += 1
        return UUID(f"00000000-0000-4000-8000-{self._value:012d}")


class FakeAttendanceRepository:
    def __init__(self) -> None:
        self.last_ingestion: AttendanceIngestionRequest | None = None

    def ingest_event(self, request: AttendanceIngestionRequest) -> AttendanceIngestionOutcome:
        self.last_ingestion = request
        if request.consent_snapshot is ConsentSnapshot.BLOCKED:
            return AttendanceIngestionOutcome(None, None, duplicate=False, blocked=True)
        record = AttendanceRecord(
            attendance_record_id=request.attendance_record_id,
            school_id=request.school_id,
            student_id=request.student_id,
            class_id=request.class_id,
            attendance_date=request.attendance_date,
            status=(
                AttendanceStatus.PENDING_REVIEW
                if request.requires_review
                else AttendanceStatus.PRESENT
            ),
            first_check_in_at=request.occurred_at,
            last_check_out_at=None,
            source_type=SourceType.AI,
            review_status=(
                ReviewStatus.PENDING if request.requires_review else ReviewStatus.NOT_REQUIRED
            ),
            retention_until=request.retention_until,
            created_at=request.recorded_at,
            updated_at=request.recorded_at,
            row_version=1,
        )
        link = AttendanceEventLink(
            attendance_event_link_id=request.attendance_event_link_id,
            attendance_record_id=record.attendance_record_id,
            normalized_event_id=request.normalized_event_id,
            link_type=request.link_type,
            decision_confidence=request.decision_confidence,
            consent_snapshot=request.consent_snapshot,
            occurred_at=request.occurred_at,
            recorded_at=request.recorded_at,
        )
        return AttendanceIngestionOutcome(record, link, duplicate=False, blocked=False)

    def get_record(self, record_id: UUID, school_id: UUID) -> AttendanceRecord | None:
        return None

    def correct_record(
        self,
        request: AttendanceCorrectionRequest,
        context: TrustedAttendanceContext,
    ) -> AttendanceCorrectionOutcome:
        raise AssertionError("unexpected correction")


def _payload(confidence: str | None) -> dict[str, object]:
    return {
        "schema_version": 1,
        "normalized_event_id": "00000000-0000-4000-8000-000000000622",
        "student_id": "00000000-0000-4000-8000-000000000623",
        "class_id": "00000000-0000-4000-8000-000000000624",
        "occurred_at": datetime(2026, 7, 21, 18, 30, tzinfo=UTC),
        "link_type": "check_in",
        "decision_confidence": confidence,
        "school_timezone": "Asia/Bangkok",
        "retention_until": NOW + timedelta(days=30),
    }


def _context(consent: ConsentSnapshot) -> TrustedIngestionContext:
    return TrustedIngestionContext(
        school_id=SCHOOL_ID,
        consent_snapshot=consent,
        purpose_code="student_attendance",
        relationship_verified=True,
        minimum_auto_accept_confidence=Decimal("0.8000"),
    )


def test_school_timezone_derives_daily_key_and_low_confidence_routes_review() -> None:
    repository = FakeAttendanceRepository()
    service = AttendanceApplicationService(
        repository,
        clock=lambda: NOW,
        identifier_factory=SequenceIdentifierFactory(),
    )

    outcome = service.ingest_event(_payload("0.7000"), _context(ConsentSnapshot.ALLOWED))

    assert outcome.record is not None
    assert outcome.record.attendance_date == date(2026, 7, 22)
    assert outcome.record.status is AttendanceStatus.PENDING_REVIEW
    assert repository.last_ingestion is not None
    assert repository.last_ingestion.requires_review is True


def test_missing_confidence_routes_review() -> None:
    repository = FakeAttendanceRepository()
    service = AttendanceApplicationService(repository, clock=lambda: NOW)
    outcome = service.ingest_event(_payload(None), _context(ConsentSnapshot.NOT_REQUIRED))
    assert outcome.record is not None
    assert outcome.record.status is AttendanceStatus.PENDING_REVIEW


def test_blocked_consent_uses_rejected_non_mutating_repository_command() -> None:
    repository = FakeAttendanceRepository()
    service = AttendanceApplicationService(repository, clock=lambda: NOW)

    outcome = service.ingest_event(_payload("0.9900"), _context(ConsentSnapshot.BLOCKED))

    assert outcome.blocked is True
    assert outcome.record is None
    assert repository.last_ingestion is not None
    assert repository.last_ingestion.link_type is LinkType.REJECTED
    assert repository.last_ingestion.requires_review is False
