"""Timekeeping use cases over trusted contexts and strict internal commands."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from uuid import UUID, uuid4

from timekeeping_service.application.ports import TimekeepingRepository
from timekeeping_service.domain.errors import TimekeepingError
from timekeeping_service.domain.models import (
    ApprovalStatus,
    ConsentSnapshot,
    LinkType,
    TimekeepingCorrectionOutcome,
    TimekeepingCorrectionRequest,
    TimekeepingIngestionOutcome,
    TimekeepingIngestionRequest,
    TimekeepingRecord,
    TimekeepingStatus,
    TrustedIngestionContext,
    TrustedTimekeepingContext,
    derive_shift_window,
    status_for_event,
)
from timekeeping_service.domain.policies import (
    authorize_correction_approval,
    authorize_record,
    consent_is_blocked,
    ingestion_is_allowed,
)
from timekeeping_service.schemas.commands import parse_apply_event, parse_correction


class TimekeepingApplicationService:
    def __init__(
        self,
        repository: TimekeepingRepository,
        *,
        clock: Callable[[], datetime] | None = None,
        identifier_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._repository = repository
        self._clock = clock or (lambda: datetime.now(UTC))
        self._identifier_factory = identifier_factory

    def ingest_event(
        self,
        payload: Mapping[str, object],
        context: TrustedIngestionContext,
    ) -> TimekeepingIngestionOutcome:
        command = parse_apply_event(payload)
        if not ingestion_is_allowed(context):
            raise TimekeepingError("TIMEKEEPING_AUTHORITY_DENIED")
        recorded_at = self._clock()
        if recorded_at.tzinfo is None or recorded_at.utcoffset() is None:
            raise TimekeepingError("TIMEKEEPING_INPUT_INVALID")
        if command.occurred_at > recorded_at or command.retention_until <= recorded_at:
            raise TimekeepingError("TIMEKEEPING_INPUT_INVALID")
        shift = self._repository.get_effective_shift(
            command.shift_id,
            context.school_id,
            command.occurred_at,
        )
        if shift is None:
            raise TimekeepingError("TIMEKEEPING_SHIFT_NOT_FOUND")
        window = derive_shift_window(shift, command.occurred_at, command.link_type)
        if not self._repository.has_active_assignment(
            context.school_id,
            command.staff_id,
            shift.shift_id,
            window.work_date,
        ):
            raise TimekeepingError("TIMEKEEPING_ASSIGNMENT_DENIED")
        blocked = consent_is_blocked(context)
        requires_review = not blocked and (
            command.decision_confidence is None
            or command.decision_confidence < context.minimum_auto_accept_confidence
            or window.ambiguous
        )
        link_type = LinkType.REJECTED if blocked else command.link_type
        event_status = (
            TimekeepingStatus.REVIEW
            if blocked
            else status_for_event(
                window,
                command.occurred_at,
                command.link_type,
                check_in_grace_minutes=shift.check_in_grace_minutes,
                check_out_grace_minutes=shift.check_out_grace_minutes,
                requires_review=requires_review,
            )
        )
        request = TimekeepingIngestionRequest(
            timekeeping_record_id=self._identifier_factory(),
            timekeeping_event_link_id=self._identifier_factory(),
            school_id=context.school_id,
            staff_id=command.staff_id,
            shift_id=shift.shift_id,
            work_date=window.work_date,
            normalized_event_id=command.normalized_event_id,
            link_type=link_type,
            decision_confidence=command.decision_confidence,
            consent_snapshot=(ConsentSnapshot.BLOCKED if blocked else context.consent_snapshot),
            event_status=event_status,
            requires_review=requires_review,
            retention_until=command.retention_until,
            occurred_at=command.occurred_at,
            recorded_at=recorded_at,
        )
        return self._repository.ingest_event(request)

    def get_record(
        self,
        record_id: UUID,
        context: TrustedTimekeepingContext,
    ) -> TimekeepingRecord:
        if record_id.int == 0:
            raise TimekeepingError("TIMEKEEPING_INPUT_INVALID")
        record = self._repository.get_record(record_id, context.school_id)
        if record is None:
            raise TimekeepingError("TIMEKEEPING_NOT_FOUND")
        authorize_record(record, context, operation="read")
        return record

    def correct_record(
        self,
        payload: Mapping[str, object],
        context: TrustedTimekeepingContext,
    ) -> TimekeepingCorrectionOutcome:
        command = parse_correction(payload)
        current = self._repository.get_record(command.timekeeping_record_id, context.school_id)
        if current is None:
            raise TimekeepingError("TIMEKEEPING_NOT_FOUND")
        authorize_record(current, context, operation="correct")
        authorize_correction_approval(current, command.approval_status, context)
        request = TimekeepingCorrectionRequest(
            timekeeping_correction_id=self._identifier_factory(),
            timekeeping_record_id=command.timekeeping_record_id,
            expected_version=command.expected_version,
            to_status=command.to_status,
            to_check_in_at=command.to_check_in_at,
            to_check_out_at=command.to_check_out_at,
            reason_code=command.reason_code,
            approval_status=command.approval_status,
            approver_id=(
                context.actor_id
                if command.approval_status in {ApprovalStatus.APPROVED, ApprovalStatus.REJECTED}
                else None
            ),
            request_id=command.request_id,
            changed_at=self._clock(),
        )
        return self._repository.correct_record(request, context)
