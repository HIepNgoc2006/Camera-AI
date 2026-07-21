"""Attendance use cases over trusted contexts and strict internal commands."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from attendance_service.application.ports import AttendanceRepository
from attendance_service.domain.errors import AttendanceError
from attendance_service.domain.models import (
    ApprovalStatus,
    AttendanceCorrectionOutcome,
    AttendanceCorrectionRequest,
    AttendanceIngestionOutcome,
    AttendanceIngestionRequest,
    AttendanceRecord,
    ConsentSnapshot,
    LinkType,
    TrustedAttendanceContext,
    TrustedIngestionContext,
)
from attendance_service.domain.policies import (
    authorize_correction_approval,
    authorize_record,
    ingestion_is_allowed,
)
from attendance_service.schemas.commands import parse_apply_event, parse_correction


class AttendanceApplicationService:
    def __init__(
        self,
        repository: AttendanceRepository,
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
    ) -> AttendanceIngestionOutcome:
        command = parse_apply_event(payload)
        if not ingestion_is_allowed(context):
            raise AttendanceError("ATTENDANCE_AUTHORITY_DENIED")
        recorded_at = self._clock()
        if recorded_at.tzinfo is None or recorded_at.utcoffset() is None:
            raise AttendanceError("ATTENDANCE_INPUT_INVALID")
        if command.retention_until <= recorded_at:
            raise AttendanceError("ATTENDANCE_INPUT_INVALID")
        if command.occurred_at > recorded_at:
            raise AttendanceError("ATTENDANCE_INPUT_INVALID")
        request = AttendanceIngestionRequest(
            attendance_record_id=self._identifier_factory(),
            attendance_event_link_id=self._identifier_factory(),
            school_id=context.school_id,
            student_id=command.student_id,
            class_id=command.class_id,
            attendance_date=command.occurred_at.astimezone(
                ZoneInfo(command.school_timezone)
            ).date(),
            normalized_event_id=command.normalized_event_id,
            link_type=(
                command.link_type
                if context.consent_snapshot is not ConsentSnapshot.BLOCKED
                else LinkType.REJECTED
            ),
            decision_confidence=command.decision_confidence,
            consent_snapshot=context.consent_snapshot,
            requires_review=(
                context.consent_snapshot is not ConsentSnapshot.BLOCKED
                and (
                    command.decision_confidence is None
                    or command.decision_confidence < context.minimum_auto_accept_confidence
                )
            ),
            retention_until=command.retention_until,
            occurred_at=command.occurred_at,
            recorded_at=recorded_at,
        )
        return self._repository.ingest_event(request)

    def get_record(
        self,
        record_id: UUID,
        context: TrustedAttendanceContext,
    ) -> AttendanceRecord:
        if record_id.int == 0:
            raise AttendanceError("ATTENDANCE_INPUT_INVALID")
        record = self._repository.get_record(record_id, context.school_id)
        if record is None:
            raise AttendanceError("ATTENDANCE_NOT_FOUND")
        authorize_record(record, context, operation="read")
        return record

    def correct_record(
        self,
        payload: Mapping[str, object],
        context: TrustedAttendanceContext,
    ) -> AttendanceCorrectionOutcome:
        command = parse_correction(payload)
        current = self._repository.get_record(command.attendance_record_id, context.school_id)
        if current is None:
            raise AttendanceError("ATTENDANCE_NOT_FOUND")
        authorize_record(current, context, operation="correct")
        authorize_correction_approval(command.approval_status, command.to_status, context)
        request = AttendanceCorrectionRequest(
            attendance_correction_id=self._identifier_factory(),
            attendance_record_id=command.attendance_record_id,
            expected_version=command.expected_version,
            to_status=command.to_status,
            to_check_in_at=command.to_check_in_at,
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
