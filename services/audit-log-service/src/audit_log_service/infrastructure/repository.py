"""Serialized PostgreSQL append and integrity verification adapter."""

from __future__ import annotations

import hmac
import re
from datetime import UTC, datetime, timedelta
from ipaddress import ip_network
from typing import cast
from uuid import UUID

import sqlalchemy as sa
from pydantic import ValidationError
from sqlalchemy import Engine
from sqlalchemy.engine import RowMapping
from sqlalchemy.exc import SQLAlchemyError

from audit_log_service.domain.errors import AuditError
from audit_log_service.domain.integrity import (
    IntegritySigner,
    partition_for,
    semantic_bytes,
    signing_message,
)
from audit_log_service.domain.models import (
    ActorType,
    AppendOutcome,
    AuditChanges,
    AuditEvent,
    AuditResult,
    StoredAuditEvent,
)
from audit_log_service.infrastructure.tables import audit_events
from audit_log_service.schemas.events import AuditChangesV1

PARTITION_PATTERN = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}:[0-9]{2}$")


def _uuid(value: object) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))


def _optional_uuid(value: object) -> UUID | None:
    return None if value is None else _uuid(value)


def _datetime(value: object) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise AuditError("AUDIT_INTEGRITY_FAILED")
    return value


def _changes(value: object) -> AuditChanges:
    if value == {}:
        return AuditChanges()
    try:
        return AuditChangesV1.model_validate(value).to_domain()
    except ValidationError:
        raise AuditError("AUDIT_INTEGRITY_FAILED") from None


def _optional_text(value: object) -> str | None:
    return None if value is None else str(value)


def _row_to_stored(row: RowMapping) -> StoredAuditEvent:
    try:
        prefix_value = row["ip_prefix"]
        prefix = None if prefix_value is None else ip_network(str(prefix_value), strict=False)
        event = AuditEvent(
            event_schema_version=int(cast(int, row["event_schema_version"])),
            source_service=str(row["source_service"]),
            source_event_id=_uuid(row["source_event_id"]),
            correlation_id=_optional_text(row["correlation_id"]),
            actor_type=ActorType(str(row["actor_type"])),
            actor_id=_optional_uuid(row["actor_id"]),
            actor_role=_optional_text(row["actor_role"]),
            school_id=_optional_uuid(row["school_id"]),
            action=str(row["action"]),
            purpose_code=_optional_text(row["purpose_code"]),
            resource_type=str(row["resource_type"]),
            resource_id=_optional_uuid(row["resource_id"]),
            resource_ref=_optional_text(row["resource_ref"]),
            request_id=str(row["request_id"]),
            result=AuditResult(str(row["result"])),
            reason_code=_optional_text(row["reason_code"]),
            ip_prefix=prefix,
            user_agent_family=_optional_text(row["user_agent_family"]),
            changes=_changes(row["changes"]),
            occurred_at=_datetime(row["occurred_at"]),
            retention_until=_datetime(row["retention_until"]),
        )
        previous = row["previous_event_hash"]
        event_hash = row["event_hash"]
        return StoredAuditEvent(
            event=event,
            audit_event_id=_uuid(row["audit_event_id"]),
            recorded_at=_datetime(row["recorded_at"]),
            integrity_partition=str(row["integrity_partition"]),
            hash_version=int(cast(int, row["hash_version"])),
            previous_event_hash=None if previous is None else bytes(previous),
            event_hash=bytes(event_hash),
        )
    except (KeyError, TypeError, ValueError):
        raise AuditError("AUDIT_INTEGRITY_FAILED") from None


def _safe_sign(signer: IntegritySigner, event: StoredAuditEvent) -> bytes:
    try:
        digest = signer.sign(signing_message(event))
    except AuditError:
        raise
    except Exception:
        raise AuditError("AUDIT_UNAVAILABLE") from None
    if len(digest) != 32:
        raise AuditError("AUDIT_INTEGRITY_FAILED")
    return digest


def _values(event: StoredAuditEvent) -> dict[str, object]:
    item = event.event
    return {
        "audit_event_id": event.audit_event_id,
        "occurred_at": item.occurred_at,
        "recorded_at": event.recorded_at,
        "school_id": item.school_id,
        "event_schema_version": item.event_schema_version,
        "source_service": item.source_service,
        "source_event_id": str(item.source_event_id),
        "correlation_id": item.correlation_id,
        "actor_type": item.actor_type.value,
        "actor_id": item.actor_id,
        "actor_role": item.actor_role,
        "action": item.action,
        "purpose_code": item.purpose_code,
        "resource_type": item.resource_type,
        "resource_id": item.resource_id,
        "resource_ref": item.resource_ref,
        "request_id": item.request_id,
        "result": item.result.value,
        "reason_code": item.reason_code,
        "ip_prefix": str(item.ip_prefix) if item.ip_prefix is not None else None,
        "user_agent_family": item.user_agent_family,
        "changes": item.changes.as_dict(),
        "integrity_partition": event.integrity_partition,
        "hash_version": event.hash_version,
        "previous_event_hash": event.previous_event_hash,
        "event_hash": event.event_hash,
        "retention_until": item.retention_until,
    }


class SqlAlchemyAuditRepository:
    """Own the audit schema and serialize publisher identities and integrity partitions."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def append(
        self,
        event: AuditEvent,
        *,
        recorded_at: datetime,
        audit_event_id: UUID,
        signer: IntegritySigner,
    ) -> AppendOutcome:
        requested_time = recorded_at.astimezone(UTC)
        partition = partition_for(requested_time)
        try:
            with self._engine.begin() as connection:
                connection.execute(
                    sa.text("SELECT pg_advisory_xact_lock(hashtextextended(:identity, 1))"),
                    {"identity": f"{event.source_service}:{event.source_event_id}"},
                )
                connection.execute(
                    sa.text("SELECT pg_advisory_xact_lock(hashtextextended(:partition, 0))"),
                    {"partition": partition},
                )
                existing_row = (
                    connection.execute(
                        sa.select(audit_events).where(
                            audit_events.c.source_service == event.source_service,
                            audit_events.c.source_event_id == str(event.source_event_id),
                        )
                    )
                    .mappings()
                    .one_or_none()
                )
                if existing_row is not None:
                    existing = _row_to_stored(existing_row)
                    if not hmac.compare_digest(
                        semantic_bytes(existing.event), semantic_bytes(event)
                    ):
                        raise AuditError("AUDIT_DUPLICATE_CONFLICT")
                    return AppendOutcome(event=existing, duplicate=True)

                previous_row = (
                    connection.execute(
                        sa.select(audit_events.c.recorded_at, audit_events.c.event_hash)
                        .where(audit_events.c.integrity_partition == partition)
                        .order_by(
                            audit_events.c.recorded_at.desc(),
                            audit_events.c.audit_event_id.desc(),
                        )
                        .limit(1)
                    )
                    .mappings()
                    .one_or_none()
                )
                previous_hash: bytes | None = None
                if previous_row is not None:
                    previous_time = _datetime(previous_row["recorded_at"])
                    if requested_time <= previous_time:
                        requested_time = previous_time + timedelta(microseconds=1)
                    previous_hash = bytes(previous_row["event_hash"])
                if partition_for(requested_time) != partition:
                    raise AuditError("AUDIT_UNAVAILABLE")

                unsigned = StoredAuditEvent(
                    event=event,
                    audit_event_id=audit_event_id,
                    recorded_at=requested_time,
                    integrity_partition=partition,
                    hash_version=1,
                    previous_event_hash=previous_hash,
                    event_hash=bytes(32),
                )
                digest = _safe_sign(signer, unsigned)
                stored = StoredAuditEvent(
                    event=event,
                    audit_event_id=audit_event_id,
                    recorded_at=requested_time,
                    integrity_partition=partition,
                    hash_version=1,
                    previous_event_hash=previous_hash,
                    event_hash=digest,
                )
                connection.execute(sa.insert(audit_events).values(**_values(stored)))
                return AppendOutcome(event=stored, duplicate=False)
        except AuditError:
            raise
        except SQLAlchemyError:
            raise AuditError("AUDIT_UNAVAILABLE") from None

    def verify_partition(self, partition: str, signer: IntegritySigner) -> None:
        if PARTITION_PATTERN.fullmatch(partition) is None:
            raise AuditError("AUDIT_EVENT_INVALID")
        try:
            with self._engine.connect() as connection:
                rows = connection.execute(
                    sa.select(audit_events)
                    .where(audit_events.c.integrity_partition == partition)
                    .order_by(audit_events.c.recorded_at, audit_events.c.audit_event_id)
                ).mappings()
                expected_previous: bytes | None = None
                for row in rows:
                    stored = _row_to_stored(row)
                    if stored.previous_event_hash != expected_previous:
                        raise AuditError("AUDIT_INTEGRITY_FAILED")
                    expected_hash = _safe_sign(signer, stored)
                    if not hmac.compare_digest(stored.event_hash, expected_hash):
                        raise AuditError("AUDIT_INTEGRITY_FAILED")
                    expected_previous = stored.event_hash
        except AuditError:
            raise
        except SQLAlchemyError:
            raise AuditError("AUDIT_UNAVAILABLE") from None
