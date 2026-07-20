from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import UUID

import pytest
from audit_log_service.application.service import AppendAuditEventService
from audit_log_service.domain.errors import AuditError
from audit_log_service.domain.integrity import IntegritySigner, partition_for, signing_message
from audit_log_service.domain.models import (
    ActorType,
    AppendOutcome,
    AuditEvent,
    StoredAuditEvent,
    TrustedAuditContext,
)

NOW = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)
SCHOOL_ID = UUID("00000000-0000-4000-8000-000000000001")
ACTOR_ID = UUID("00000000-0000-4000-8000-000000000002")
RESOURCE_ID = UUID("00000000-0000-4000-8000-000000000003")
EVENT_ID = UUID("00000000-0000-4000-8000-000000000004")
AUDIT_ID = UUID("00000000-0000-4000-8000-000000000005")


class FakeSigner:
    def sign(self, message: bytes) -> bytes:
        return sha256(b"fake-test-signer\0" + message).digest()


class CapturingRepository:
    def __init__(self) -> None:
        self.received: AuditEvent | None = None

    def append(
        self,
        event: AuditEvent,
        *,
        recorded_at: datetime,
        audit_event_id: UUID,
        signer: IntegritySigner,
    ) -> AppendOutcome:
        self.received = event
        unsigned = StoredAuditEvent(
            event=event,
            audit_event_id=audit_event_id,
            recorded_at=recorded_at,
            integrity_partition=partition_for(recorded_at),
            hash_version=1,
            previous_event_hash=None,
            event_hash=bytes(32),
        )
        stored = replace(unsigned, event_hash=signer.sign(signing_message(unsigned)))
        return AppendOutcome(stored, duplicate=False)

    def verify_partition(self, partition: str, signer: IntegritySigner) -> None:
        return None


def _context(source_service: str = "identity-service") -> TrustedAuditContext:
    return TrustedAuditContext(
        source_service=source_service,
        actor_type=ActorType.USER,
        actor_id=ACTOR_ID,
        actor_role="system_admin",
        school_id=SCHOOL_ID,
        retention_until=NOW + timedelta(days=30),
    )


def _payload() -> dict[str, object]:
    return {
        "event_schema_version": 1,
        "source_service": "identity-service",
        "source_event_id": str(EVENT_ID),
        "action": "ROLE_ASSIGNMENT_CHANGED",
        "resource_type": "role_assignment",
        "resource_id": str(RESOURCE_ID),
        "request_id": "req_0123456789abcdef",
        "result": "success",
        "occurred_at": NOW.isoformat(),
        "changes": {
            "schema_version": "audit_changes_v1",
            "changed_fields": ["status"],
            "state_before_codes": {"status": "pending"},
            "state_after_codes": {"status": "active"},
            "reference_ids": {"role_id": str(RESOURCE_ID)},
            "policy_versions": {"rbac_policy": "rbac_v1"},
        },
    }


def _service(repository: CapturingRepository) -> AppendAuditEventService:
    return AppendAuditEventService(
        repository,
        FakeSigner(),
        clock=lambda: NOW,
        identifier_factory=lambda: AUDIT_ID,
    )


def test_append_binds_actor_tenant_time_and_hash_fields_from_server_context() -> None:
    repository = CapturingRepository()

    outcome = _service(repository).append(_payload(), _context())

    assert outcome.duplicate is False
    assert repository.received is not None
    assert repository.received.actor_id == ACTOR_ID
    assert repository.received.school_id == SCHOOL_ID
    assert outcome.event.recorded_at == NOW
    assert outcome.event.integrity_partition == "2026-07-18:00"
    assert len(outcome.event.event_hash) == 32


def test_append_rejects_source_identity_spoofing() -> None:
    payload = _payload()
    payload["source_service"] = "school-service"

    with pytest.raises(AuditError, match="AUDIT_EVENT_INVALID"):
        _service(CapturingRepository()).append(payload, _context())


def test_append_rejects_unknown_action_and_action_specific_change() -> None:
    unknown = _payload()
    unknown["action"] = "UNAPPROVED_ACTION"
    with pytest.raises(AuditError, match="AUDIT_ACTION_UNKNOWN"):
        _service(CapturingRepository()).append(unknown, _context())

    forbidden = _payload()
    forbidden["changes"] = {
        "schema_version": "audit_changes_v1",
        "changed_fields": ["email"],
    }
    with pytest.raises(AuditError, match="AUDIT_CHANGE_FORBIDDEN") as caught:
        _service(CapturingRepository()).append(forbidden, _context())
    assert "email" not in str(caught.value)


def test_append_rejects_expired_retention_context() -> None:
    context = replace(_context(), retention_until=NOW)

    with pytest.raises(AuditError, match="AUDIT_EVENT_INVALID"):
        _service(CapturingRepository()).append(_payload(), context)


def test_camera_registry_zone_change_matches_the_minimized_audit_policy() -> None:
    payload: dict[str, object] = {
        "event_schema_version": 1,
        "source_service": "camera-registry-service",
        "source_event_id": str(EVENT_ID),
        "action": "CAMERA_MAPPING_CHANGED",
        "purpose_code": "camera_operations",
        "resource_type": "camera_zone",
        "resource_id": str(RESOURCE_ID),
        "request_id": "req_0123456789abcdef",
        "result": "success",
        "occurred_at": NOW.isoformat(),
        "changes": {
            "schema_version": "audit_changes_v1",
            "changed_fields": ["status", "zone"],
            "state_before_codes": {"status": "active"},
            "state_after_codes": {"status": "inactive"},
            "reference_ids": {"zone_id": str(RESOURCE_ID)},
            "policy_versions": {"camera_mapping": "camera_policy_v1"},
        },
    }

    outcome = _service(CapturingRepository()).append(
        payload,
        _context("camera-registry-service"),
    )

    assert outcome.event.event.action == "CAMERA_MAPPING_CHANGED"
    assert outcome.event.event.resource_type == "camera_zone"
