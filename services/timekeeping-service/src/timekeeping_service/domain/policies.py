"""Fail-closed ingestion and object-level timekeeping authorization."""

from __future__ import annotations

from timekeeping_service.domain.errors import TimekeepingError
from timekeeping_service.domain.models import (
    ApprovalStatus,
    ConsentSnapshot,
    TimekeepingRecord,
    TimekeepingRole,
    TrustedIngestionContext,
    TrustedTimekeepingContext,
)


def ingestion_is_allowed(context: TrustedIngestionContext) -> bool:
    return context.relationship_verified and context.purpose_code == "staff_timekeeping"


def consent_is_blocked(context: TrustedIngestionContext) -> bool:
    if context.consent_snapshot is ConsentSnapshot.BLOCKED:
        return True
    return context.biometric_processing and context.consent_snapshot is not ConsentSnapshot.ALLOWED


def authorize_record(
    record: TimekeepingRecord,
    context: TrustedTimekeepingContext,
    *,
    operation: str,
) -> None:
    if (
        record.school_id != context.school_id
        or not context.relationship_verified
        or context.role is TimekeepingRole.SYSTEM_ADMIN
        or operation not in {"read", "correct", "review"}
        or f"timekeeping.{operation}" not in context.permission_codes
    ):
        raise TimekeepingError("TIMEKEEPING_AUTHORITY_DENIED")
    if context.role is TimekeepingRole.BGH and context.school_wide_access:
        return
    if context.role is TimekeepingRole.HR and (
        context.school_wide_access or record.staff_id in context.authorized_staff_ids
    ):
        return
    if (
        context.role is TimekeepingRole.STAFF_SELF
        and context.actor_staff_id == record.staff_id
        and operation in {"read", "correct"}
    ):
        return
    raise TimekeepingError("TIMEKEEPING_AUTHORITY_DENIED")


def authorize_correction_approval(
    record: TimekeepingRecord,
    approval_status: ApprovalStatus,
    context: TrustedTimekeepingContext,
) -> None:
    if approval_status is ApprovalStatus.PENDING:
        return
    if context.role not in {TimekeepingRole.HR, TimekeepingRole.BGH}:
        raise TimekeepingError("TIMEKEEPING_AUTHORITY_DENIED")
    if "timekeeping.review" not in context.permission_codes:
        raise TimekeepingError("TIMEKEEPING_AUTHORITY_DENIED")
    if context.actor_staff_id is not None and context.actor_staff_id == record.staff_id:
        raise TimekeepingError("TIMEKEEPING_AUTHORITY_DENIED")
