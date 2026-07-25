from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from uuid import UUID

import pytest
from timekeeping_service.application.service import TimekeepingApplicationService
from timekeeping_service.domain.errors import TimekeepingError
from timekeeping_service.domain.models import (
    ConsentSnapshot,
    LinkType,
    ReviewStatus,
    Shift,
    ShiftStatus,
    SourceType,
    TimekeepingCorrectionOutcome,
    TimekeepingCorrectionRequest,
    TimekeepingEventLink,
    TimekeepingIngestionOutcome,
    TimekeepingIngestionRequest,
    TimekeepingRecord,
    TimekeepingStatus,
    TrustedIngestionContext,
    TrustedTimekeepingContext,
)

NOW = datetime(2026, 7, 26, 0, 0, tzinfo=UTC)
SCHOOL_ID = UUID("00000000-0000-4000-8000-000000000821")
STAFF_ID = UUID("00000000-0000-4000-8000-000000000822")
SHIFT_ID = UUID("00000000-0000-4000-8000-000000000823")


class SequenceIdentifierFactory:
    def __init__(self) -> None:
        self._value = 830

    def __call__(self) -> UUID:
        self._value += 1
        return UUID(f"00000000-0000-4000-8000-{self._value:012d}")


class FakeTimekeepingRepository:
    def __init__(self, *, assigned: bool = True) -> None:
        self.assigned = assigned
        self.last_ingestion: TimekeepingIngestionRequest | None = None
        self.shift = Shift(
            shift_id=SHIFT_ID,
            school_id=SCHOOL_ID,
            code="NIGHT_01",
            name="Night shift",
            timezone="Asia/Bangkok",
            start_local_time=time(22, 0),
            end_local_time=time(6, 0),
            overnight=True,
            check_in_grace_minutes=15,
            check_out_grace_minutes=15,
            status=ShiftStatus.ACTIVE,
            version=1,
            valid_from=NOW - timedelta(days=10),
            valid_to=None,
            created_at=NOW - timedelta(days=20),
        )

    def get_effective_shift(
        self,
        shift_id: UUID,
        school_id: UUID,
        occurred_at: datetime,
    ) -> Shift | None:
        return self.shift if (shift_id, school_id) == (SHIFT_ID, SCHOOL_ID) else None

    def has_active_assignment(
        self,
        school_id: UUID,
        staff_id: UUID,
        shift_id: UUID,
        work_date: date,
    ) -> bool:
        return self.assigned

    def ingest_event(
        self,
        request: TimekeepingIngestionRequest,
    ) -> TimekeepingIngestionOutcome:
        self.last_ingestion = request
        if request.consent_snapshot is ConsentSnapshot.BLOCKED:
            return TimekeepingIngestionOutcome(None, None, duplicate=False, blocked=True)
        record = TimekeepingRecord(
            timekeeping_record_id=request.timekeeping_record_id,
            school_id=request.school_id,
            staff_id=request.staff_id,
            shift_id=request.shift_id,
            work_date=request.work_date,
            check_in_at=request.occurred_at,
            check_out_at=None,
            status=request.event_status,
            source_type=SourceType.AI,
            review_status=(
                ReviewStatus.PENDING
                if request.event_status is TimekeepingStatus.REVIEW
                else ReviewStatus.NOT_REQUIRED
            ),
            retention_until=request.retention_until,
            created_at=request.recorded_at,
            updated_at=request.recorded_at,
            row_version=1,
        )
        link = TimekeepingEventLink(
            timekeeping_event_link_id=request.timekeeping_event_link_id,
            timekeeping_record_id=record.timekeeping_record_id,
            normalized_event_id=request.normalized_event_id,
            link_type=request.link_type,
            decision_confidence=request.decision_confidence,
            consent_snapshot=request.consent_snapshot,
            occurred_at=request.occurred_at,
            recorded_at=request.recorded_at,
        )
        return TimekeepingIngestionOutcome(record, link, duplicate=False, blocked=False)

    def get_record(self, record_id: UUID, school_id: UUID) -> TimekeepingRecord | None:
        return None

    def correct_record(
        self,
        request: TimekeepingCorrectionRequest,
        context: TrustedTimekeepingContext,
    ) -> TimekeepingCorrectionOutcome:
        raise AssertionError("unexpected correction")


def _payload(confidence: str | None) -> dict[str, object]:
    return {
        "schema_version": 1,
        "normalized_event_id": "00000000-0000-4000-8000-000000000824",
        "staff_id": str(STAFF_ID),
        "shift_id": str(SHIFT_ID),
        "occurred_at": datetime(2026, 7, 25, 22, 5, tzinfo=UTC),
        "link_type": "check_out",
        "decision_confidence": confidence,
        "retention_until": NOW + timedelta(days=30),
    }


def _context(
    consent: ConsentSnapshot,
    *,
    biometric: bool,
) -> TrustedIngestionContext:
    return TrustedIngestionContext(
        school_id=SCHOOL_ID,
        consent_snapshot=consent,
        purpose_code="staff_timekeeping",
        relationship_verified=True,
        biometric_processing=biometric,
        minimum_auto_accept_confidence=Decimal("0.8000"),
    )


def test_overnight_work_date_and_low_confidence_route_review() -> None:
    repository = FakeTimekeepingRepository()
    service = TimekeepingApplicationService(
        repository,
        clock=lambda: NOW,
        identifier_factory=SequenceIdentifierFactory(),
    )

    outcome = service.ingest_event(
        _payload("0.7000"),
        _context(ConsentSnapshot.ALLOWED, biometric=True),
    )

    assert outcome.record is not None
    assert outcome.record.work_date == date(2026, 7, 25)
    assert outcome.record.status is TimekeepingStatus.REVIEW
    assert repository.last_ingestion is not None
    assert repository.last_ingestion.requires_review is True


def test_biometric_blocked_consent_is_rejected_and_non_mutating() -> None:
    repository = FakeTimekeepingRepository()
    service = TimekeepingApplicationService(repository, clock=lambda: NOW)

    outcome = service.ingest_event(
        _payload("0.9900"),
        _context(ConsentSnapshot.BLOCKED, biometric=True),
    )

    assert outcome.blocked is True
    assert outcome.record is None
    assert repository.last_ingestion is not None
    assert repository.last_ingestion.link_type is LinkType.REJECTED
    assert repository.last_ingestion.consent_snapshot is ConsentSnapshot.BLOCKED


def test_non_biometric_not_required_consent_is_accepted() -> None:
    repository = FakeTimekeepingRepository()
    service = TimekeepingApplicationService(repository, clock=lambda: NOW)

    outcome = service.ingest_event(
        _payload("0.9900"),
        _context(ConsentSnapshot.NOT_REQUIRED, biometric=False),
    )

    assert outcome.blocked is False
    assert outcome.record is not None
    assert repository.last_ingestion is not None
    assert repository.last_ingestion.consent_snapshot is ConsentSnapshot.NOT_REQUIRED


def test_missing_assignment_fails_before_record_mutation() -> None:
    repository = FakeTimekeepingRepository(assigned=False)
    service = TimekeepingApplicationService(repository, clock=lambda: NOW)

    with pytest.raises(TimekeepingError, match="TIMEKEEPING_ASSIGNMENT_DENIED"):
        service.ingest_event(
            _payload("0.9900"),
            _context(ConsentSnapshot.ALLOWED, biometric=True),
        )
    assert repository.last_ingestion is None
