from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID

import pytest
from timekeeping_service.domain.errors import TimekeepingError
from timekeeping_service.domain.models import (
    ApprovalStatus,
    LinkType,
    ReviewStatus,
    Shift,
    ShiftStatus,
    SourceType,
    TimekeepingCorrectionRequest,
    TimekeepingRecord,
    TimekeepingRole,
    TimekeepingStatus,
    TrustedTimekeepingContext,
    apply_correction,
    derive_shift_window,
    status_for_event,
)
from timekeeping_service.domain.policies import (
    authorize_correction_approval,
    authorize_record,
)

NOW = datetime(2026, 7, 25, 15, 0, tzinfo=UTC)
SCHOOL_ID = UUID("00000000-0000-4000-8000-000000000801")
STAFF_ID = UUID("00000000-0000-4000-8000-000000000802")
SHIFT_ID = UUID("00000000-0000-4000-8000-000000000803")
ACTOR_ID = UUID("00000000-0000-4000-8000-000000000804")
RECORD_ID = UUID("00000000-0000-4000-8000-000000000805")


def _shift() -> Shift:
    return Shift(
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


def _record() -> TimekeepingRecord:
    return TimekeepingRecord(
        timekeeping_record_id=RECORD_ID,
        school_id=SCHOOL_ID,
        staff_id=STAFF_ID,
        shift_id=SHIFT_ID,
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


def _context(
    role: TimekeepingRole,
    *,
    school_id: UUID = SCHOOL_ID,
    actor_staff_id: UUID | None = None,
    staff_ids: frozenset[UUID] = frozenset(),
    school_wide: bool = False,
    permissions: frozenset[str] = frozenset({"timekeeping.read"}),
    verified: bool = True,
) -> TrustedTimekeepingContext:
    return TrustedTimekeepingContext(
        school_id=school_id,
        actor_id=ACTOR_ID,
        actor_staff_id=actor_staff_id,
        role=role,
        authorized_staff_ids=staff_ids,
        school_wide_access=school_wide,
        permission_codes=permissions,
        relationship_verified=verified,
    )


def test_overnight_work_date_uses_shift_start_for_check_in_and_end_for_check_out() -> None:
    check_in = datetime(2026, 7, 25, 15, 5, tzinfo=UTC)
    check_out = datetime(2026, 7, 25, 22, 5, tzinfo=UTC)

    check_in_window = derive_shift_window(_shift(), check_in, link_type=LinkType.CHECK_IN)
    check_out_window = derive_shift_window(_shift(), check_out, link_type=LinkType.CHECK_OUT)

    assert check_in_window.work_date == date(2026, 7, 25)
    assert check_out_window.work_date == date(2026, 7, 25)
    assert check_out_window.scheduled_end_at.date() == date(2026, 7, 26)


@pytest.mark.parametrize(
    ("occurred_at", "link_type", "expected"),
    [
        (datetime(2026, 7, 25, 15, 15, tzinfo=UTC), "check_in", TimekeepingStatus.PRESENT),
        (datetime(2026, 7, 25, 15, 16, tzinfo=UTC), "check_in", TimekeepingStatus.LATE),
        (datetime(2026, 7, 25, 22, 45, tzinfo=UTC), "check_out", TimekeepingStatus.PRESENT),
        (
            datetime(2026, 7, 25, 22, 44, tzinfo=UTC),
            "check_out",
            TimekeepingStatus.EARLY_LEAVE,
        ),
    ],
)
def test_exact_grace_boundaries(
    occurred_at: datetime,
    link_type: str,
    expected: TimekeepingStatus,
) -> None:
    typed_link = LinkType(link_type)
    window = derive_shift_window(_shift(), occurred_at, typed_link)
    assert (
        status_for_event(
            window,
            occurred_at,
            typed_link,
            check_in_grace_minutes=15,
            check_out_grace_minutes=15,
            requires_review=False,
        )
        is expected
    )


@pytest.mark.parametrize(
    "context",
    [
        _context(TimekeepingRole.STAFF_SELF, actor_staff_id=STAFF_ID),
        _context(TimekeepingRole.HR, staff_ids=frozenset({STAFF_ID})),
        _context(TimekeepingRole.BGH, school_wide=True),
    ],
)
def test_self_hr_and_bgh_authorized_scopes(context: TrustedTimekeepingContext) -> None:
    authorize_record(_record(), context, operation="read")


@pytest.mark.parametrize(
    "context",
    [
        _context(TimekeepingRole.STAFF_SELF),
        _context(TimekeepingRole.HR),
        _context(TimekeepingRole.BGH),
        _context(TimekeepingRole.SYSTEM_ADMIN, school_wide=True),
        _context(
            TimekeepingRole.BGH,
            school_id=UUID("00000000-0000-4000-8000-000000000899"),
            school_wide=True,
        ),
        _context(TimekeepingRole.BGH, school_wide=True, verified=False),
    ],
)
def test_wrong_object_school_relationship_and_admin_fail_closed(
    context: TrustedTimekeepingContext,
) -> None:
    with pytest.raises(TimekeepingError, match="TIMEKEEPING_AUTHORITY_DENIED"):
        authorize_record(_record(), context, operation="read")


def test_staff_can_request_but_cannot_approve_own_correction() -> None:
    context = _context(
        TimekeepingRole.STAFF_SELF,
        actor_staff_id=STAFF_ID,
        permissions=frozenset({"timekeeping.correct", "timekeeping.review"}),
    )
    authorize_correction_approval(_record(), ApprovalStatus.PENDING, context)
    with pytest.raises(TimekeepingError, match="TIMEKEEPING_AUTHORITY_DENIED"):
        authorize_correction_approval(_record(), ApprovalStatus.APPROVED, context)


def test_approved_typed_correction_changes_both_times_and_version() -> None:
    check_out = NOW + timedelta(hours=8)
    request = TimekeepingCorrectionRequest(
        timekeeping_correction_id=UUID("00000000-0000-4000-8000-000000000806"),
        timekeeping_record_id=RECORD_ID,
        expected_version=1,
        to_status=TimekeepingStatus.LATE,
        to_check_in_at=NOW + timedelta(minutes=20),
        to_check_out_at=check_out,
        reason_code="TIME_ADJUSTMENT",
        approval_status=ApprovalStatus.APPROVED,
        approver_id=ACTOR_ID,
        request_id="req_0123456789abcdef",
        changed_at=check_out + timedelta(minutes=1),
    )

    updated = apply_correction(_record(), request)

    assert updated.status is TimekeepingStatus.LATE
    assert updated.check_out_at == check_out
    assert updated.source_type is SourceType.MANUAL
    assert updated.row_version == 2


def test_pending_correction_is_append_only_intent_without_record_mutation() -> None:
    request = TimekeepingCorrectionRequest(
        timekeeping_correction_id=UUID("00000000-0000-4000-8000-000000000806"),
        timekeeping_record_id=RECORD_ID,
        expected_version=1,
        to_status=TimekeepingStatus.PRESENT,
        to_check_in_at=NOW,
        to_check_out_at=None,
        reason_code="MISSED_CHECK_OUT",
        approval_status=ApprovalStatus.PENDING,
        approver_id=None,
        request_id="req_0123456789abcdef",
        changed_at=NOW + timedelta(minutes=1),
    )
    assert apply_correction(_record(), request) == _record()
