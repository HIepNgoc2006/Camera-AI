"""Pure immutable audit evidence models."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from ipaddress import IPv4Network, IPv6Network
from uuid import UUID

from audit_log_service.domain.errors import AuditError

STABLE_CODE = re.compile(r"^[a-z][a-z0-9_.:-]{0,63}$")
SERVICE_CODE = re.compile(r"^[a-z][a-z0-9-]{1,62}[a-z0-9]$")
UPPER_CODE = re.compile(r"^[A-Z][A-Z0-9_]{1,95}$")
REQUEST_ID = re.compile(r"^req_[A-Za-z0-9_-]{8,120}$")
CORRELATION_ID = re.compile(r"^cor_[A-Za-z0-9_-]{8,120}$")


class ActorType(StrEnum):
    USER = "user"
    SERVICE = "service"
    SYSTEM = "system"


class AuditResult(StrEnum):
    SUCCESS = "success"
    DENIED = "denied"
    FAILED = "failed"


def _aware(value: datetime, field: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise AuditError("AUDIT_EVENT_INVALID")
    if field == "retention_until" and value.year > 9998:
        raise AuditError("AUDIT_EVENT_INVALID")


def _nonzero(value: UUID | None) -> None:
    if value is not None and value.int == 0:
        raise AuditError("AUDIT_EVENT_INVALID")


def _matches(value: str | None, pattern: re.Pattern[str]) -> None:
    if value is not None and pattern.fullmatch(value) is None:
        raise AuditError("AUDIT_EVENT_INVALID")


@dataclass(frozen=True, slots=True)
class AuditChanges:
    """Controlled audit_changes_v1 content represented as immutable pairs."""

    changed_fields: tuple[str, ...] = ()
    state_before_codes: tuple[tuple[str, str | bool], ...] = ()
    state_after_codes: tuple[tuple[str, str | bool], ...] = ()
    reference_ids: tuple[tuple[str, UUID], ...] = ()
    count_summary: tuple[tuple[str, int], ...] = ()
    policy_versions: tuple[tuple[str, str], ...] = ()

    @property
    def is_empty(self) -> bool:
        return not any(
            (
                self.changed_fields,
                self.state_before_codes,
                self.state_after_codes,
                self.reference_ids,
                self.count_summary,
                self.policy_versions,
            )
        )

    def as_dict(self) -> dict[str, object]:
        if self.is_empty:
            return {}
        result: dict[str, object] = {"schema_version": "audit_changes_v1"}
        if self.changed_fields:
            result["changed_fields"] = list(self.changed_fields)
        if self.state_before_codes:
            result["state_before_codes"] = dict(self.state_before_codes)
        if self.state_after_codes:
            result["state_after_codes"] = dict(self.state_after_codes)
        if self.reference_ids:
            result["reference_ids"] = {key: str(value) for key, value in self.reference_ids}
        if self.count_summary:
            result["count_summary"] = dict(self.count_summary)
        if self.policy_versions:
            result["policy_versions"] = dict(self.policy_versions)
        return result


@dataclass(frozen=True, slots=True)
class TrustedAuditContext:
    """Actor, tenant, publisher, and retention values from trusted server context."""

    source_service: str
    actor_type: ActorType
    retention_until: datetime
    school_id: UUID | None = None
    actor_id: UUID | None = None
    actor_role: str | None = None

    def __post_init__(self) -> None:
        _matches(self.source_service, SERVICE_CODE)
        _matches(self.actor_role, STABLE_CODE)
        _nonzero(self.school_id)
        _nonzero(self.actor_id)
        _aware(self.retention_until, "retention_until")
        if self.actor_type is ActorType.USER and self.actor_id is None:
            raise AuditError("AUDIT_EVENT_INVALID")


@dataclass(frozen=True, slots=True)
class AuditEvent:
    """A validated publisher event combined with trusted server context."""

    event_schema_version: int
    source_service: str
    source_event_id: UUID
    action: str
    resource_type: str
    request_id: str
    result: AuditResult
    occurred_at: datetime
    retention_until: datetime
    actor_type: ActorType
    changes: AuditChanges
    school_id: UUID | None = None
    correlation_id: str | None = None
    actor_id: UUID | None = None
    actor_role: str | None = None
    purpose_code: str | None = None
    resource_id: UUID | None = None
    resource_ref: str | None = None
    reason_code: str | None = None
    ip_prefix: IPv4Network | IPv6Network | None = None
    user_agent_family: str | None = None

    def __post_init__(self) -> None:
        if self.event_schema_version != 1:
            raise AuditError("AUDIT_EVENT_INVALID")
        _matches(self.source_service, SERVICE_CODE)
        _matches(self.action, UPPER_CODE)
        _matches(self.resource_type, STABLE_CODE)
        _matches(self.request_id, REQUEST_ID)
        _matches(self.correlation_id, CORRELATION_ID)
        _matches(self.actor_role, STABLE_CODE)
        _matches(self.purpose_code, STABLE_CODE)
        _matches(self.resource_ref, STABLE_CODE)
        _matches(self.user_agent_family, STABLE_CODE)
        if self.reason_code is not None and UPPER_CODE.fullmatch(self.reason_code) is None:
            raise AuditError("AUDIT_EVENT_INVALID")
        for value in (self.source_event_id, self.school_id, self.actor_id, self.resource_id):
            _nonzero(value)
        _aware(self.occurred_at, "occurred_at")
        _aware(self.retention_until, "retention_until")
        if self.resource_id is not None and self.resource_ref is not None:
            raise AuditError("AUDIT_EVENT_INVALID")
        if self.result in {AuditResult.DENIED, AuditResult.FAILED} and self.reason_code is None:
            raise AuditError("AUDIT_EVENT_INVALID")
        if self.ip_prefix is not None:
            limit = 24 if self.ip_prefix.version == 4 else 48
            if self.ip_prefix.prefixlen > limit:
                raise AuditError("AUDIT_EVENT_INVALID")


@dataclass(frozen=True, slots=True)
class StoredAuditEvent:
    """The immutable database evidence record including server-controlled chain fields."""

    event: AuditEvent
    audit_event_id: UUID
    recorded_at: datetime
    integrity_partition: str
    hash_version: int
    previous_event_hash: bytes | None
    event_hash: bytes

    def __post_init__(self) -> None:
        _nonzero(self.audit_event_id)
        _aware(self.recorded_at, "recorded_at")
        if self.hash_version != 1:
            raise AuditError("AUDIT_INTEGRITY_FAILED")
        if self.previous_event_hash is not None and len(self.previous_event_hash) != 32:
            raise AuditError("AUDIT_INTEGRITY_FAILED")
        if len(self.event_hash) != 32:
            raise AuditError("AUDIT_INTEGRITY_FAILED")
        if self.event.retention_until <= self.recorded_at:
            raise AuditError("AUDIT_EVENT_INVALID")


@dataclass(frozen=True, slots=True)
class AppendOutcome:
    event: StoredAuditEvent
    duplicate: bool
