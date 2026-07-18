from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest
from audit_log_service.domain.errors import AuditError
from audit_log_service.schemas.events import AuditChangesV1, parse_audit_event
from pydantic import ValidationError

EVENT_ID = "00000000-0000-4000-8000-000000000101"
RESOURCE_ID = "00000000-0000-4000-8000-000000000201"


def _payload() -> dict[str, object]:
    return {
        "event_schema_version": 1,
        "source_service": "identity-service",
        "source_event_id": EVENT_ID,
        "correlation_id": "cor_0123456789abcdef",
        "action": "ROLE_ASSIGNMENT_CHANGED",
        "resource_type": "role_assignment",
        "resource_id": RESOURCE_ID,
        "request_id": "req_0123456789abcdef",
        "result": "success",
        "occurred_at": datetime(2026, 7, 18, 12, 0, tzinfo=UTC).isoformat(),
        "ip_prefix": "192.0.2.0/24",
        "user_agent_family": "service_client",
        "changes": {
            "schema_version": "audit_changes_v1",
            "changed_fields": ["status"],
            "state_before_codes": {"status": "pending"},
            "state_after_codes": {"status": "active"},
            "reference_ids": {"role_id": RESOURCE_ID},
            "policy_versions": {"rbac_policy": "rbac_v1"},
        },
    }


def test_parse_audit_event_accepts_json_compatible_opaque_values() -> None:
    parsed = parse_audit_event(_payload())

    assert parsed.source_event_id == UUID(EVENT_ID)
    assert str(parsed.ip_prefix) == "192.0.2.0/24"
    assert parsed.changes is not None
    assert parsed.changes.changed_fields == ("status",)


@pytest.mark.parametrize(
    "mutation",
    [
        {"actor_id": RESOURCE_ID},
        {"unexpected": "not_allowed"},
        {"ip_prefix": "192.0.2.4/32"},
        {"occurred_at": "2026-07-18T12:00:00"},
        {"request_id": None},
    ],
)
def test_parse_audit_event_rejects_untrusted_or_over_precise_input(
    mutation: dict[str, object],
) -> None:
    payload = _payload()
    payload.update(mutation)

    with pytest.raises(AuditError, match="AUDIT_EVENT_INVALID"):
        parse_audit_event(payload)


def test_parse_failure_does_not_echo_rejected_content() -> None:
    rejected_marker = "person@example.invalid"
    payload = _payload()
    payload["changes"] = {
        "schema_version": "audit_changes_v1",
        "reference_ids": {"role_id": rejected_marker},
    }

    with pytest.raises(AuditError) as caught:
        parse_audit_event(payload)

    assert rejected_marker not in str(caught.value)


def test_change_schema_rejects_unknown_keys_and_empty_content() -> None:
    with pytest.raises(ValidationError):
        AuditChangesV1.model_validate(
            {"schema_version": "audit_changes_v1", "raw_payload": "forbidden"}
        )
    with pytest.raises(ValidationError):
        AuditChangesV1.model_validate({"schema_version": "audit_changes_v1"})
    with pytest.raises(ValidationError):
        AuditChangesV1.model_validate(
            {"schema_version": "audit_changes_v2", "changed_fields": ["status"]}
        )


def test_change_schema_rejects_excessive_items_nested_values_and_forbidden_strings() -> None:
    excessive_counts = {f"count_{index}": index for index in range(33)}
    with pytest.raises(ValidationError):
        AuditChangesV1.model_validate(
            {
                "schema_version": "audit_changes_v1",
                "count_summary": excessive_counts,
            }
        )
    with pytest.raises(ValidationError):
        AuditChangesV1.model_validate(
            {
                "schema_version": "audit_changes_v1",
                "state_after_codes": {"status": {"nested": "forbidden"}},
            }
        )
    for forbidden_value in ("https://private.invalid/object", "image/jpeg;base64,AAAA"):
        with pytest.raises(ValidationError):
            AuditChangesV1.model_validate(
                {
                    "schema_version": "audit_changes_v1",
                    "policy_versions": {"rbac_policy": forbidden_value},
                }
            )
