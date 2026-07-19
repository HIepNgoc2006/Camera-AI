"""Fail-closed consent evaluation and audit-intent policy."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from consent_service.domain.models import (
    Consent,
    ConsentDecision,
    ConsentDecisionCode,
    ConsentEventType,
    ConsentStatus,
    Purpose,
    TrustedEvaluationContext,
)

AUDIT_ACTIONS = {
    ConsentEventType.REQUESTED: "CONSENT_REQUESTED",
    ConsentEventType.GRANTED: "CONSENT_GRANTED",
    ConsentEventType.DENIED: "CONSENT_DENIED",
    ConsentEventType.WITHDRAWN: "CONSENT_WITHDRAWN",
    ConsentEventType.EXPIRED: "CONSENT_EXPIRED",
    ConsentEventType.RESTRICTED: "CONSENT_RESTRICTED",
}


def evaluate_consent(
    consent: Consent | None,
    purpose: Purpose | None,
    *,
    context: TrustedEvaluationContext,
    expected_purpose_id: UUID,
    required_scope_codes: tuple[str, ...],
    expected_version: int | None,
    evaluated_at: datetime,
) -> ConsentDecision:
    """Return a non-throwing deny decision for every missing or ambiguous gate."""

    if consent is None or purpose is None:
        return ConsentDecision(False, ConsentDecisionCode.NOT_FOUND)
    if consent.school_id != context.school_id:
        return ConsentDecision(False, ConsentDecisionCode.NOT_FOUND)

    def decision(allowed: bool, reason: ConsentDecisionCode) -> ConsentDecision:
        return ConsentDecision(
            allowed,
            reason,
            consent_id=consent.consent_id,
            consent_version=consent.row_version,
        )

    if consent.subject_type is not context.subject_type or consent.subject_id != context.subject_id:
        return decision(False, ConsentDecisionCode.SUBJECT_MISMATCH)
    if consent.purpose_id != expected_purpose_id or purpose.purpose_id != expected_purpose_id:
        return decision(False, ConsentDecisionCode.PURPOSE_MISMATCH)
    if not context.relationship_verified:
        return decision(False, ConsentDecisionCode.AUTHORITY_DENIED)
    if expected_version is not None and consent.row_version != expected_version:
        return decision(False, ConsentDecisionCode.STALE_VERSION)
    if consent.status is ConsentStatus.WITHDRAWN:
        return decision(False, ConsentDecisionCode.WITHDRAWN)
    if consent.status is ConsentStatus.RESTRICTED:
        return decision(False, ConsentDecisionCode.RESTRICTED)
    if consent.status is ConsentStatus.EXPIRED:
        return decision(False, ConsentDecisionCode.EXPIRED)
    if consent.status is not ConsentStatus.GRANTED:
        return decision(False, ConsentDecisionCode.NOT_GRANTED)
    if consent.valid_from is None or evaluated_at < consent.valid_from:
        return decision(False, ConsentDecisionCode.NOT_YET_VALID)
    if consent.valid_to is not None and evaluated_at >= consent.valid_to:
        return decision(False, ConsentDecisionCode.EXPIRED)
    if not purpose.is_active_at(evaluated_at, context.school_id):
        return decision(False, ConsentDecisionCode.PURPOSE_INACTIVE)
    if not set(required_scope_codes).issubset(consent.scope_codes):
        return decision(False, ConsentDecisionCode.SCOPE_DENIED)
    if not set(required_scope_codes).issubset(purpose.data_categories):
        return decision(False, ConsentDecisionCode.SCOPE_DENIED)
    return decision(True, ConsentDecisionCode.ALLOWED)
