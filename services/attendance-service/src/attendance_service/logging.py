"""Allowlisted, minimized fields for attendance operational logs."""

from __future__ import annotations

from attendance_service.domain.models import AttendanceCorrectionOutcome, AttendanceIngestionOutcome


def safe_ingestion_log_fields(outcome: AttendanceIngestionOutcome) -> dict[str, str]:
    if outcome.blocked:
        result = "consent_blocked"
    elif outcome.duplicate:
        result = "duplicate"
    else:
        result = "accepted"
    status = "not_created" if outcome.record is None else outcome.record.status.value
    return {
        "service_name": "attendance-service",
        "operation": "ingest_normalized_event",
        "result": result,
        "status": status,
    }


def safe_correction_log_fields(outcome: AttendanceCorrectionOutcome) -> dict[str, str]:
    return {
        "service_name": "attendance-service",
        "operation": "correct_attendance",
        "action": outcome.audit_intent.action,
        "request_id": outcome.correction.request_id,
        "result": outcome.audit_intent.result,
        "status": outcome.record.status.value,
    }
