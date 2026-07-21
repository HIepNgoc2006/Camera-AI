"""Transactional PostgreSQL repository for the Attendance Service-owned schema."""

from __future__ import annotations

import hmac
from datetime import datetime
from decimal import Decimal
from typing import cast
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.engine import Connection, Engine, RowMapping
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from attendance_service.domain.errors import AttendanceError
from attendance_service.domain.models import (
    AttendanceAuditIntent,
    AttendanceCorrection,
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
    apply_correction,
)
from attendance_service.domain.policies import authorize_record
from attendance_service.infrastructure.tables import (
    attendance_corrections,
    attendance_event_links,
    attendance_records,
)


def _uuid(value: object) -> UUID:
    return cast(UUID, value)


def _datetime(value: object) -> datetime:
    return cast(datetime, value)


def _record(row: RowMapping) -> AttendanceRecord:
    return AttendanceRecord(
        attendance_record_id=_uuid(row["attendance_record_id"]),
        school_id=_uuid(row["school_id"]),
        student_id=_uuid(row["student_id"]),
        class_id=_uuid(row["class_id"]),
        attendance_date=row["attendance_date"],
        status=AttendanceStatus(str(row["status"])),
        first_check_in_at=cast(datetime | None, row["first_check_in_at"]),
        last_check_out_at=cast(datetime | None, row["last_check_out_at"]),
        source_type=SourceType(str(row["source_type"])),
        review_status=ReviewStatus(str(row["review_status"])),
        retention_until=_datetime(row["retention_until"]),
        created_at=_datetime(row["created_at"]),
        updated_at=_datetime(row["updated_at"]),
        row_version=int(row["row_version"]),
    )


def _event_link(row: RowMapping) -> AttendanceEventLink:
    return AttendanceEventLink(
        attendance_event_link_id=_uuid(row["attendance_event_link_id"]),
        attendance_record_id=_uuid(row["attendance_record_id"]),
        normalized_event_id=_uuid(row["normalized_event_id"]),
        link_type=LinkType(str(row["link_type"])),
        decision_confidence=(
            None if row["decision_confidence"] is None else Decimal(str(row["decision_confidence"]))
        ),
        consent_snapshot=ConsentSnapshot(str(row["consent_snapshot_status"])),
        occurred_at=_datetime(row["occurred_at"]),
        recorded_at=_datetime(row["recorded_at"]),
    )


def _record_values(item: AttendanceRecord) -> dict[str, object]:
    return {
        "attendance_record_id": item.attendance_record_id,
        "school_id": item.school_id,
        "student_id": item.student_id,
        "class_id": item.class_id,
        "attendance_date": item.attendance_date,
        "status": item.status.value,
        "first_check_in_at": item.first_check_in_at,
        "last_check_out_at": item.last_check_out_at,
        "source_type": item.source_type.value,
        "review_status": item.review_status.value,
        "retention_until": item.retention_until,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
        "row_version": item.row_version,
    }


def _link_values(item: AttendanceEventLink) -> dict[str, object]:
    return {
        "attendance_event_link_id": item.attendance_event_link_id,
        "attendance_record_id": item.attendance_record_id,
        "normalized_event_id": item.normalized_event_id,
        "link_type": item.link_type.value,
        "decision_confidence": item.decision_confidence,
        "consent_snapshot_status": item.consent_snapshot.value,
        "occurred_at": item.occurred_at,
        "recorded_at": item.recorded_at,
    }


def _correction_values(item: AttendanceCorrection) -> dict[str, object]:
    return {
        "attendance_correction_id": item.attendance_correction_id,
        "attendance_record_id": item.attendance_record_id,
        "from_status": item.from_status.value,
        "to_status": item.to_status.value,
        "from_check_in_at": item.from_check_in_at,
        "to_check_in_at": item.to_check_in_at,
        "reason_code": item.reason_code,
        "actor_id": item.actor_id,
        "approval_status": item.approval_status.value,
        "approver_id": item.approver_id,
        "request_id": item.request_id,
        "occurred_at": item.occurred_at,
        "recorded_at": item.recorded_at,
    }


def _same_event(
    record: AttendanceRecord,
    link: AttendanceEventLink,
    request: AttendanceIngestionRequest,
) -> bool:
    if link.decision_confidence is None or request.decision_confidence is None:
        confidence_matches = link.decision_confidence is request.decision_confidence
    else:
        confidence_matches = hmac.compare_digest(
            format(link.decision_confidence, "f").encode(),
            format(request.decision_confidence, "f").encode(),
        )
    return (
        record.school_id == request.school_id
        and record.student_id == request.student_id
        and record.class_id == request.class_id
        and record.attendance_date == request.attendance_date
        and link.normalized_event_id == request.normalized_event_id
        and link.link_type is request.link_type
        and confidence_matches
        and link.consent_snapshot is request.consent_snapshot
        and link.occurred_at == request.occurred_at
    )


def _existing_event(
    connection: Connection,
    request: AttendanceIngestionRequest,
) -> AttendanceIngestionOutcome | None:
    link_row = (
        connection.execute(
            sa.select(attendance_event_links).where(
                attendance_event_links.c.normalized_event_id == request.normalized_event_id,
                attendance_event_links.c.link_type == request.link_type.value,
            )
        )
        .mappings()
        .one_or_none()
    )
    if link_row is None:
        return None
    link = _event_link(link_row)
    record_row = (
        connection.execute(
            sa.select(attendance_records).where(
                attendance_records.c.attendance_record_id == link.attendance_record_id
            )
        )
        .mappings()
        .one()
    )
    record = _record(record_row)
    if not _same_event(record, link, request):
        raise AttendanceError("ATTENDANCE_DUPLICATE_CONFLICT")
    return AttendanceIngestionOutcome(
        record,
        link,
        duplicate=True,
        blocked=link.consent_snapshot is ConsentSnapshot.BLOCKED,
    )


def _new_record(request: AttendanceIngestionRequest) -> AttendanceRecord:
    if request.consent_snapshot is ConsentSnapshot.BLOCKED or request.link_type in {
        LinkType.SUPPORTING,
        LinkType.REJECTED,
    }:
        raise AttendanceError("ATTENDANCE_CONSENT_BLOCKED")
    return AttendanceRecord(
        attendance_record_id=request.attendance_record_id,
        school_id=request.school_id,
        student_id=request.student_id,
        class_id=request.class_id,
        attendance_date=request.attendance_date,
        status=(
            AttendanceStatus.PENDING_REVIEW if request.requires_review else AttendanceStatus.PRESENT
        ),
        first_check_in_at=(request.occurred_at if request.link_type is LinkType.CHECK_IN else None),
        last_check_out_at=(
            request.occurred_at if request.link_type is LinkType.CHECK_OUT else None
        ),
        source_type=SourceType.AI,
        review_status=ReviewStatus.PENDING
        if request.requires_review
        else ReviewStatus.NOT_REQUIRED,
        retention_until=request.retention_until,
        created_at=request.recorded_at,
        updated_at=request.recorded_at,
        row_version=1,
    )


def _merge_event(record: AttendanceRecord, request: AttendanceIngestionRequest) -> AttendanceRecord:
    if record.class_id != request.class_id:
        raise AttendanceError("ATTENDANCE_DUPLICATE_CONFLICT")
    first_check_in = record.first_check_in_at
    last_check_out = record.last_check_out_at
    if request.link_type is LinkType.CHECK_IN:
        first_check_in = (
            request.occurred_at
            if first_check_in is None
            else min(first_check_in, request.occurred_at)
        )
    elif request.link_type is LinkType.CHECK_OUT:
        last_check_out = (
            request.occurred_at
            if last_check_out is None
            else max(last_check_out, request.occurred_at)
        )
    if (
        first_check_in is not None
        and last_check_out is not None
        and last_check_out < first_check_in
    ):
        raise AttendanceError("ATTENDANCE_INPUT_INVALID")
    status = AttendanceStatus.PENDING_REVIEW if request.requires_review else record.status
    review_status = ReviewStatus.PENDING if request.requires_review else record.review_status
    candidate = AttendanceRecord(
        attendance_record_id=record.attendance_record_id,
        school_id=record.school_id,
        student_id=record.student_id,
        class_id=record.class_id,
        attendance_date=record.attendance_date,
        status=status,
        first_check_in_at=first_check_in,
        last_check_out_at=last_check_out,
        source_type=record.source_type,
        review_status=review_status,
        retention_until=max(record.retention_until, request.retention_until),
        created_at=record.created_at,
        updated_at=request.recorded_at,
        row_version=record.row_version + 1,
    )
    comparable = (
        "status",
        "first_check_in_at",
        "last_check_out_at",
        "review_status",
        "retention_until",
    )
    if all(getattr(candidate, field) == getattr(record, field) for field in comparable):
        return record
    return candidate


class SqlAlchemyAttendanceRepository:
    """Own only the attendance schema; all external identifiers stay logical."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def ingest_event(self, request: AttendanceIngestionRequest) -> AttendanceIngestionOutcome:
        try:
            with self._engine.begin() as connection:
                connection.execute(
                    sa.text("SELECT pg_advisory_xact_lock(hashtextextended(:identity, 0))"),
                    {"identity": f"{request.normalized_event_id}:{request.link_type.value}"},
                )
                existing_event = _existing_event(connection, request)
                if existing_event is not None:
                    return existing_event
                connection.execute(
                    sa.text("SELECT pg_advisory_xact_lock(hashtextextended(:daily, 1))"),
                    {
                        "daily": (
                            f"{request.school_id}:{request.student_id}:"
                            f"{request.attendance_date.isoformat()}"
                        )
                    },
                )
                row = (
                    connection.execute(
                        sa.select(attendance_records)
                        .where(
                            attendance_records.c.school_id == request.school_id,
                            attendance_records.c.student_id == request.student_id,
                            attendance_records.c.attendance_date == request.attendance_date,
                        )
                        .with_for_update()
                    )
                    .mappings()
                    .one_or_none()
                )
                if request.link_type is LinkType.REJECTED:
                    if row is None:
                        return AttendanceIngestionOutcome(
                            None,
                            None,
                            duplicate=False,
                            blocked=request.consent_snapshot is ConsentSnapshot.BLOCKED,
                        )
                    record = _record(row)
                    link = AttendanceEventLink(
                        attendance_event_link_id=request.attendance_event_link_id,
                        attendance_record_id=record.attendance_record_id,
                        normalized_event_id=request.normalized_event_id,
                        link_type=LinkType.REJECTED,
                        decision_confidence=request.decision_confidence,
                        consent_snapshot=request.consent_snapshot,
                        occurred_at=request.occurred_at,
                        recorded_at=request.recorded_at,
                    )
                    connection.execute(
                        sa.insert(attendance_event_links).values(**_link_values(link))
                    )
                    return AttendanceIngestionOutcome(
                        record,
                        link,
                        duplicate=False,
                        blocked=request.consent_snapshot is ConsentSnapshot.BLOCKED,
                    )
                if row is None and request.link_type is LinkType.SUPPORTING:
                    raise AttendanceError("ATTENDANCE_NOT_FOUND")
                if row is None:
                    record = _new_record(request)
                    connection.execute(
                        sa.insert(attendance_records).values(**_record_values(record))
                    )
                else:
                    current = _record(row)
                    record = _merge_event(current, request)
                    if record.row_version != current.row_version:
                        result = connection.execute(
                            sa.update(attendance_records)
                            .where(
                                attendance_records.c.attendance_record_id
                                == current.attendance_record_id,
                                attendance_records.c.row_version == current.row_version,
                            )
                            .values(**_record_values(record))
                        )
                        if result.rowcount != 1:
                            raise AttendanceError("ATTENDANCE_VERSION_CONFLICT")
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
                connection.execute(sa.insert(attendance_event_links).values(**_link_values(link)))
                return AttendanceIngestionOutcome(record, link, duplicate=False, blocked=False)
        except AttendanceError:
            raise
        except IntegrityError:
            raise AttendanceError("ATTENDANCE_DUPLICATE_CONFLICT") from None
        except SQLAlchemyError:
            raise AttendanceError("ATTENDANCE_UNAVAILABLE") from None

    def get_record(self, record_id: UUID, school_id: UUID) -> AttendanceRecord | None:
        try:
            with self._engine.connect() as connection:
                row = (
                    connection.execute(
                        sa.select(attendance_records).where(
                            attendance_records.c.attendance_record_id == record_id,
                            attendance_records.c.school_id == school_id,
                        )
                    )
                    .mappings()
                    .one_or_none()
                )
            return None if row is None else _record(row)
        except AttendanceError:
            raise
        except SQLAlchemyError:
            raise AttendanceError("ATTENDANCE_UNAVAILABLE") from None

    def correct_record(
        self,
        request: AttendanceCorrectionRequest,
        context: TrustedAttendanceContext,
    ) -> AttendanceCorrectionOutcome:
        try:
            with self._engine.begin() as connection:
                row = (
                    connection.execute(
                        sa.select(attendance_records)
                        .where(
                            attendance_records.c.attendance_record_id
                            == request.attendance_record_id,
                            attendance_records.c.school_id == context.school_id,
                        )
                        .with_for_update()
                    )
                    .mappings()
                    .one_or_none()
                )
                if row is None:
                    raise AttendanceError("ATTENDANCE_NOT_FOUND")
                current = _record(row)
                authorize_record(current, context, operation="correct")
                if current.row_version != request.expected_version:
                    raise AttendanceError("ATTENDANCE_VERSION_CONFLICT")
                updated = apply_correction(current, request)
                correction = AttendanceCorrection(
                    attendance_correction_id=request.attendance_correction_id,
                    attendance_record_id=current.attendance_record_id,
                    from_status=current.status,
                    to_status=request.to_status,
                    from_check_in_at=current.first_check_in_at,
                    to_check_in_at=request.to_check_in_at,
                    reason_code=request.reason_code,
                    actor_id=context.actor_id,
                    approval_status=request.approval_status,
                    approver_id=request.approver_id,
                    request_id=request.request_id,
                    occurred_at=request.changed_at,
                    recorded_at=request.changed_at,
                )
                if updated.row_version != current.row_version:
                    result = connection.execute(
                        sa.update(attendance_records)
                        .where(
                            attendance_records.c.attendance_record_id
                            == current.attendance_record_id,
                            attendance_records.c.row_version == request.expected_version,
                        )
                        .values(**_record_values(updated))
                    )
                    if result.rowcount != 1:
                        raise AttendanceError("ATTENDANCE_VERSION_CONFLICT")
                connection.execute(
                    sa.insert(attendance_corrections).values(**_correction_values(correction))
                )
                intent = AttendanceAuditIntent(
                    source_event_id=correction.attendance_correction_id,
                    school_id=context.school_id,
                    actor_id=context.actor_id,
                    action="ATTENDANCE_CORRECTED",
                    resource_id=current.attendance_record_id,
                    request_id=request.request_id,
                    result="success",
                    state_before=current.status.value,
                    state_after=updated.status.value,
                    created_at=request.changed_at,
                )
                return AttendanceCorrectionOutcome(updated, correction, intent)
        except AttendanceError:
            raise
        except IntegrityError:
            raise AttendanceError("ATTENDANCE_DUPLICATE_CONFLICT") from None
        except SQLAlchemyError:
            raise AttendanceError("ATTENDANCE_UNAVAILABLE") from None
