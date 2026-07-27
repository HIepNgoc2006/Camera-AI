"""Fail-closed consent gate contract for biometric event ingestion (Issue #139).

The adapter never interprets consent policy itself: it maps each biometric
event type onto one approved processing purpose, asks the consent gate for a
strict ``allowed | blocked | not_required`` decision, and persists that status
plus the policy version at rest. ``not_evaluated`` exists only as a legacy
schema value and must never be written again for face or emotion events.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from ansvis_adapter.domain.models import EventType

CONSENT_GATE_POLICY_VERSION = "consent_gate_v1"
CONSENT_UNAVAILABLE = "EVENT_CONSENT_UNAVAILABLE"
CONSENT_BLOCKED = "EVENT_CONSENT_BLOCKED"

_POLICY_VERSION_PATTERN = re.compile(r"^[a-z][a-z0-9_.:-]{0,63}$")
_REASON_CODE_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]{1,63}$")

CONSENT_PURPOSE_BY_EVENT_TYPE: dict[EventType, str] = {
    EventType.ATTENDANCE_FACE_OBSERVED: "attendance",
    EventType.TIMEKEEPING_FACE_OBSERVED: "timekeeping",
    EventType.EMOTION_OBSERVED: "emotion",
}

BIOMETRIC_EVENT_TYPES = frozenset(CONSENT_PURPOSE_BY_EVENT_TYPE)
_KNOWN_EVENT_TYPE_VALUES = frozenset(item.value for item in EventType)
_BIOMETRIC_EVENT_TYPE_VALUES = frozenset(item.value for item in BIOMETRIC_EVENT_TYPES)
_FANOUT_PERMITTED_STATUSES = frozenset({"allowed", "not_required"})


class ConsentGateStatus(StrEnum):
    ALLOWED = "allowed"
    BLOCKED = "blocked"
    NOT_REQUIRED = "not_required"


@dataclass(frozen=True, slots=True, kw_only=True)
class ConsentGateRequest:
    """One evaluation request; ``school_id`` is the trusted resolved scope."""

    school_id: UUID
    tenant_ref: str
    school_ref: str
    subject_ref: str | None
    purpose_code: str
    policy_version: str

    def __post_init__(self) -> None:
        if self.school_id.int == 0:
            raise ValueError("consent gate request requires a resolved school scope")
        if not self.tenant_ref or not self.school_ref:
            raise ValueError("consent gate request requires source references")
        if self.purpose_code not in CONSENT_PURPOSE_BY_EVENT_TYPE.values():
            raise ValueError("consent gate request requires an approved purpose")
        if _POLICY_VERSION_PATTERN.fullmatch(self.policy_version) is None:
            raise ValueError("consent gate request requires a stable policy version")


@dataclass(frozen=True, slots=True, kw_only=True)
class ConsentGateDecision:
    """Strict gate output validated before anything is persisted from it."""

    status: ConsentGateStatus
    reason_code: str
    policy_version: str

    def __post_init__(self) -> None:
        if not isinstance(self.status, ConsentGateStatus):
            raise ValueError("consent decision status must be a gate status")
        if _REASON_CODE_PATTERN.fullmatch(self.reason_code) is None:
            raise ValueError("consent decision requires a stable reason code")
        if _POLICY_VERSION_PATTERN.fullmatch(self.policy_version) is None:
            raise ValueError("consent decision requires a stable policy version")


NOT_REQUIRED_DECISION = ConsentGateDecision(
    status=ConsentGateStatus.NOT_REQUIRED,
    reason_code="CONSENT_NOT_REQUIRED",
    policy_version=CONSENT_GATE_POLICY_VERSION,
)


def consent_purpose_for(event_type: EventType) -> str | None:
    """Return the approved processing purpose, or None for non-biometric types."""

    return CONSENT_PURPOSE_BY_EVENT_TYPE.get(event_type)


def fanout_permitted(payload: Mapping[str, object]) -> bool:
    """Refuse fan-out unless the payload proves a non-biometric type or a real
    consent decision; unknown or malformed payloads fail closed."""

    event_type = payload.get("event_type")
    if not isinstance(event_type, str) or event_type not in _KNOWN_EVENT_TYPE_VALUES:
        return False
    if event_type not in _BIOMETRIC_EVENT_TYPE_VALUES:
        return True
    return payload.get("consent_gate_status") in _FANOUT_PERMITTED_STATUSES
