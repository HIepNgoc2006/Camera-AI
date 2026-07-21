"""Fail-closed ingestion and object-level attendance authorization."""

from __future__ import annotations

from attendance_service.domain.errors import AttendanceError
from attendance_service.domain.models import (
    ApprovalStatus,
    AttendanceRecord,
    AttendanceRole,
    AttendanceStatus,
    TrustedAttendanceContext,
    TrustedIngestionContext,
)


def ingestion_is_allowed(context: TrustedIngestionContext) -> bool:
    """Permit only the approved purpose with a resolved subject relationship."""

    return context.relationship_verified and context.purpose_code == "student_attendance"


def authorize_record(
    record: AttendanceRecord,
    context: TrustedAttendanceContext,
    *,
    operation: str,
) -> None:
    """Enforce tenant, role, object relationship, and explicit permission together."""

    if (
        record.school_id != context.school_id
        or not context.relationship_verified
        or context.role is AttendanceRole.SYSTEM_ADMIN
        or operation not in {"read", "correct", "review"}
        or f"attendance.{operation}" not in context.permission_codes
    ):
        raise AttendanceError("ATTENDANCE_AUTHORITY_DENIED")

    if context.role is AttendanceRole.BGH:
        return
    if context.role is AttendanceRole.TEACHER and record.class_id in context.assigned_class_ids:
        return
    if (
        operation == "read"
        and context.role is AttendanceRole.PARENT
        and record.student_id in context.linked_student_ids
    ):
        return
    raise AttendanceError("ATTENDANCE_AUTHORITY_DENIED")


def authorize_correction_approval(
    approval_status: ApprovalStatus,
    to_status: AttendanceStatus,
    context: TrustedAttendanceContext,
) -> None:
    """A decided correction requires the separately granted review permission."""

    if context.role is AttendanceRole.TEACHER:
        if approval_status is ApprovalStatus.PENDING:
            return
        raise AttendanceError("ATTENDANCE_AUTHORITY_DENIED")
    if context.role is not AttendanceRole.BGH:
        raise AttendanceError("ATTENDANCE_AUTHORITY_DENIED")
    if approval_status in {ApprovalStatus.APPROVED, ApprovalStatus.REJECTED} and (
        "attendance.review" not in context.permission_codes
    ):
        raise AttendanceError("ATTENDANCE_AUTHORITY_DENIED")
    if approval_status is ApprovalStatus.APPROVED and to_status is AttendanceStatus.PENDING_REVIEW:
        raise AttendanceError("ATTENDANCE_AUTHORITY_DENIED")
