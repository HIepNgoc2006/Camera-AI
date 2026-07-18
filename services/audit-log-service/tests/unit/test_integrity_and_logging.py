from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from audit_log_service.domain.errors import AuditError
from audit_log_service.domain.integrity import semantic_bytes
from audit_log_service.domain.models import (
    ActorType,
    AuditChanges,
    AuditEvent,
    AuditResult,
)
from audit_log_service.infrastructure.integrity import HmacSha256IntegritySigner
from audit_log_service.logging import safe_audit_log_fields

NOW = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)


def _event() -> AuditEvent:
    return AuditEvent(
        event_schema_version=1,
        source_service="identity-service",
        source_event_id=UUID("00000000-0000-4000-8000-000000000010"),
        actor_type=ActorType.USER,
        actor_id=UUID("00000000-0000-4000-8000-000000000011"),
        actor_role="system_admin",
        school_id=UUID("00000000-0000-4000-8000-000000000012"),
        action="ROLE_ASSIGNMENT_CHANGED",
        resource_type="role_assignment",
        resource_id=UUID("00000000-0000-4000-8000-000000000013"),
        request_id="req_0123456789abcdef",
        result=AuditResult.SUCCESS,
        changes=AuditChanges(changed_fields=("status",)),
        occurred_at=NOW,
        retention_until=NOW + timedelta(days=30),
    )


def test_hmac_signer_is_deterministic_and_never_reveals_key_material() -> None:
    key = bytes(range(32))
    signer = HmacSha256IntegritySigner(key)

    assert signer.sign(b"message") == signer.sign(b"message")
    assert len(signer.sign(b"message")) == 32
    assert key.hex() not in repr(signer)
    assert "redacted" in repr(signer)


def test_hmac_signer_rejects_short_key_without_echoing_it() -> None:
    with pytest.raises(AuditError, match="AUDIT_INTEGRITY_FAILED") as caught:
        HmacSha256IntegritySigner(b"short")

    assert "short" not in str(caught.value)


def test_safe_logging_excludes_sensitive_and_integrity_fields() -> None:
    event = _event()

    fields = safe_audit_log_fields(event, "append")

    assert fields == {
        "service_name": "audit-log-service",
        "operation": "append",
        "source_service": "identity-service",
        "action": "ROLE_ASSIGNMENT_CHANGED",
        "result": "success",
        "request_id": "req_0123456789abcdef",
    }
    serialized = repr(fields)
    for forbidden in (str(event.actor_id), str(event.school_id), str(event.resource_id), "changes"):
        assert forbidden not in serialized


def test_canonicalization_is_stable_for_equivalent_change_map_order() -> None:
    first = _event()
    second = replace(
        first,
        changes=AuditChanges(
            changed_fields=("status",),
            policy_versions=(("rbac_policy", "rbac_v1"),),
            reference_ids=(
                ("scope_id", UUID("00000000-0000-4000-8000-000000000015")),
                ("role_id", UUID("00000000-0000-4000-8000-000000000014")),
            ),
        ),
    )
    third = replace(
        first,
        changes=AuditChanges(
            changed_fields=("status",),
            reference_ids=(
                ("role_id", UUID("00000000-0000-4000-8000-000000000014")),
                ("scope_id", UUID("00000000-0000-4000-8000-000000000015")),
            ),
            policy_versions=(("rbac_policy", "rbac_v1"),),
        ),
    )

    assert semantic_bytes(second) == semantic_bytes(third)
