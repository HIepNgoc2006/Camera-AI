from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import UUID

import pytest
from attendance_service.domain.errors import AttendanceError
from attendance_service.domain.models import (
    ApprovalStatus,
    AttendanceCorrectionRequest,
    AttendanceRecord,
    AttendanceRole,
    AttendanceStatus,
    ReviewStatus,
    SourceType,
    TrustedAttendanceContext,
    apply_correction,
)
from attendance_service.domain.policies import authorize_correction_approval, authorize_record

NOW = datetime(2026, 7, 22, 3, 0, tzinfo=UTC)
SCHOOL_ID = UUID("00000000-0000-4000-8000-000000000601")
STUDENT_ID = UUID("00000000-0000-4000-8000-000000000602")
CLASS_ID = UUID("00000000-0000-4000-8000-000000000603")
ACTOR_ID = UUID("00000000-0000-4000-8000-000000000604")
RECORD_ID = UUID("00000000-0000-4000-8000-000000000605")


def _record() -> AttendanceRecord:
    return AttendanceRecord(
        attendance_record_id=RECORD_ID,
        school_id=SCHOOL_ID,
        student_id=STUDENT_ID,
        class_id=CLASS_ID,
        attendance_date=date(2026, 7, 22),
        status=AttendanceStatus.PRESENT,
        first_check_in_at=NOW,
        last_check_out_at=None,
        source_type=SourceType.AI,
        review_status=ReviewStatus.NOT_REQUIRED,
        retention_until=NOW + timedelta(days=30),
        created_at=NOW,
        updated_at=NOW,
        row_version=1,
    )


def _context(
    role: AttendanceRole,
    *,
    school_id: UUID = SCHOOL_ID,
    classes: frozenset[UUID] = frozenset(),
    students: frozenset[UUID] = frozenset(),
    permissions: frozenset[str] = frozenset({"attendance.read"}),
    verified: bool = True,
) -> TrustedAttendanceContext:
    return TrustedAttendanceContext(
        school_id=school_id,
        actor_id=ACTOR_ID,
        role=role,
        assigned_class_ids=classes,
        linked_student_ids=students,
        permission_codes=permissions,
        relationship_verified=verified,
    )


@pytest.mark.parametrize(
    ("context", "operation"),
    [
        (_context(AttendanceRole.BGH), "read"),
        (_context(AttendanceRole.TEACHER, classes=frozenset({CLASS_ID})), "read"),
        (_context(AttendanceRole.PARENT, students=frozenset({STUDENT_ID})), "read"),
        (
            _context(
                AttendanceRole.TEACHER,
                classes=frozenset({CLASS_ID}),
                permissions=frozenset({"attendance.correct"}),
            ),
            "correct",
        ),
    ],
)
def test_authorized_object_scopes(context: TrustedAttendanceContext, operation: str) -> None:
    authorize_record(_record(), context, operation=operation)


@pytest.mark.parametrize(
    "context",
    [
        _context(
            AttendanceRole.BGH,
            school_id=UUID("00000000-0000-4000-8000-000000000699"),
        ),
        _context(AttendanceRole.TEACHER),
        _context(AttendanceRole.PARENT),
        _context(AttendanceRole.SYSTEM_ADMIN),
        _context(AttendanceRole.BGH, verified=False),
    ],
)
def test_wrong_school_object_relationship_and_system_admin_fail_closed(
    context: TrustedAttendanceContext,
) -> None:
    with pytest.raises(AttendanceError, match="ATTENDANCE_AUTHORITY_DENIED"):
        authorize_record(_record(), context, operation="read")


def test_parent_cannot_correct_even_with_injected_permission() -> None:
    context = _context(
        AttendanceRole.PARENT,
        students=frozenset({STUDENT_ID}),
        permissions=frozenset({"attendance.correct"}),
    )
    with pytest.raises(AttendanceError, match="ATTENDANCE_AUTHORITY_DENIED"):
        authorize_record(_record(), context, operation="correct")


def test_teacher_can_submit_pending_intent_but_cannot_self_approve() -> None:
    teacher = _context(
        AttendanceRole.TEACHER,
        classes=frozenset({CLASS_ID}),
        permissions=frozenset({"attendance.correct"}),
    )
    authorize_correction_approval(ApprovalStatus.PENDING, AttendanceStatus.EXCUSED, teacher)
    with pytest.raises(AttendanceError, match="ATTENDANCE_AUTHORITY_DENIED"):
        authorize_correction_approval(
            ApprovalStatus.NOT_REQUIRED,
            AttendanceStatus.EXCUSED,
            teacher,
        )


def test_bgh_decision_requires_review_permission() -> None:
    without_review = _context(
        AttendanceRole.BGH,
        permissions=frozenset({"attendance.correct"}),
    )
    with pytest.raises(AttendanceError, match="ATTENDANCE_AUTHORITY_DENIED"):
        authorize_correction_approval(
            ApprovalStatus.APPROVED,
            AttendanceStatus.EXCUSED,
            without_review,
        )


def test_correction_is_typed_versioned_and_does_not_change_checkout() -> None:
    request = AttendanceCorrectionRequest(
        attendance_correction_id=UUID("00000000-0000-4000-8000-000000000606"),
        attendance_record_id=RECORD_ID,
        expected_version=1,
        to_status=AttendanceStatus.EXCUSED,
        to_check_in_at=NOW + timedelta(minutes=2),
        reason_code="EXCUSED_ABSENCE",
        approval_status=ApprovalStatus.APPROVED,
        approver_id=ACTOR_ID,
        request_id="req_0123456789abcdef",
        changed_at=NOW + timedelta(minutes=3),
    )

    updated = apply_correction(_record(), request)

    assert updated.status is AttendanceStatus.EXCUSED
    assert updated.source_type is SourceType.MANUAL
    assert updated.row_version == 2
    assert updated.last_check_out_at is None


def test_pending_correction_is_an_append_only_intent_and_does_not_change_record() -> None:
    request = AttendanceCorrectionRequest(
        attendance_correction_id=UUID("00000000-0000-4000-8000-000000000606"),
        attendance_record_id=RECORD_ID,
        expected_version=1,
        to_status=AttendanceStatus.PRESENT,
        to_check_in_at=NOW,
        reason_code="MANUAL_CORRECTION",
        approval_status=ApprovalStatus.PENDING,
        approver_id=None,
        request_id="req_0123456789abcdef",
        changed_at=NOW + timedelta(minutes=1),
    )
    assert apply_correction(_record(), request) == _record()
