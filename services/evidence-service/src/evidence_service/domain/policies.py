"""Evidence selection, lifecycle and access policy rules."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime

from evidence_service.domain.errors import EvidenceError
from evidence_service.domain.models import (
    AccessAction,
    ConsentState,
    EvidenceObject,
    EvidenceState,
    LegalHoldState,
    ScanState,
)

POLICY_VERSION = "evidence_access_policy_v1"
SELECTION_POLICY_VERSION = "evidence_selection_policy_v1"

_TRANSITIONS = {
    EvidenceState.PENDING_UPLOAD: frozenset(
        {EvidenceState.QUARANTINED, EvidenceState.FAILED, EvidenceState.MISSING}
    ),
    EvidenceState.QUARANTINED: frozenset(
        {EvidenceState.AVAILABLE, EvidenceState.FAILED, EvidenceState.MISSING}
    ),
    EvidenceState.AVAILABLE: frozenset({EvidenceState.DELETE_PENDING, EvidenceState.MISSING}),
    EvidenceState.DELETE_PENDING: frozenset({EvidenceState.DELETED, EvidenceState.FAILED}),
    EvidenceState.MISSING: frozenset({EvidenceState.QUARANTINED, EvidenceState.DELETE_PENDING}),
    EvidenceState.FAILED: frozenset({EvidenceState.DELETE_PENDING}),
    EvidenceState.DELETED: frozenset(),
}

_SELECTION_BOUNDS = {
    "student_attendance": (1, 4),
    "staff_timekeeping": (1, 4),
    "emotion_insight": (0, 0),
    "littering": (5, 20),
    "smoking": (6, 20),
    "student_uniform": (2, 5),
    "kitchen_ppe": (2, 6),
}

_PERMISSIONS = {
    AccessAction.VIEW_METADATA: "evidence.view_metadata",
    AccessAction.VIEW_THUMBNAIL: "evidence.view_thumbnail",
    AccessAction.VIEW_ORIGINAL: "evidence.view_original",
    AccessAction.DOWNLOAD: "evidence.download",
    AccessAction.EXPORT: "evidence.export",
}

_REASON_REQUIRED = frozenset(
    {AccessAction.VIEW_ORIGINAL, AccessAction.DOWNLOAD, AccessAction.EXPORT}
)
_REASON_ALLOWLIST = frozenset(
    {
        "BUSINESS_REVIEW",
        "ATTENDANCE_AUDIT",
        "TIMEKEEPING_AUDIT",
        "VIOLATION_REVIEW",
        "SECURITY_INVESTIGATION",
        "LEGAL_REQUEST",
        "DATA_SUBJECT_REQUEST",
        "MANAGEMENT_REPORT",
    }
)
_EXPORT_RECIPIENT_CONTROLS = frozenset(
    {
        "authenticated_requester",
        "approved_internal_recipient",
        "approved_external_recipient_with_expiry",
    }
)


@dataclass(frozen=True, slots=True)
class PolicyActivation:
    privacy_legal_approved: bool = False
    security_ops_approved: bool = False
    business_owner_approved: bool = False
    policy_version: str = POLICY_VERSION

    @property
    def active(self) -> bool:
        return (
            self.policy_version == POLICY_VERSION
            and self.privacy_legal_approved
            and self.security_ops_approved
            and self.business_owner_approved
        )


def new_object_key() -> str:
    random_id = secrets.token_hex(16)
    return f"evidence/v1/{random_id[:2]}/{random_id}"


def require_transition(current: EvidenceState, target: EvidenceState) -> None:
    if target not in _TRANSITIONS[current]:
        raise EvidenceError("EVIDENCE_STATE_CONFLICT")


def selection_bounds(event_type: str) -> tuple[int, int]:
    try:
        return _SELECTION_BOUNDS[event_type]
    except KeyError:
        raise EvidenceError("EVIDENCE_SELECTION_POLICY_UNAVAILABLE") from None


def validate_selection(event_type: str, sequence_count: int) -> None:
    minimum, maximum = selection_bounds(event_type)
    if not minimum <= sequence_count <= maximum:
        raise EvidenceError("EVIDENCE_SELECTION_INVALID")


def permission_for(action: AccessAction) -> str:
    return _PERMISSIONS[action]


def audit_actions(action: AccessAction) -> tuple[str, str]:
    if action is AccessAction.EXPORT:
        return "EVIDENCE_EXPORT_GRANTED", "EVIDENCE_EXPORT_DENIED"
    return "EVIDENCE_VIEW_GRANTED", "EVIDENCE_VIEW_DENIED"


def access_ttl(action: AccessAction, requested: int | None) -> int:
    hard_max = 120 if action is AccessAction.EXPORT else 300
    ttl = 60 if requested is None else requested
    if not 1 <= ttl <= hard_max:
        raise EvidenceError("EVIDENCE_ACCESS_INVALID")
    return ttl


def assert_access_preconditions(
    *,
    evidence: EvidenceObject,
    action: AccessAction,
    consent_state: ConsentState,
    reason_code: str | None,
    approval_status: str,
    recipient_control_code: str | None,
    activation: PolicyActivation,
    now: datetime,
) -> None:
    if not activation.active:
        raise EvidenceError("EVIDENCE_ACCESS_UNAVAILABLE")
    if evidence.state is not EvidenceState.AVAILABLE or evidence.scan_state is not ScanState.CLEAN:
        raise EvidenceError("EVIDENCE_NOT_AVAILABLE")
    if evidence.retention_expires_at <= now:
        raise EvidenceError("EVIDENCE_NOT_AVAILABLE")
    if evidence.legal_hold_state is LegalHoldState.UNAVAILABLE:
        raise EvidenceError("EVIDENCE_ACCESS_UNAVAILABLE")
    if consent_state not in {ConsentState.ALLOWED, ConsentState.NOT_REQUIRED}:
        raise EvidenceError("EVIDENCE_NOT_FOUND")
    if action in _REASON_REQUIRED and reason_code not in _REASON_ALLOWLIST:
        raise EvidenceError("EVIDENCE_ACCESS_INVALID")
    if action is AccessAction.EXPORT:
        if approval_status != "approved":
            raise EvidenceError("EVIDENCE_EXPORT_APPROVAL_REQUIRED")
        if recipient_control_code not in _EXPORT_RECIPIENT_CONTROLS:
            raise EvidenceError("EVIDENCE_EXPORT_RECIPIENT_INVALID")
