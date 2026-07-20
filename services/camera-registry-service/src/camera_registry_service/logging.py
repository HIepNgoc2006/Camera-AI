"""Minimized Camera Registry log fields."""

from __future__ import annotations

from camera_registry_service.domain.models import RegistryChangeOutcome


def safe_change_log_fields(
    outcome: RegistryChangeOutcome,
    operation: str,
) -> dict[str, str]:
    return {
        "service_name": "camera-registry-service",
        "operation": operation,
        "action": outcome.audit_intent.action,
        "change_code": outcome.audit_intent.change_code,
        "resource_type": outcome.audit_intent.resource_type,
        "status": outcome.resource.status.value,
        "request_id": outcome.audit_intent.request_id,
        "result": "duplicate" if outcome.duplicate else "success",
    }
