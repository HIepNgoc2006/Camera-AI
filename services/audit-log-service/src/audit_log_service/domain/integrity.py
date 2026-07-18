"""Canonicalization and injected integrity-signing boundary."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Protocol

from audit_log_service.domain.models import AuditEvent, StoredAuditEvent


class IntegritySigner(Protocol):
    """A keyed signer whose key material remains outside the audit domain and database."""

    def sign(self, message: bytes) -> bytes:
        """Return a 32-byte keyed integrity value."""


def _timestamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def semantic_payload(event: AuditEvent) -> dict[str, object]:
    """Return the exact trusted publisher content used for duplicate equivalence."""

    return {
        "event_schema_version": event.event_schema_version,
        "source_service": event.source_service,
        "source_event_id": str(event.source_event_id),
        "correlation_id": event.correlation_id,
        "actor_type": event.actor_type.value,
        "actor_id": str(event.actor_id) if event.actor_id is not None else None,
        "actor_role": event.actor_role,
        "school_id": str(event.school_id) if event.school_id is not None else None,
        "action": event.action,
        "purpose_code": event.purpose_code,
        "resource_type": event.resource_type,
        "resource_id": str(event.resource_id) if event.resource_id is not None else None,
        "resource_ref": event.resource_ref,
        "request_id": event.request_id,
        "result": event.result.value,
        "reason_code": event.reason_code,
        "ip_prefix": str(event.ip_prefix) if event.ip_prefix is not None else None,
        "user_agent_family": event.user_agent_family,
        "changes": event.changes.as_dict(),
        "occurred_at": _timestamp(event.occurred_at),
        "retention_until": _timestamp(event.retention_until),
    }


def canonical_json_bytes(value: dict[str, object]) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


def semantic_bytes(event: AuditEvent) -> bytes:
    return canonical_json_bytes(semantic_payload(event))


def integrity_bytes(event: StoredAuditEvent) -> bytes:
    payload = semantic_payload(event.event)
    payload.update(
        {
            "audit_event_id": str(event.audit_event_id),
            "recorded_at": _timestamp(event.recorded_at),
            "integrity_partition": event.integrity_partition,
            "hash_version": event.hash_version,
        }
    )
    return canonical_json_bytes(payload)


def signing_message(event: StoredAuditEvent) -> bytes:
    previous = event.previous_event_hash or bytes(32)
    return b"camera-ai-audit-integrity-v1\0" + previous + b"\0" + integrity_bytes(event)


def partition_for(recorded_at: datetime) -> str:
    utc = recorded_at.astimezone(UTC)
    return f"{utc:%Y-%m-%d}:00"
