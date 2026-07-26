"""Shape-validated audit intents mirroring the AuditEventV1 publisher contract.

Mirrored constraints (patterns, sizes, denied/failed-requires-reason) come from the owning
audit-log-service schema; the authoritative action policy (`validate_action_policy`) still runs
at delivery. Free-text, media, tokens, secrets and personal values structurally cannot appear:
every field is a bounded stable code, UUID, count or timestamp.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID

AUDIT_EVENT_SCHEMA_VERSION = 1

_SERVICE_PATTERN = re.compile(r"^[a-z][a-z0-9-]{1,62}[a-z0-9]$")
_ACTION_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]{2,95}$")
_REASON_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]{1,63}$")
_STABLE_CODE_PATTERN = re.compile(r"^[a-z][a-z0-9_.:-]{0,63}$")
_REQUEST_PATTERN = re.compile(r"^req_[A-Za-z0-9_-]{8,120}$")
_CORRELATION_PATTERN = re.compile(r"^cor_[A-Za-z0-9_-]{8,120}$")
_MAX_ITEMS = 32


class AuditIntentInvalidError(ValueError):
    """Raised with a stable message; never carries the offending value."""

    def __init__(self) -> None:
        super().__init__("AUDIT_INTENT_INVALID")


class IntentResult(StrEnum):
    SUCCESS = "success"
    DENIED = "denied"
    FAILED = "failed"


def _require(condition: bool) -> None:
    if not condition:
        raise AuditIntentInvalidError


def _aware(value: datetime) -> None:
    _require(value.tzinfo is not None and value.utcoffset() is not None)


@dataclass(frozen=True, slots=True, kw_only=True)
class AuditIntent:
    """One publisher-side audit event awaiting trusted-context delivery."""

    source_service: str
    source_event_id: UUID
    action: str
    resource_type: str
    request_id: str
    result: IntentResult
    occurred_at: datetime
    reason_code: str | None = None
    correlation_id: str | None = None
    resource_id: UUID | None = None
    resource_ref: str | None = None
    purpose_code: str | None = None
    school_id: UUID | None = None
    reference_ids: tuple[tuple[str, UUID], ...] = field(default=())
    count_summary: tuple[tuple[str, int], ...] = field(default=())
    policy_versions: tuple[tuple[str, str], ...] = field(default=())

    def __post_init__(self) -> None:
        _require(_SERVICE_PATTERN.fullmatch(self.source_service) is not None)
        _require(_ACTION_PATTERN.fullmatch(self.action) is not None)
        _require(_STABLE_CODE_PATTERN.fullmatch(self.resource_type) is not None)
        _require(_REQUEST_PATTERN.fullmatch(self.request_id) is not None)
        _require(self.source_event_id.int != 0)
        _aware(self.occurred_at)
        if self.result in {IntentResult.DENIED, IntentResult.FAILED}:
            _require(self.reason_code is not None)
        if self.reason_code is not None:
            _require(_REASON_PATTERN.fullmatch(self.reason_code) is not None)
        if self.correlation_id is not None:
            _require(_CORRELATION_PATTERN.fullmatch(self.correlation_id) is not None)
        for optional_code in (self.resource_ref, self.purpose_code):
            if optional_code is not None:
                _require(_STABLE_CODE_PATTERN.fullmatch(optional_code) is not None)
        _require(not (self.resource_id is not None and self.resource_ref is not None))
        if self.resource_id is not None:
            _require(self.resource_id.int != 0)
        if self.school_id is not None:
            _require(self.school_id.int != 0)
        for pairs in (self.reference_ids, self.count_summary, self.policy_versions):
            _require(len(pairs) <= _MAX_ITEMS)
        for name, reference in self.reference_ids:
            _require(_STABLE_CODE_PATTERN.fullmatch(name) is not None and reference.int != 0)
        for name, count in self.count_summary:
            _require(_STABLE_CODE_PATTERN.fullmatch(name) is not None)
            _require(0 <= count <= 1_000_000_000)
        for name, version in self.policy_versions:
            _require(_STABLE_CODE_PATTERN.fullmatch(name) is not None)
            _require(_STABLE_CODE_PATTERN.fullmatch(version) is not None)

    def publisher_payload(self) -> dict[str, object]:
        """Return the AuditEventV1 publisher mapping consumed at delivery."""

        payload: dict[str, object] = {
            "event_schema_version": AUDIT_EVENT_SCHEMA_VERSION,
            "source_service": self.source_service,
            "source_event_id": str(self.source_event_id),
            "action": self.action,
            "resource_type": self.resource_type,
            "request_id": self.request_id,
            "result": self.result.value,
            "occurred_at": self.occurred_at.isoformat(),
        }
        for key, value in (
            ("reason_code", self.reason_code),
            ("correlation_id", self.correlation_id),
            ("resource_ref", self.resource_ref),
            ("purpose_code", self.purpose_code),
        ):
            if value is not None:
                payload[key] = value
        if self.resource_id is not None:
            payload["resource_id"] = str(self.resource_id)
        changes: dict[str, object] = {}
        if self.reference_ids:
            changes["reference_ids"] = {name: str(ref) for name, ref in self.reference_ids}
        if self.count_summary:
            changes["count_summary"] = dict(self.count_summary)
        if self.policy_versions:
            changes["policy_versions"] = dict(self.policy_versions)
        if changes:
            changes["schema_version"] = "audit_changes_v1"
            payload["changes"] = changes
        return payload
