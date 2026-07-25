"""Transactional PostgreSQL repository for the Timekeeping Service-owned schema."""

from __future__ import annotations

import hmac
from datetime import date, datetime, time
from decimal import Decimal
from typing import cast
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.engine import Connection, Engine, RowMapping
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from timekeeping_service.domain.errors import TimekeepingError
from timekeeping_service.domain.models import (
    ConsentSnapshot,
    LinkType,
    ReviewStatus,
    Shift,
    ShiftStatus,
    SourceType,
    TimekeepingAuditIntent,
    TimekeepingCorrection,
    TimekeepingCorrectionOutcome,
    TimekeepingCorrectionRequest,
    TimekeepingEventLink,
    TimekeepingIngestionOutcome,
    TimekeepingIngestionRequest,
    TimekeepingRecord,
    TimekeepingStatus,
    TrustedTimekeepingContext,
    apply_correction,
)
from timekeeping_service.domain.policies import authorize_record
from timekeeping_service.infrastructure.tables import (
    shifts,
    staff_shift_assignments,
    timekeeping_corrections,
    timekeeping_event_links,
    timekeeping_records,
)


def _uuid(value: object) -> UUID:
    return cast(UUID, value)


def _datetime(value: object) -> datetime:
    return cast(datetime, value)


def _date(value: object) -> date:
    return cast(date, value)


def _time(value: object) -> time:
    return cast(time, value)


def _shift(row: RowMapping) -> Shift:
    return Shift(
        shift_id=_uuid(row["shift_id"]),
        school_id=_uuid(row["school_id"]),
        code=str(row["code"]),
        name=str(row["name"]),
        timezone=str(row["timezone"]),
        start_local_time=_time(row["start_local_time"]),
        end_local_time=_time(row["end_local_time"]),
        overnight=bool(row["overnight"]),
        check_in_grace_minutes=int(row["check_in_grace_minutes"]),
        check_out_grace_minutes=int(row["check_out_grace_minutes"]),
        status=ShiftStatus(str(row["status"])),
        version=int(row["version"]),
        valid_from=_datetime(row["valid_from"]),
        valid_to=cast(datetime | None, row["valid_to"]),
        created_at=_datetime(row["created_at"]),
    )


def _record(row: RowMapping) -> TimekeepingRecord:
    return TimekeepingRecord(
        timekeeping_record_id=_uuid(row["timekeeping_record_id"]),
        school_id=_uuid(row["school_id"]),
        staff_id=_uuid(row["staff_id"]),
        shift_id=_uuid(row["shift_id"]),
        work_date=_date(row["work_date"]),
        check_in_at=cast(datetime | None, row["check_in_at"]),
        check_out_at=cast(datetime | None, row["check_out_at"]),
        status=TimekeepingStatus(str(row["status"])),
        source_type=SourceType(str(row["source_type"])),
        review_status=ReviewStatus(str(row["review_status"])),
        retention_until=_datetime(row["retention_until"]),
        created_at=_datetime(row["created_at"]),
        updated_at=_datetime(row["updated_at"]),
        row_version=int(row["row_version"]),
    )


def _event_link(row: RowMapping) -> TimekeepingEventLink:
    return TimekeepingEventLink(
        timekeeping_event_link_id=_uuid(row["timekeeping_event_link_id"]),
        timekeeping_record_id=_uuid(row["timekeeping_record_id"]),
        normalized_event_id=_uuid(row["normalized_event_id"]),
        link_type=LinkType(str(row["link_type"])),
        decision_confidence=(
            None if row["decision_confidence"] is None else Decimal(str(row["decision_confidence"]))
        ),
        consent_snapshot=ConsentSnapshot(str(row["consent_snapshot_status"])),
        occurred_at=_datetime(row["occurred_at"]),
        recorded_at=_datetime(row["recorded_at"]),
    )


def _record_values(item: TimekeepingRecord) -> dict[str, object]:
    return {
        "timekeeping_record_id": item.timekeeping_record_id,
        "school_id": item.school_id,
        "staff_id": item.staff_id,
        "shift_id": item.shift_id,
        "work_date": item.work_date,
        "check_in_at": item.check_in_at,
        "check_out_at": item.check_out_at,
        "status": item.status.value,
        "source_type": item.source_type.value,
        "review_status": item.review_status.value,
        "retention_until": item.retention_until,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
        "row_version": item.row_version,
    }


def _link_values(item: TimekeepingEventLink) -> dict[str, object]:
    return {
        "timekeeping_event_link_id": item.timekeeping_event_link_id,
        "timekeeping_record_id": item.timekeeping_record_id,
        "normalized_event_id": item.normalized_event_id,
        "link_type": item.link_type.value,
        "decision_confidence": item.decision_confidence,
        "consent_snapshot_status": item.consent_snapshot.value,
        "occurred_at": item.occurred_at,
        "recorded_at": item.recorded_at,
    }


def _correction_values(item: TimekeepingCorrection) -> dict[str, object]:
    return {
        "timekeeping_correction_id": item.timekeeping_correction_id,
        "timekeeping_record_id": item.timekeeping_record_id,
        "from_status": item.from_status.value,
        "to_status": item.to_status.value,
        "from_check_in_at": item.from_check_in_at,
        "to_check_in_at": item.to_check_in_at,
        "from_check_out_at": item.from_check_out_at,
        "to_check_out_at": item.to_check_out_at,
        "reason_code": item.reason_code,
        "actor_id": item.actor_id,
        "approval_status": item.approval_status.value,
        "approver_id": item.approver_id,
        "request_id": item.request_id,
        "occurred_at": item.occurred_at,
        "recorded_at": item.recorded_at,
    }


def _same_event(
    record: TimekeepingRecord,
    link: TimekeepingEventLink,
    request: TimekeepingIngestionRequest,
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
        and record.staff_id == request.staff_id
        and record.shift_id == request.shift_id
        and record.work_date == request.work_date
        and link.normalized_event_id == request.normalized_event_id
        and link.link_type is request.link_type
        and confidence_matches
        and link.consent_snapshot is request.consent_snapshot
        and link.occurred_at == request.occurred_at
    )


def _existing_event(
    connection: Connection,
    request: TimekeepingIngestionRequest,
) -> TimekeepingIngestionOutcome | None:
    link_row = (
        connection.execute(
            sa.select(timekeeping_event_links).where(
                timekeeping_event_links.c.normalized_event_id == request.normalized_event_id,
                timekeeping_event_links.c.link_type == request.link_type.value,
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
            sa.select(timekeeping_records).where(
                timekeeping_records.c.timekeeping_record_id == link.timekeeping_record_id
            )
        )
        .mappings()
        .one()
    )
    record = _record(record_row)
    if not _same_event(record, link, request):
        raise TimekeepingError("TIMEKEEPING_DUPLICATE_CONFLICT")
    return TimekeepingIngestionOutcome(
        record,
        link,
        duplicate=True,
        blocked=link.consent_snapshot is ConsentSnapshot.BLOCKED,
    )


def _new_record(request: TimekeepingIngestionRequest) -> TimekeepingRecord:
    if request.consent_snapshot is ConsentSnapshot.BLOCKED or request.link_type in {
        LinkType.SUPPORTING,
        LinkType.REJECTED,
    }:
        raise TimekeepingError("TIMEKEEPING_CONSENT_BLOCKED")
    missing_pair = request.link_type is LinkType.CHECK_OUT
    status = TimekeepingStatus.REVIEW if missing_pair else request.event_status
    return TimekeepingRecord(
        timekeeping_record_id=request.timekeeping_record_id,
        school_id=request.school_id,
        staff_id=request.staff_id,
        shift_id=request.shift_id,
        work_date=request.work_date,
        check_in_at=(request.occurred_at if request.link_type is LinkType.CHECK_IN else None),
        check_out_at=(request.occurred_at if request.link_type is LinkType.CHECK_OUT else None),
        status=status,
        source_type=SourceType.AI,
        review_status=(
            ReviewStatus.PENDING
            if status is TimekeepingStatus.REVIEW
            else ReviewStatus.NOT_REQUIRED
        ),
        retention_until=request.retention_until,
        created_at=request.recorded_at,
        updated_at=request.recorded_at,
        row_version=1,
    )


def _merged_status(
    record: TimekeepingRecord,
    request: TimekeepingIngestionRequest,
    *,
    invalid_order: bool,
) -> TimekeepingStatus:
    if (
        invalid_order
        or record.status is TimekeepingStatus.REVIEW
        or request.requires_review
        or request.event_status is TimekeepingStatus.REVIEW
        or request.link_type is LinkType.SUPPORTING
    ):
        return TimekeepingStatus.REVIEW
    if request.link_type is LinkType.CHECK_IN:
        if (
            record.status is TimekeepingStatus.EARLY_LEAVE
            and request.event_status is TimekeepingStatus.LATE
        ):
            return TimekeepingStatus.REVIEW
        if record.status is TimekeepingStatus.EARLY_LEAVE:
            return record.status
        return request.event_status
    if request.link_type is LinkType.CHECK_OUT:
        if (
            record.status is TimekeepingStatus.LATE
            and request.event_status is TimekeepingStatus.EARLY_LEAVE
        ):
            return TimekeepingStatus.REVIEW
        if request.event_status is TimekeepingStatus.EARLY_LEAVE:
            return request.event_status
        if record.status is TimekeepingStatus.LATE:
            return record.status
        return TimekeepingStatus.PRESENT
    return TimekeepingStatus.REVIEW


def _merge_event(
    record: TimekeepingRecord,
    request: TimekeepingIngestionRequest,
) -> TimekeepingRecord:
    if record.shift_id != request.shift_id:
        raise TimekeepingError("TIMEKEEPING_DUPLICATE_CONFLICT")
    check_in = record.check_in_at
    check_out = record.check_out_at
    if request.link_type is LinkType.CHECK_IN:
        check_in = request.occurred_at if check_in is None else min(check_in, request.occurred_at)
    elif request.link_type is LinkType.CHECK_OUT:
        check_out = (
            request.occurred_at if check_out is None else max(check_out, request.occurred_at)
        )
    invalid_order = check_in is not None and check_out is not None and check_out < check_in
    if invalid_order:
        check_in = record.check_in_at
        check_out = record.check_out_at
    status = _merged_status(record, request, invalid_order=invalid_order)
    review_status = (
        ReviewStatus.PENDING if status is TimekeepingStatus.REVIEW else record.review_status
    )
    candidate = TimekeepingRecord(
        timekeeping_record_id=record.timekeeping_record_id,
        school_id=record.school_id,
        staff_id=record.staff_id,
        shift_id=record.shift_id,
        work_date=record.work_date,
        check_in_at=check_in,
        check_out_at=check_out,
        status=status,
        source_type=record.source_type,
        review_status=review_status,
        retention_until=max(record.retention_until, request.retention_until),
        created_at=record.created_at,
        updated_at=request.recorded_at,
        row_version=record.row_version + 1,
    )
    comparable = (
        "check_in_at",
        "check_out_at",
        "status",
        "review_status",
        "retention_until",
    )
    if all(getattr(candidate, field) == getattr(record, field) for field in comparable):
        return record
    return candidate


class SqlAlchemyTimekeepingRepository:
    """Own only the timekeeping schema; all external identifiers stay logical."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def get_effective_shift(
        self,
        shift_id: UUID,
        school_id: UUID,
        occurred_at: datetime,
    ) -> Shift | None:
        try:
            with self._engine.connect() as connection:
                row = (
                    connection.execute(
                        sa.select(shifts).where(
                            shifts.c.shift_id == shift_id,
                            shifts.c.school_id == school_id,
                            shifts.c.status.in_(
                                (ShiftStatus.ACTIVE.value, ShiftStatus.RETIRED.value)
                            ),
                            shifts.c.valid_from <= occurred_at,
                            sa.or_(shifts.c.valid_to.is_(None), shifts.c.valid_to > occurred_at),
                        )
                    )
                    .mappings()
                    .one_or_none()
                )
            return None if row is None else _shift(row)
        except TimekeepingError:
            raise
        except SQLAlchemyError:
            raise TimekeepingError("TIMEKEEPING_UNAVAILABLE") from None

    def has_active_assignment(
        self,
        school_id: UUID,
        staff_id: UUID,
        shift_id: UUID,
        work_date: date,
    ) -> bool:
        try:
            with self._engine.connect() as connection:
                assignment_id = connection.scalar(
                    sa.select(staff_shift_assignments.c.staff_shift_assignment_id).where(
                        staff_shift_assignments.c.school_id == school_id,
                        staff_shift_assignments.c.staff_id == staff_id,
                        staff_shift_assignments.c.shift_id == shift_id,
                        staff_shift_assignments.c.status == "active",
                        staff_shift_assignments.c.valid_from <= work_date,
                        sa.or_(
                            staff_shift_assignments.c.valid_to.is_(None),
                            staff_shift_assignments.c.valid_to >= work_date,
                        ),
                    )
                )
            return assignment_id is not None
        except SQLAlchemyError:
            raise TimekeepingError("TIMEKEEPING_UNAVAILABLE") from None

    def ingest_event(
        self,
        request: TimekeepingIngestionRequest,
    ) -> TimekeepingIngestionOutcome:
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
                    sa.text("SELECT pg_advisory_xact_lock(hashtextextended(:record, 1))"),
                    {
                        "record": (
                            f"{request.school_id}:{request.staff_id}:{request.shift_id}:"
                            f"{request.work_date.isoformat()}"
                        )
                    },
                )
                row = (
                    connection.execute(
                        sa.select(timekeeping_records)
                        .where(
                            timekeeping_records.c.school_id == request.school_id,
                            timekeeping_records.c.staff_id == request.staff_id,
                            timekeeping_records.c.shift_id == request.shift_id,
                            timekeeping_records.c.work_date == request.work_date,
                        )
                        .with_for_update()
                    )
                    .mappings()
                    .one_or_none()
                )
                if request.link_type is LinkType.REJECTED:
                    if row is None:
                        return TimekeepingIngestionOutcome(
                            None,
                            None,
                            duplicate=False,
                            blocked=True,
                        )
                    record = _record(row)
                    link = TimekeepingEventLink(
                        timekeeping_event_link_id=request.timekeeping_event_link_id,
                        timekeeping_record_id=record.timekeeping_record_id,
                        normalized_event_id=request.normalized_event_id,
                        link_type=LinkType.REJECTED,
                        decision_confidence=request.decision_confidence,
                        consent_snapshot=ConsentSnapshot.BLOCKED,
                        occurred_at=request.occurred_at,
                        recorded_at=request.recorded_at,
                    )
                    connection.execute(
                        sa.insert(timekeeping_event_links).values(**_link_values(link))
                    )
                    return TimekeepingIngestionOutcome(
                        record,
                        link,
                        duplicate=False,
                        blocked=True,
                    )
                if row is None and request.link_type is LinkType.SUPPORTING:
                    raise TimekeepingError("TIMEKEEPING_NOT_FOUND")
                if row is None:
                    record = _new_record(request)
                    connection.execute(
                        sa.insert(timekeeping_records).values(**_record_values(record))
                    )
                else:
                    current = _record(row)
                    record = _merge_event(current, request)
                    if record.row_version != current.row_version:
                        result = connection.execute(
                            sa.update(timekeeping_records)
                            .where(
                                timekeeping_records.c.timekeeping_record_id
                                == current.timekeeping_record_id,
                                timekeeping_records.c.row_version == current.row_version,
                            )
                            .values(**_record_values(record))
                        )
                        if result.rowcount != 1:
                            raise TimekeepingError("TIMEKEEPING_VERSION_CONFLICT")
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
                connection.execute(sa.insert(timekeeping_event_links).values(**_link_values(link)))
                return TimekeepingIngestionOutcome(
                    record,
                    link,
                    duplicate=False,
                    blocked=False,
                )
        except TimekeepingError:
            raise
        except IntegrityError:
            raise TimekeepingError("TIMEKEEPING_DUPLICATE_CONFLICT") from None
        except SQLAlchemyError:
            raise TimekeepingError("TIMEKEEPING_UNAVAILABLE") from None

    def get_record(
        self,
        record_id: UUID,
        school_id: UUID,
    ) -> TimekeepingRecord | None:
        try:
            with self._engine.connect() as connection:
                row = (
                    connection.execute(
                        sa.select(timekeeping_records).where(
                            timekeeping_records.c.timekeeping_record_id == record_id,
                            timekeeping_records.c.school_id == school_id,
                        )
                    )
                    .mappings()
                    .one_or_none()
                )
            return None if row is None else _record(row)
        except TimekeepingError:
            raise
        except SQLAlchemyError:
            raise TimekeepingError("TIMEKEEPING_UNAVAILABLE") from None

    def correct_record(
        self,
        request: TimekeepingCorrectionRequest,
        context: TrustedTimekeepingContext,
    ) -> TimekeepingCorrectionOutcome:
        try:
            with self._engine.begin() as connection:
                row = (
                    connection.execute(
                        sa.select(timekeeping_records)
                        .where(
                            timekeeping_records.c.timekeeping_record_id
                            == request.timekeeping_record_id,
                            timekeeping_records.c.school_id == context.school_id,
                        )
                        .with_for_update()
                    )
                    .mappings()
                    .one_or_none()
                )
                if row is None:
                    raise TimekeepingError("TIMEKEEPING_NOT_FOUND")
                current = _record(row)
                authorize_record(current, context, operation="correct")
                if current.row_version != request.expected_version:
                    raise TimekeepingError("TIMEKEEPING_VERSION_CONFLICT")
                updated = apply_correction(current, request)
                correction = TimekeepingCorrection(
                    timekeeping_correction_id=request.timekeeping_correction_id,
                    timekeeping_record_id=current.timekeeping_record_id,
                    from_status=current.status,
                    to_status=request.to_status,
                    from_check_in_at=current.check_in_at,
                    to_check_in_at=request.to_check_in_at,
                    from_check_out_at=current.check_out_at,
                    to_check_out_at=request.to_check_out_at,
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
                        sa.update(timekeeping_records)
                        .where(
                            timekeeping_records.c.timekeeping_record_id
                            == current.timekeeping_record_id,
                            timekeeping_records.c.row_version == request.expected_version,
                        )
                        .values(**_record_values(updated))
                    )
                    if result.rowcount != 1:
                        raise TimekeepingError("TIMEKEEPING_VERSION_CONFLICT")
                connection.execute(
                    sa.insert(timekeeping_corrections).values(**_correction_values(correction))
                )
                intent = TimekeepingAuditIntent(
                    source_event_id=correction.timekeeping_correction_id,
                    school_id=context.school_id,
                    actor_id=context.actor_id,
                    action="TIMEKEEPING_CORRECTED",
                    resource_id=current.timekeeping_record_id,
                    request_id=request.request_id,
                    result="success",
                    state_before=current.status.value,
                    state_after=updated.status.value,
                    created_at=request.changed_at,
                )
                return TimekeepingCorrectionOutcome(updated, correction, intent)
        except TimekeepingError:
            raise
        except IntegrityError:
            raise TimekeepingError("TIMEKEEPING_DUPLICATE_CONFLICT") from None
        except SQLAlchemyError:
            raise TimekeepingError("TIMEKEEPING_UNAVAILABLE") from None
