"""Fail-closed tri-state processing gate for biometric event ingestion (Issue #139).

The gate maps the rich consent evaluation onto the strict contract the event
ingestion path persists at rest: ``allowed | blocked | not_required`` plus the
policy version the decision was made under. Every missing, unknown, ambiguous
or unsupported condition maps to ``blocked``; only a transport/storage outage
is allowed to surface as an exception so the caller can defer with a durable
receipt instead of persisting an unevaluated biometric event.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from consent_service.domain.errors import ConsentError
from consent_service.domain.models import (
    UPPER_CODE,
    Consent,
    ConsentDecisionCode,
    Purpose,
    SubjectType,
    TrustedEvaluationContext,
)
from consent_service.domain.policies import evaluate_consent

PROCESSING_GATE_POLICY_VERSION = "consent_gate_v1"
SUPPORTED_GATE_POLICY_VERSIONS = frozenset({PROCESSING_GATE_POLICY_VERSION})


class ProcessingConsentStatus(StrEnum):
    ALLOWED = "allowed"
    BLOCKED = "blocked"
    NOT_REQUIRED = "not_required"


class ProcessingGateReason(StrEnum):
    """Gate-owned stable reasons beyond the consent decision codes."""

    POLICY_VERSION_UNSUPPORTED = "CONSENT_POLICY_VERSION_UNSUPPORTED"
    PURPOSE_UNSUPPORTED = "CONSENT_PURPOSE_UNSUPPORTED"
    PURPOSE_INACTIVE = "CONSENT_PURPOSE_INACTIVE"
    PURPOSE_AMBIGUOUS = "CONSENT_PURPOSE_AMBIGUOUS"
    SUBJECT_UNRESOLVED = "CONSENT_SUBJECT_UNRESOLVED"
    CONSENT_AMBIGUOUS = "CONSENT_AMBIGUOUS"
    NOT_REQUIRED = "CONSENT_NOT_REQUIRED"


@dataclass(frozen=True, slots=True, kw_only=True)
class ProcessingPurpose:
    """One approved biometric processing purpose the gate can evaluate."""

    code: str
    subject_type: SubjectType
    required_scope_codes: tuple[str, ...]


PROCESSING_PURPOSES: dict[str, ProcessingPurpose] = {
    "attendance": ProcessingPurpose(
        code="attendance",
        subject_type=SubjectType.STUDENT,
        required_scope_codes=("attendance", "biometric"),
    ),
    "timekeeping": ProcessingPurpose(
        code="timekeeping",
        subject_type=SubjectType.STAFF,
        required_scope_codes=("biometric", "timekeeping"),
    ),
    "emotion": ProcessingPurpose(
        code="emotion",
        subject_type=SubjectType.STUDENT,
        required_scope_codes=("biometric", "emotion"),
    ),
}


@dataclass(frozen=True, slots=True, kw_only=True)
class ProcessingConsentDecision:
    """Strict gate output; ``policy_version`` is what the event persists at rest."""

    status: ProcessingConsentStatus
    reason_code: str
    policy_version: str

    def __post_init__(self) -> None:
        if UPPER_CODE.fullmatch(self.reason_code) is None:
            raise ConsentError("CONSENT_INPUT_INVALID")


@dataclass(frozen=True, slots=True)
class ProcessingLookup:
    """Bounded repository snapshot for one subject/purpose evaluation."""

    purposes: tuple[Purpose, ...]
    consents: tuple[Consent, ...]


def resolve_subject(subject_ref: str | None) -> UUID | None:
    """Return the subject identity or None when the reference cannot be trusted."""

    if subject_ref is None:
        return None
    try:
        subject_id = UUID(subject_ref.strip())
    except (AttributeError, TypeError, ValueError):
        return None
    return None if subject_id.int == 0 else subject_id


def _blocked(reason: str, policy_version: str) -> ProcessingConsentDecision:
    return ProcessingConsentDecision(
        status=ProcessingConsentStatus.BLOCKED,
        reason_code=reason,
        policy_version=policy_version,
    )


def decide_processing(
    lookup: ProcessingLookup,
    *,
    school_id: UUID,
    subject_id: UUID | None,
    purpose_code: str,
    gate_policy_version: str,
    evaluated_at: datetime,
) -> ProcessingConsentDecision:
    """Pure fail-closed mapping from a bounded lookup to the tri-state decision."""

    if gate_policy_version not in SUPPORTED_GATE_POLICY_VERSIONS:
        return _blocked(
            ProcessingGateReason.POLICY_VERSION_UNSUPPORTED.value,
            PROCESSING_GATE_POLICY_VERSION,
        )
    mapping = PROCESSING_PURPOSES.get(purpose_code)
    if mapping is None:
        return _blocked(
            ProcessingGateReason.PURPOSE_UNSUPPORTED.value, PROCESSING_GATE_POLICY_VERSION
        )
    active_purposes = tuple(
        purpose for purpose in lookup.purposes if purpose.is_active_at(evaluated_at, school_id)
    )
    if not active_purposes:
        return _blocked(ProcessingGateReason.PURPOSE_INACTIVE.value, PROCESSING_GATE_POLICY_VERSION)
    if len(active_purposes) > 1:
        return _blocked(
            ProcessingGateReason.PURPOSE_AMBIGUOUS.value, PROCESSING_GATE_POLICY_VERSION
        )
    purpose = active_purposes[0]
    if not purpose.requires_biometric_consent:
        return ProcessingConsentDecision(
            status=ProcessingConsentStatus.NOT_REQUIRED,
            reason_code=ProcessingGateReason.NOT_REQUIRED.value,
            policy_version=PROCESSING_GATE_POLICY_VERSION,
        )
    if subject_id is None:
        return _blocked(
            ProcessingGateReason.SUBJECT_UNRESOLVED.value, PROCESSING_GATE_POLICY_VERSION
        )
    matching = tuple(
        consent for consent in lookup.consents if consent.purpose_id == purpose.purpose_id
    )
    if not matching:
        return _blocked(ConsentDecisionCode.NOT_FOUND.value, PROCESSING_GATE_POLICY_VERSION)
    if len(matching) > 1:
        return _blocked(
            ProcessingGateReason.CONSENT_AMBIGUOUS.value, PROCESSING_GATE_POLICY_VERSION
        )
    consent = matching[0]
    decision = evaluate_consent(
        consent,
        purpose,
        context=TrustedEvaluationContext(
            school_id=school_id,
            subject_type=mapping.subject_type,
            subject_id=subject_id,
            relationship_verified=True,
        ),
        expected_purpose_id=purpose.purpose_id,
        required_scope_codes=mapping.required_scope_codes,
        expected_version=None,
        evaluated_at=evaluated_at,
    )
    if decision.allowed:
        return ProcessingConsentDecision(
            status=ProcessingConsentStatus.ALLOWED,
            reason_code=ConsentDecisionCode.ALLOWED.value,
            policy_version=consent.policy_version,
        )
    return _blocked(decision.reason_code.value, consent.policy_version)
