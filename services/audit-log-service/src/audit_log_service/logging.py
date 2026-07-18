"""Minimal redacted logging fields for accepted audit operations."""

from __future__ import annotations

from audit_log_service.domain.models import AuditEvent


def safe_audit_log_fields(event: AuditEvent, operation: str) -> dict[str, str]:
    """Exclude actor, tenant, resource, changes, hashes, URLs, and payload content."""

    fields = {
        "service_name": "audit-log-service",
        "operation": operation,
        "source_service": event.source_service,
        "action": event.action,
        "result": event.result.value,
        "request_id": event.request_id,
    }
    if event.reason_code is not None:
        fields["reason_code"] = event.reason_code
    return fields
