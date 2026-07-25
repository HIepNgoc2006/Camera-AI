"""Pure immutable timekeeping models and shift-time rules."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from enum import StrEnum
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from timekeeping_service.domain.errors import TimekeepingError

STABLE_CODE = re.compile(r"^[a-z][a-z0-9_.:-]{0,63}$")
UPPER_CODE = re.compile(r"^[A-Z][A-Z0-9_]{1,63}$")
REQUEST_ID = re.compile(r"^req_[A-Za-z0-9_-]{8,120}$")
SHIFT_CODE = re.compile(r"^[A-Z][A-Z0-9_-]{1,31}$")
CORRECTION_REASON_CODES = frozenset(
    {
        "MISSED_CHECK_IN",
        "MISSED_CHECK_OUT",
        "REVIEW_RESOLUTION",
        "SHIFT_OVERRIDE",
        "TIME_ADJUSTMENT",
    }
)


class ShiftStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    RETIRED = "retired"


class AssignmentStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    ENDED = "ended"


class TimekeepingStatus(StrEnum):
    PENDING = "pending"
    PRESENT = "present"
    LATE = "late"
    EARLY_LEAVE = "early_leave"
    ABSENT = "absent"
    REVIEW = "review"


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


class TimekeepingRole(StrEnum):
    STAFF_SELF = "staff_self"
    HR = "hr"
    BGH = "bgh"
    SYSTEM_ADMIN = "system_admin"


def _nonzero(*values: UUID | None) -> None:
    if any(value is not None and value.int == 0 for value in values):
        raise TimekeepingError("TIMEKEEPING_INPUT_INVALID")


def _aware(*values: datetime | None) -> None:
    if any(
        value is not None and (value.tzinfo is None or value.utcoffset() is None)
        for value in values
    ):
        raise TimekeepingError("TIMEKEEPING_INPUT_INVALID")


def _matches(value: str | None, pattern: re.Pattern[str]) -> None:
    if value is not None and pattern.fullmatch(value) is None:
        raise TimekeepingError("TIMEKEEPING_INPUT_INVALID")


def _safe_label(value: str) -> None:
    if not 1 <= len(value) <= 100 or any(ord(character) < 32 for character in value):
        raise TimekeepingError("TIMEKEEPING_INPUT_INVALID")


@dataclass(frozen=True, slots=True)
class Shift:
    shift_id: UUID
    school_id: UUID
    code: str
    name: str
    timezone: str
    start_local_time: time
    end_local_time: time
    overnight: bool
    check_in_grace_minutes: int
    check_out_grace_minutes: int
    status: ShiftStatus
    version: int
    valid_from: datetime
    valid_to: datetime | None
    created_at: datetime

    def __post_init__(self) -> None:
        _nonzero(self.shift_id, self.school_id)
        _matches(self.code, SHIFT_CODE)
        _safe_label(self.name)
        _aware(self.valid_from, self.valid_to, self.created_at)
        try:
            ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError:
            raise TimekeepingError("TIMEKEEPING_INPUT_INVALID") from None
        if self.version < 1 or not 0 <= self.check_in_grace_minutes <= 240:
            raise TimekeepingError("TIMEKEEPING_INPUT_INVALID")
        if not 0 <= self.check_out_grace_minutes <= 240:
            raise TimekeepingError("TIMEKEEPING_INPUT_INVALID")
        if self.start_local_time == self.end_local_time:
            raise TimekeepingError("TIMEKEEPING_INPUT_INVALID")
        if self.overnight != (self.end_local_time < self.start_local_time):
            raise TimekeepingError("TIMEKEEPING_INPUT_INVALID")
        if self.valid_to is not None and self.valid_to <= self.valid_from:
            raise TimekeepingError("TIMEKEEPING_INPUT_INVALID")
        if self.status is ShiftStatus.ACTIVE and self.valid_to is not None:
            raise TimekeepingError("TIMEKEEPING_INPUT_INVALID")
        if self.status is ShiftStatus.RETIRED and self.valid_to is None:
            raise TimekeepingError("TIMEKEEPING_INPUT_INVALID")

    def is_effective_at(self, instant: datetime) -> bool:
        _aware(instant)
        return (
            self.status in {ShiftStatus.ACTIVE, ShiftStatus.RETIRED}
            and instant >= self.valid_from
            and (self.valid_to is None or instant < self.valid_to)
        )


@dataclass(frozen=True, slots=True)
class StaffShiftAssignment:
    staff_shift_assignment_id: UUID
    school_id: UUID
    staff_id: UUID
    shift_id: UUID
    valid_from: date
    valid_to: date | None
    status: AssignmentStatus
    created_at: datetime
    updated_at: datetime
    row_version: int

    def __post_init__(self) -> None:
        _nonzero(
            self.staff_shift_assignment_id,
            self.school_id,
            self.staff_id,
            self.shift_id,
        )
        _aware(self.created_at, self.updated_at)
        if self.valid_to is not None and self.valid_to < self.valid_from:
            raise TimekeepingError("TIMEKEEPING_INPUT_INVALID")
        if self.updated_at < self.created_at or self.row_version < 1:
            raise TimekeepingError("TIMEKEEPING_INPUT_INVALID")

    def applies_on(self, work_date: date) -> bool:
        return (
            self.status is AssignmentStatus.ACTIVE
            and work_date >= self.valid_from
            and (self.valid_to is None or work_date <= self.valid_to)
        )


@dataclass(frozen=True, slots=True)
class ShiftWindow:
    work_date: date
    scheduled_start_at: datetime
    scheduled_end_at: datetime
    ambiguous: bool

    def __post_init__(self) -> None:
        _aware(self.scheduled_start_at, self.scheduled_end_at)
        if self.scheduled_end_at <= self.scheduled_start_at:
            raise TimekeepingError("TIMEKEEPING_INPUT_INVALID")


def scheduled_shift_window(shift: Shift, work_date: date) -> ShiftWindow:
    zone = ZoneInfo(shift.timezone)
    scheduled_start = datetime.combine(work_date, shift.start_local_time, tzinfo=zone)
    end_date = work_date + timedelta(days=1) if shift.overnight else work_date
    scheduled_end = datetime.combine(end_date, shift.end_local_time, tzinfo=zone)
    return ShiftWindow(work_date, scheduled_start, scheduled_end, ambiguous=False)


def derive_shift_window(shift: Shift, occurred_at: datetime, link_type: LinkType) -> ShiftWindow:
    """Resolve overnight work date against the closest applicable start/end anchor."""

    _aware(occurred_at)
    local_date = occurred_at.astimezone(ZoneInfo(shift.timezone)).date()
    if not shift.overnight:
        return scheduled_shift_window(shift, local_date)
    candidates = (
        scheduled_shift_window(shift, local_date - timedelta(days=1)),
        scheduled_shift_window(shift, local_date),
    )
    anchor_name = "scheduled_end_at" if link_type is LinkType.CHECK_OUT else "scheduled_start_at"
    distances = tuple(
        abs((occurred_at - getattr(candidate, anchor_name)).total_seconds())
        for candidate in candidates
    )
    selected = candidates[0] if distances[0] <= distances[1] else candidates[1]
    return replace(selected, ambiguous=distances[0] == distances[1])


def status_for_event(
    window: ShiftWindow,
    occurred_at: datetime,
    link_type: LinkType,
    *,
    check_in_grace_minutes: int,
    check_out_grace_minutes: int,
    requires_review: bool,
) -> TimekeepingStatus:
    _aware(occurred_at)
    if requires_review or window.ambiguous or link_type is LinkType.SUPPORTING:
        return TimekeepingStatus.REVIEW
    if link_type is LinkType.CHECK_IN:
        limit = window.scheduled_start_at + timedelta(minutes=check_in_grace_minutes)
        return TimekeepingStatus.LATE if occurred_at > limit else TimekeepingStatus.PRESENT
    if link_type is LinkType.CHECK_OUT:
        limit = window.scheduled_end_at - timedelta(minutes=check_out_grace_minutes)
        return TimekeepingStatus.EARLY_LEAVE if occurred_at < limit else TimekeepingStatus.PRESENT
    raise TimekeepingError("TIMEKEEPING_INPUT_INVALID")


@dataclass(frozen=True, slots=True)
class TimekeepingRecord:
    timekeeping_record_id: UUID
    school_id: UUID
    staff_id: UUID
    shift_id: UUID
    work_date: date
    check_in_at: datetime | None
    check_out_at: datetime | None
    status: TimekeepingStatus
    source_type: SourceType
    review_status: ReviewStatus
    retention_until: datetime
    created_at: datetime
    updated_at: datetime
    row_version: int

    def __post_init__(self) -> None:
        _nonzero(self.timekeeping_record_id, self.school_id, self.staff_id, self.shift_id)
        _aware(
            self.check_in_at,
            self.check_out_at,
            self.retention_until,
            self.created_at,
            self.updated_at,
        )
        if self.row_version < 1 or self.updated_at < self.created_at:
            raise TimekeepingError("TIMEKEEPING_INPUT_INVALID")
        if self.retention_until <= self.created_at:
            raise TimekeepingError("TIMEKEEPING_INPUT_INVALID")
        if (
            self.check_in_at is not None
            and self.check_out_at is not None
            and self.check_out_at < self.check_in_at
        ):
            raise TimekeepingError("TIMEKEEPING_INPUT_INVALID")
        if (self.status is TimekeepingStatus.REVIEW) != (
            self.review_status is ReviewStatus.PENDING
        ):
            raise TimekeepingError("TIMEKEEPING_INPUT_INVALID")


@dataclass(frozen=True, slots=True)
class TimekeepingEventLink:
    timekeeping_event_link_id: UUID
    timekeeping_record_id: UUID
    normalized_event_id: UUID
    link_type: LinkType
    decision_confidence: Decimal | None
    consent_snapshot: ConsentSnapshot
    occurred_at: datetime
    recorded_at: datetime

    def __post_init__(self) -> None:
        _nonzero(
            self.timekeeping_event_link_id,
            self.timekeeping_record_id,
            self.normalized_event_id,
        )
        _aware(self.occurred_at, self.recorded_at)
        if self.recorded_at < self.occurred_at:
            raise TimekeepingError("TIMEKEEPING_INPUT_INVALID")
        if self.decision_confidence is not None and not (
            Decimal("0") <= self.decision_confidence <= Decimal("1")
        ):
            raise TimekeepingError("TIMEKEEPING_INPUT_INVALID")
        if (
            self.consent_snapshot is ConsentSnapshot.BLOCKED
            and self.link_type is not LinkType.REJECTED
        ):
            raise TimekeepingError("TIMEKEEPING_INPUT_INVALID")


@dataclass(frozen=True, slots=True)
class TimekeepingCorrection:
    timekeeping_correction_id: UUID
    timekeeping_record_id: UUID
    from_status: TimekeepingStatus
    to_status: TimekeepingStatus
    from_check_in_at: datetime | None
    to_check_in_at: datetime | None
    from_check_out_at: datetime | None
    to_check_out_at: datetime | None
    reason_code: str
    actor_id: UUID
    approval_status: ApprovalStatus
    approver_id: UUID | None
    request_id: str
    occurred_at: datetime
    recorded_at: datetime

    def __post_init__(self) -> None:
        _nonzero(
            self.timekeeping_correction_id,
            self.timekeeping_record_id,
            self.actor_id,
            self.approver_id,
        )
        _aware(
            self.from_check_in_at,
            self.to_check_in_at,
            self.from_check_out_at,
            self.to_check_out_at,
            self.occurred_at,
            self.recorded_at,
        )
        _matches(self.reason_code, UPPER_CODE)
        _matches(self.request_id, REQUEST_ID)
        if self.reason_code not in CORRECTION_REASON_CODES:
            raise TimekeepingError("TIMEKEEPING_INPUT_INVALID")
        decided = self.approval_status in {ApprovalStatus.APPROVED, ApprovalStatus.REJECTED}
        if decided != (self.approver_id is not None):
            raise TimekeepingError("TIMEKEEPING_INPUT_INVALID")


@dataclass(frozen=True, slots=True)
class TrustedIngestionContext:
    school_id: UUID
    consent_snapshot: ConsentSnapshot
    purpose_code: str
    relationship_verified: bool
    biometric_processing: bool
    minimum_auto_accept_confidence: Decimal

    def __post_init__(self) -> None:
        _nonzero(self.school_id)
        _matches(self.purpose_code, STABLE_CODE)
        if not Decimal("0") <= self.minimum_auto_accept_confidence <= Decimal("1"):
            raise TimekeepingError("TIMEKEEPING_INPUT_INVALID")


@dataclass(frozen=True, slots=True)
class TrustedTimekeepingContext:
    school_id: UUID
    actor_id: UUID
    actor_staff_id: UUID | None
    role: TimekeepingRole
    authorized_staff_ids: frozenset[UUID]
    school_wide_access: bool
    permission_codes: frozenset[str]
    relationship_verified: bool

    def __post_init__(self) -> None:
        _nonzero(
            self.school_id,
            self.actor_id,
            self.actor_staff_id,
            *self.authorized_staff_ids,
        )
        if any(STABLE_CODE.fullmatch(code) is None for code in self.permission_codes):
            raise TimekeepingError("TIMEKEEPING_INPUT_INVALID")


@dataclass(frozen=True, slots=True)
class TimekeepingIngestionRequest:
    timekeeping_record_id: UUID
    timekeeping_event_link_id: UUID
    school_id: UUID
    staff_id: UUID
    shift_id: UUID
    work_date: date
    normalized_event_id: UUID
    link_type: LinkType
    decision_confidence: Decimal | None
    consent_snapshot: ConsentSnapshot
    event_status: TimekeepingStatus
    requires_review: bool
    retention_until: datetime
    occurred_at: datetime
    recorded_at: datetime


@dataclass(frozen=True, slots=True)
class TimekeepingIngestionOutcome:
    record: TimekeepingRecord | None
    event_link: TimekeepingEventLink | None
    duplicate: bool
    blocked: bool


@dataclass(frozen=True, slots=True)
class TimekeepingCorrectionRequest:
    timekeeping_correction_id: UUID
    timekeeping_record_id: UUID
    expected_version: int
    to_status: TimekeepingStatus
    to_check_in_at: datetime | None
    to_check_out_at: datetime | None
    reason_code: str
    approval_status: ApprovalStatus
    approver_id: UUID | None
    request_id: str
    changed_at: datetime


@dataclass(frozen=True, slots=True)
class TimekeepingAuditIntent:
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
class TimekeepingCorrectionOutcome:
    record: TimekeepingRecord
    correction: TimekeepingCorrection
    audit_intent: TimekeepingAuditIntent


def apply_correction(
    record: TimekeepingRecord,
    request: TimekeepingCorrectionRequest,
) -> TimekeepingRecord:
    _aware(request.to_check_in_at, request.to_check_out_at, request.changed_at)
    if request.expected_version < 1 or request.changed_at < record.updated_at:
        raise TimekeepingError("TIMEKEEPING_INPUT_INVALID")
    if (
        request.to_check_in_at is not None
        and request.to_check_out_at is not None
        and request.to_check_out_at < request.to_check_in_at
    ):
        raise TimekeepingError("TIMEKEEPING_INPUT_INVALID")
    if request.approval_status in {ApprovalStatus.PENDING, ApprovalStatus.REJECTED}:
        return record
    if request.to_status is TimekeepingStatus.REVIEW:
        raise TimekeepingError("TIMEKEEPING_INPUT_INVALID")
    review_status = (
        ReviewStatus.APPROVED
        if request.approval_status is ApprovalStatus.APPROVED
        else ReviewStatus.NOT_REQUIRED
    )
    return replace(
        record,
        status=request.to_status,
        check_in_at=request.to_check_in_at,
        check_out_at=request.to_check_out_at,
        source_type=SourceType.MANUAL,
        review_status=review_status,
        updated_at=request.changed_at,
        row_version=record.row_version + 1,
    )
