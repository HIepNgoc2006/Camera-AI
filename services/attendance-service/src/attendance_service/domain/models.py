"""Pure immutable attendance models and transition rules."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from attendance_service.domain.errors import AttendanceError

STABLE_CODE = re.compile(r"^[a-z][a-z0-9_.:-]{0,63}$")
UPPER_CODE = re.compile(r"^[A-Z][A-Z0-9_]{1,63}$")
REQUEST_ID = re.compile(r"^req_[A-Za-z0-9_-]{8,120}$")
CORRECTION_REASON_CODES = frozenset(
    {
        "EXCUSED_ABSENCE",
        "MANUAL_CORRECTION",
        "REVIEW_RESOLUTION",
        "TIME_ADJUSTMENT",
    }
)


class AttendanceStatus(StrEnum):
    PRESENT = "present"
    ABSENT = "absent"
    LATE = "late"
    EXCUSED = "excused"
    PENDING_REVIEW = "pending_review"


class SourceType(StrEnum):
    AI = "ai"
    MANUAL = "manual"
    IMPORT = "import"


class ReviewStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    NOT_REQUIRED = "not_required"


class LinkType(StrEnum):
    CHECK_IN = "check_in"
    CHECK_OUT = "check_out"
    SUPPORTING = "supporting"
    REJECTED = "rejected"


class ConsentSnapshot(StrEnum):
    ALLOWED = "allowed"
    BLOCKED = "blocked"
    NOT_REQUIRED = "not_required"


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    NOT_REQUIRED = "not_required"


class AttendanceRole(StrEnum):
    BGH = "bgh"
    TEACHER = "teacher"
    PARENT = "parent"
    SYSTEM_ADMIN = "system_admin"


def _nonzero(*values: UUID | None) -> None:
    if any(value is not None and value.int == 0 for value in values):
        raise AttendanceError("ATTENDANCE_INPUT_INVALID")


def _aware(*values: datetime | None) -> None:
    if any(
        value is not None and (value.tzinfo is None or value.utcoffset() is None)
        for value in values
    ):
        raise AttendanceError("ATTENDANCE_INPUT_INVALID")


def _matches(value: str | None, pattern: re.Pattern[str]) -> None:
    if value is not None and pattern.fullmatch(value) is None:
        raise AttendanceError("ATTENDANCE_INPUT_INVALID")


@dataclass(frozen=True, slots=True)
class AttendanceRecord:
    attendance_record_id: UUID
    school_id: UUID
    student_id: UUID
    class_id: UUID
    attendance_date: date
    status: AttendanceStatus
    first_check_in_at: datetime | None
    last_check_out_at: datetime | None
    source_type: SourceType
    review_status: ReviewStatus
    retention_until: datetime
    created_at: datetime
    updated_at: datetime
    row_version: int

    def __post_init__(self) -> None:
        _nonzero(self.attendance_record_id, self.school_id, self.student_id, self.class_id)
        _aware(
            self.first_check_in_at,
            self.last_check_out_at,
            self.retention_until,
            self.created_at,
            self.updated_at,
        )
        if self.row_version < 1 or self.updated_at < self.created_at:
            raise AttendanceError("ATTENDANCE_INPUT_INVALID")
        if self.retention_until <= self.created_at:
            raise AttendanceError("ATTENDANCE_INPUT_INVALID")
        if (
            self.first_check_in_at is not None
            and self.last_check_out_at is not None
            and self.last_check_out_at < self.first_check_in_at
        ):
            raise AttendanceError("ATTENDANCE_INPUT_INVALID")
        if (self.status is AttendanceStatus.PENDING_REVIEW) != (
            self.review_status is ReviewStatus.PENDING
        ):
            raise AttendanceError("ATTENDANCE_INPUT_INVALID")


@dataclass(frozen=True, slots=True)
class AttendanceEventLink:
    attendance_event_link_id: UUID
    attendance_record_id: UUID
    normalized_event_id: UUID
    link_type: LinkType
    decision_confidence: Decimal | None
    consent_snapshot: ConsentSnapshot
    occurred_at: datetime
    recorded_at: datetime

    def __post_init__(self) -> None:
        _nonzero(
            self.attendance_event_link_id,
            self.attendance_record_id,
            self.normalized_event_id,
        )
        _aware(self.occurred_at, self.recorded_at)
        if self.decision_confidence is not None and not (
            Decimal("0") <= self.decision_confidence <= Decimal("1")
        ):
            raise AttendanceError("ATTENDANCE_INPUT_INVALID")
        if (
            self.consent_snapshot is ConsentSnapshot.BLOCKED
            and self.link_type is not LinkType.REJECTED
        ):
            raise AttendanceError("ATTENDANCE_INPUT_INVALID")


@dataclass(frozen=True, slots=True)
class AttendanceCorrection:
    attendance_correction_id: UUID
    attendance_record_id: UUID
    from_status: AttendanceStatus
    to_status: AttendanceStatus
    from_check_in_at: datetime | None
    to_check_in_at: datetime | None
    reason_code: str
    actor_id: UUID
    approval_status: ApprovalStatus
    approver_id: UUID | None
    request_id: str
    occurred_at: datetime
    recorded_at: datetime

    def __post_init__(self) -> None:
        _nonzero(
            self.attendance_correction_id,
            self.attendance_record_id,
            self.actor_id,
            self.approver_id,
        )
        _aware(
            self.from_check_in_at,
            self.to_check_in_at,
            self.occurred_at,
            self.recorded_at,
        )
        _matches(self.reason_code, UPPER_CODE)
        _matches(self.request_id, REQUEST_ID)
        if self.reason_code not in CORRECTION_REASON_CODES:
            raise AttendanceError("ATTENDANCE_INPUT_INVALID")
        decided = self.approval_status in {ApprovalStatus.APPROVED, ApprovalStatus.REJECTED}
        if decided != (self.approver_id is not None):
            raise AttendanceError("ATTENDANCE_INPUT_INVALID")


@dataclass(frozen=True, slots=True)
class TrustedIngestionContext:
    school_id: UUID
    consent_snapshot: ConsentSnapshot
    purpose_code: str
    relationship_verified: bool
    minimum_auto_accept_confidence: Decimal

    def __post_init__(self) -> None:
        _nonzero(self.school_id)
        _matches(self.purpose_code, STABLE_CODE)
        if not Decimal("0") <= self.minimum_auto_accept_confidence <= Decimal("1"):
            raise AttendanceError("ATTENDANCE_INPUT_INVALID")


@dataclass(frozen=True, slots=True)
class TrustedAttendanceContext:
    school_id: UUID
    actor_id: UUID
    role: AttendanceRole
    assigned_class_ids: frozenset[UUID]
    linked_student_ids: frozenset[UUID]
    permission_codes: frozenset[str]
    relationship_verified: bool

    def __post_init__(self) -> None:
        _nonzero(self.school_id, self.actor_id, *self.assigned_class_ids, *self.linked_student_ids)
        if any(STABLE_CODE.fullmatch(code) is None for code in self.permission_codes):
            raise AttendanceError("ATTENDANCE_INPUT_INVALID")


@dataclass(frozen=True, slots=True)
class AttendanceIngestionRequest:
    attendance_record_id: UUID
    attendance_event_link_id: UUID
    school_id: UUID
    student_id: UUID
    class_id: UUID
    attendance_date: date
    normalized_event_id: UUID
    link_type: LinkType
    decision_confidence: Decimal | None
    consent_snapshot: ConsentSnapshot
    requires_review: bool
    retention_until: datetime
    occurred_at: datetime
    recorded_at: datetime


@dataclass(frozen=True, slots=True)
class AttendanceIngestionOutcome:
    record: AttendanceRecord | None
    event_link: AttendanceEventLink | None
    duplicate: bool
    blocked: bool


@dataclass(frozen=True, slots=True)
class AttendanceCorrectionRequest:
    attendance_correction_id: UUID
    attendance_record_id: UUID
    expected_version: int
    to_status: AttendanceStatus
    to_check_in_at: datetime | None
    reason_code: str
    approval_status: ApprovalStatus
    approver_id: UUID | None
    request_id: str
    changed_at: datetime


@dataclass(frozen=True, slots=True)
class AttendanceAuditIntent:
    source_event_id: UUID
    school_id: UUID
    actor_id: UUID
    action: str
    resource_id: UUID
    request_id: str
    result: str
    state_before: str
    state_after: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class AttendanceCorrectionOutcome:
    record: AttendanceRecord
    correction: AttendanceCorrection
    audit_intent: AttendanceAuditIntent


def apply_correction(
    record: AttendanceRecord, request: AttendanceCorrectionRequest
) -> AttendanceRecord:
    _aware(request.to_check_in_at, request.changed_at)
    if request.expected_version < 1 or request.changed_at < record.updated_at:
        raise AttendanceError("ATTENDANCE_INPUT_INVALID")
    if record.last_check_out_at is not None and (
        request.to_check_in_at is None or record.last_check_out_at < request.to_check_in_at
    ):
        raise AttendanceError("ATTENDANCE_INPUT_INVALID")
    if request.approval_status in {ApprovalStatus.PENDING, ApprovalStatus.REJECTED}:
        return record
    if request.to_status is AttendanceStatus.PENDING_REVIEW:
        raise AttendanceError("ATTENDANCE_INPUT_INVALID")
    review_status = (
        ReviewStatus.APPROVED
        if request.approval_status is ApprovalStatus.APPROVED
        else ReviewStatus.NOT_REQUIRED
    )
    return replace(
        record,
        status=request.to_status,
        first_check_in_at=request.to_check_in_at,
        source_type=SourceType.MANUAL,
        review_status=review_status,
        updated_at=request.changed_at,
        row_version=record.row_version + 1,
    )
