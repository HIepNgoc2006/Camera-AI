from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
from camera_ai_audit import AuditIntent, UnavailableAuditIntentRecorder
from camera_ai_authorization import (
    AuditedAuthorizationService,
    AuthorizationAuditUnavailableError,
    AuthorizationRequest,
    ConsentState,
    LegalHoldState,
    ResourceState,
    RetentionState,
    ScopeDimension,
    ScopeGrant,
    load_catalog,
    permission_change_audit_intent,
)

REPO_ROOT = Path(__file__).resolve().parents[4]
CATALOG = load_catalog(
    REPO_ROOT / "packages" / "authorization-policy" / "permission-catalog-v1.json"
)
NOW = datetime(2026, 7, 28, 1, 30, tzinfo=UTC)


def _uuid(suffix: int) -> UUID:
    return UUID(f"00000000-0000-4000-8000-{suffix:012d}")


def denied_request() -> AuthorizationRequest:
    return AuthorizationRequest(
        decision_id=_uuid(1),
        request_id="req_synthetic_0001",
        correlation_id="cor_synthetic_0001",
        source_service="attendance-service",
        actor_id=_uuid(2),
        actor_authenticated=True,
        actor_permission_codes=frozenset(),
        permission_code="attendance.view_metadata",
        resource_type="attendance_record",
        action="view_metadata",
        resource_id=_uuid(3),
        resource_exists=True,
        policy_version="rbac_policy_v1",
        tenant_id=_uuid(4),
        school_id=_uuid(5),
        class_id=_uuid(6),
        guardian_subject_ref=_uuid(7),
        kitchen_zone_id=None,
        purpose_code="attendance_management",
        consent_state=ConsentState.ALLOWED,
        retention_state=RetentionState.ACTIVE,
        legal_hold_state=LegalHoldState.NONE,
        resource_state=ResourceState.AVAILABLE,
        sensitivity="high",
        approval_status="not_required",
        dependencies_available=True,
        now=NOW,
    )


def class_scope() -> ScopeGrant:
    return ScopeGrant(
        tenant_id=_uuid(4),
        school_ids=frozenset({_uuid(5)}),
        dimension=ScopeDimension.CLASS,
        scope_ids=frozenset({_uuid(6)}),
        valid_from=NOW - timedelta(days=1),
        valid_until=NOW + timedelta(days=1),
    )


class Recorder:
    def __init__(self) -> None:
        self.intents: list[AuditIntent] = []

    def record(self, intent: AuditIntent) -> None:
        self.intents.append(intent)


def test_denial_emits_minimized_registered_audit_intent() -> None:
    recorder = Recorder()
    service = AuditedAuthorizationService(CATALOG, recorder)

    decision = service.decide(denied_request(), class_scope())

    assert not decision.allowed
    assert len(recorder.intents) == 1
    payload = recorder.intents[0].publisher_payload()
    assert payload["action"] == "AUTHORIZATION_DECISION_DENIED"
    rendered = repr(payload)
    for forbidden in ("student_name", "face_embedding", "signed_url", "token", "role_name"):
        assert forbidden not in rendered


def test_denial_refuses_to_proceed_when_audit_recorder_is_unavailable() -> None:
    service = AuditedAuthorizationService(CATALOG, UnavailableAuditIntentRecorder())

    with pytest.raises(AuthorizationAuditUnavailableError, match="AUTHZ_AUDIT_UNAVAILABLE"):
        service.decide(denied_request(), class_scope())


def test_permission_change_audit_contains_only_opaque_references() -> None:
    intent = permission_change_audit_intent(
        permission_id=_uuid(20),
        actor_id=_uuid(21),
        school_id=_uuid(5),
        request_id="req_synthetic_0002",
        correlation_id="cor_synthetic_0002",
        occurred_at=NOW,
    )

    payload = intent.publisher_payload()
    assert payload["action"] == "PERMISSION_CHANGED"
    assert "role_name" not in repr(payload)
