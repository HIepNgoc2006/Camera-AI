"""Postgres transport outbox for audit intents (Issue #138).

Enqueue is idempotent on `(source_service, source_event_id)` so a retried caller can never
create duplicate evidence downstream. Claiming and failure handling mirror the event outbox:
skip-locked batch leases, the `normalized_outbox_v1` bounded retry policy, and terminal
`failed` rows for operator triage.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID, uuid4

import sqlalchemy as sa
from camera_ai_audit import AuditIntent
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from ansvis_adapter.domain.errors import AnsvisAdapterError
from ansvis_adapter.infrastructure.tables import audit_outbox

_CLAIM_SECONDS = 30
_MAX_ATTEMPTS = 5


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise AnsvisAdapterError("TIME_SOURCE_UNHEALTHY")
    return value.astimezone(UTC)


def _system_utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True, kw_only=True)
class PendingAuditIntent:
    """One leased intent row ready for trusted-context delivery."""

    audit_outbox_id: UUID
    claim_token: UUID
    source_service: str
    source_event_id: UUID
    school_id: UUID | None
    payload: Mapping[str, object]
    attempt_count: int
    recorded_at: datetime


class PostgresAuditOutbox:
    """Owns every read/write of `events.audit_outbox`; fail closed on storage errors."""

    def __init__(self, engine: Engine, *, now: Callable[[], datetime] = _system_utc_now) -> None:
        self._engine = engine
        self._now = now

    def record(self, intent: AuditIntent) -> None:
        """Durably enqueue one intent; replaying the same intent is a no-op."""

        current = _utc(self._now())
        statement = (
            pg_insert(audit_outbox)
            .values(
                audit_outbox_id=uuid4(),
                source_service=intent.source_service,
                source_event_id=intent.source_event_id,
                school_id=intent.school_id,
                payload=intent.publisher_payload(),
                publish_status="pending",
                attempt_count=0,
                next_attempt_at=current,
                recorded_at=current,
            )
            .on_conflict_do_nothing(constraint="uq_events_audit_outbox_source")
        )
        try:
            with self._engine.begin() as connection:
                connection.execute(statement)
        except SQLAlchemyError:
            raise AnsvisAdapterError("AUDIT_OUTBOX_UNAVAILABLE") from None

    def claim_batch(self, *, now: datetime, limit: int) -> tuple[PendingAuditIntent, ...]:
        if not 1 <= limit <= 50:
            raise ValueError("audit claim batch size must stay within 1..50")
        current = _utc(now)
        token = uuid4()
        try:
            with self._engine.begin() as connection:
                rows = (
                    connection.execute(
                        sa.select(audit_outbox)
                        .where(
                            audit_outbox.c.publish_status == "pending",
                            audit_outbox.c.next_attempt_at <= current,
                            sa.or_(
                                audit_outbox.c.claim_token.is_(None),
                                audit_outbox.c.claim_expires_at <= current,
                            ),
                        )
                        .order_by(audit_outbox.c.recorded_at, audit_outbox.c.audit_outbox_id)
                        .with_for_update(skip_locked=True)
                        .limit(limit)
                    )
                    .mappings()
                    .all()
                )
                if not rows:
                    return ()
                identifiers = [cast(UUID, row["audit_outbox_id"]) for row in rows]
                claimed = connection.execute(
                    sa.update(audit_outbox)
                    .where(audit_outbox.c.audit_outbox_id.in_(identifiers))
                    .values(
                        claim_token=token,
                        claim_expires_at=current + timedelta(seconds=_CLAIM_SECONDS),
                    )
                )
                if claimed.rowcount != len(identifiers):
                    raise AnsvisAdapterError("AUDIT_OUTBOX_UNAVAILABLE")
                return tuple(
                    PendingAuditIntent(
                        audit_outbox_id=cast(UUID, row["audit_outbox_id"]),
                        claim_token=token,
                        source_service=str(row["source_service"]),
                        source_event_id=cast(UUID, row["source_event_id"]),
                        school_id=cast(UUID | None, row["school_id"]),
                        payload=cast(Mapping[str, object], row["payload"]),
                        attempt_count=int(row["attempt_count"]),
                        recorded_at=_utc(cast(datetime, row["recorded_at"])),
                    )
                    for row in rows
                )
        except AnsvisAdapterError:
            raise
        except SQLAlchemyError:
            raise AnsvisAdapterError("AUDIT_OUTBOX_UNAVAILABLE") from None

    def mark_delivered_batch(
        self,
        confirmations: Sequence[tuple[UUID, UUID]],
        *,
        delivered_at: datetime,
    ) -> None:
        if not confirmations:
            return
        current = _utc(delivered_at)
        pairs = [
            sa.tuple_(sa.literal(intent_id), sa.literal(claim_token))
            for intent_id, claim_token in confirmations
        ]
        try:
            with self._engine.begin() as connection:
                result = connection.execute(
                    sa.update(audit_outbox)
                    .where(
                        sa.tuple_(
                            audit_outbox.c.audit_outbox_id,
                            audit_outbox.c.claim_token,
                        ).in_(pairs),
                        audit_outbox.c.publish_status == "pending",
                    )
                    .values(
                        publish_status="delivered",
                        delivered_at=current,
                        claim_token=None,
                        claim_expires_at=None,
                        last_error_code=None,
                    )
                )
                if result.rowcount != len(confirmations):
                    raise AnsvisAdapterError("AUDIT_OUTBOX_UNAVAILABLE")
        except AnsvisAdapterError:
            raise
        except SQLAlchemyError:
            raise AnsvisAdapterError("AUDIT_OUTBOX_UNAVAILABLE") from None

    def record_failure(
        self,
        intent: PendingAuditIntent,
        *,
        failed_at: datetime,
        next_retry_at: datetime | None,
        error_code: str,
    ) -> bool:
        current = _utc(failed_at)
        next_attempt = intent.attempt_count + 1
        dead_lettered = next_retry_at is None
        if dead_lettered != (next_attempt >= _MAX_ATTEMPTS):
            raise AnsvisAdapterError("AUDIT_OUTBOX_UNAVAILABLE")
        retry_at = current if next_retry_at is None else _utc(next_retry_at)
        try:
            with self._engine.begin() as connection:
                result = connection.execute(
                    sa.update(audit_outbox)
                    .where(
                        audit_outbox.c.audit_outbox_id == intent.audit_outbox_id,
                        audit_outbox.c.claim_token == intent.claim_token,
                        audit_outbox.c.publish_status == "pending",
                    )
                    .values(
                        publish_status="failed" if dead_lettered else "pending",
                        attempt_count=next_attempt,
                        next_attempt_at=retry_at,
                        claim_token=None,
                        claim_expires_at=None,
                        last_error_code=error_code,
                    )
                )
                if result.rowcount != 1:
                    raise AnsvisAdapterError("AUDIT_OUTBOX_UNAVAILABLE")
        except AnsvisAdapterError:
            raise
        except SQLAlchemyError:
            raise AnsvisAdapterError("AUDIT_OUTBOX_UNAVAILABLE") from None
        return dead_lettered

    def oldest_pending_seconds(self, *, now: datetime) -> int:
        """Age of the oldest undelivered intent, bounded for gauge use."""

        current = _utc(now)
        try:
            with self._engine.connect() as connection:
                oldest = connection.execute(
                    sa.select(sa.func.min(audit_outbox.c.recorded_at)).where(
                        audit_outbox.c.publish_status == "pending"
                    )
                ).scalar_one_or_none()
        except SQLAlchemyError:
            raise AnsvisAdapterError("AUDIT_OUTBOX_UNAVAILABLE") from None
        if oldest is None:
            return 0
        return max(0, int((current - _utc(oldest)).total_seconds()))


def school_for_event(engine: Engine, normalized_event_id: UUID) -> UUID:
    """Resolve the school scope of one normalized event for audit binding."""

    from ansvis_adapter.infrastructure.tables import normalized_events

    try:
        with engine.connect() as connection:
            school_id = connection.execute(
                sa.select(normalized_events.c.school_id).where(
                    normalized_events.c.normalized_event_id == normalized_event_id
                )
            ).scalar_one_or_none()
    except SQLAlchemyError:
        raise AnsvisAdapterError("AUDIT_OUTBOX_UNAVAILABLE") from None
    if school_id is None:
        raise AnsvisAdapterError("AUDIT_OUTBOX_UNAVAILABLE")
    return cast(UUID, school_id)
