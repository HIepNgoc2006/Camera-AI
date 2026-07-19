"""Minimized log fields for consent changes and decisions."""

from __future__ import annotations

from consent_service.domain.models import ConsentChangeOutcome, ConsentDecision


def safe_change_log_fields(
    outcome: ConsentChangeOutcome,
    operation: str,
) -> dict[str, str]:
    fields = {
        "service_name": "consent-service",
        "operation": operation,
        "action": outcome.audit_intent.action,
        "status": outcome.consent.status.value,
        "request_id": outcome.event.request_id,
        "result": "duplicate" if outcome.duplicate else "success",
    }
    if outcome.event.reason_code is not None:
        fields["reason_code"] = outcome.event.reason_code
    return fields


def safe_decision_log_fields(decision: ConsentDecision) -> dict[str, str]:
    return {
        "service_name": "consent-service",
        "operation": "evaluate_consent",
        "result": "allowed" if decision.allowed else "denied",
        "reason_code": decision.reason_code.value,
    }
