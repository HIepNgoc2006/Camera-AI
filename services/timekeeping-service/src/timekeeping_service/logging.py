"""Allowlisted, minimized fields for timekeeping operational logs."""

from __future__ import annotations

from timekeeping_service.domain.models import (
    TimekeepingCorrectionOutcome,
    TimekeepingIngestionOutcome,
)


def safe_ingestion_log_fields(outcome: TimekeepingIngestionOutcome) -> dict[str, str]:
    if outcome.blocked:
        result = "consent_blocked"
    elif outcome.duplicate:
        result = "duplicate"
    else:
        result = "accepted"
    status = "not_created" if outcome.record is None else outcome.record.status.value
    return {
        "service_name": "timekeeping-service",
        "operation": "ingest_normalized_event",
        "result": result,
        "status": status,
    }


def safe_correction_log_fields(outcome: TimekeepingCorrectionOutcome) -> dict[str, str]:
    return {
        "service_name": "timekeeping-service",
        "operation": "correct_timekeeping",
        "action": outcome.audit_intent.action,
        "request_id": outcome.correction.request_id,
        "result": outcome.audit_intent.result,
        "status": outcome.record.status.value,
    }
