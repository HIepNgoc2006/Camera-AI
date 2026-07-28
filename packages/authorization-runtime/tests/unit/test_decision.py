from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
from camera_ai_authorization import (
    AuthorizationRequest,
    ConsentState,
    LegalHoldState,
    ResourceState,
    RetentionState,
    ScopeDimension,
    ScopeGrant,
    evaluate_authorization,
    load_catalog,
)

REPO_ROOT = Path(__file__).resolve().parents[4]
CATALOG = load_catalog(
    REPO_ROOT / "packages" / "authorization-policy" / "permission-catalog-v1.json"
)
NOW = datetime(2026, 7, 28, 1, 30, tzinfo=UTC)


def _uuid(suffix: int) -> UUID:
    return UUID(f"00000000-0000-4000-8000-{suffix:012d}")


def request(**overrides: object) -> AuthorizationRequest:
    values: dict[str, object] = {
        "decision_id": _uuid(1),
        "request_id": "req_synthetic_0001",
        "correlation_id": "cor_synthetic_0001",
        "source_service": "attendance-service",
        "actor_id": _uuid(2),
        "actor_authenticated": True,
        "actor_permission_codes": frozenset({"attendance.view_metadata"}),
        "permission_code": "attendance.view_metadata",
        "resource_type": "attendance_record",
        "action": "view_metadata",
        "resource_id": _uuid(3),
        "resource_exists": True,
        "policy_version": "rbac_policy_v1",
        "tenant_id": _uuid(4),
        "school_id": _uuid(5),
        "class_id": _uuid(6),
        "guardian_subject_ref": _uuid(7),
        "kitchen_zone_id": None,
        "purpose_code": "attendance_management",
        "consent_state": ConsentState.ALLOWED,
        "retention_state": RetentionState.ACTIVE,
        "legal_hold_state": LegalHoldState.NONE,
        "resource_state": ResourceState.AVAILABLE,
        "sensitivity": "high",
        "approval_status": "not_required",
        "dependencies_available": True,
        "now": NOW,
    }
    values.update(overrides)
    return AuthorizationRequest(**values)  # type: ignore[arg-type]


def scope(**overrides: object) -> ScopeGrant:
    values: dict[str, object] = {
        "tenant_id": _uuid(4),
        "school_ids": frozenset({_uuid(5)}),
        "dimension": ScopeDimension.CLASS,
        "scope_ids": frozenset({_uuid(6)}),
        "valid_from": NOW - timedelta(days=1),
        "valid_until": NOW + timedelta(days=1),
    }
    values.update(overrides)
    return ScopeGrant(**values)  # type: ignore[arg-type]


def test_allowed_decision_uses_permission_code_not_role_name() -> None:
    decision = evaluate_authorization(request(), scope(), CATALOG)

    assert decision.allowed
    assert decision.required_permission_code == "attendance.view_metadata"
    assert decision.public_http_status == 0


@pytest.mark.parametrize(
    ("request_overrides", "scope_overrides", "reason"),
    [
        ({"actor_authenticated": False}, {}, "AUTHZ_ACTOR_UNAUTHENTICATED"),
        ({"actor_permission_codes": frozenset()}, {}, "AUTHZ_PERMISSION_DENIED"),
        ({"resource_exists": False}, {}, "AUTHZ_NOT_FOUND"),
        ({"school_id": _uuid(50)}, {}, "AUTHZ_SCHOOL_SCOPE_DENIED"),
        ({"class_id": None}, {}, "AUTHZ_OBJECT_SCOPE_DENIED"),
        ({"purpose_code": "unapproved_purpose"}, {}, "AUTHZ_PURPOSE_DENIED"),
        ({"consent_state": ConsentState.BLOCKED}, {}, "AUTHZ_CONSENT_DENIED"),
        ({"consent_state": ConsentState.UNAVAILABLE}, {}, "AUTHZ_CONSENT_UNAVAILABLE"),
        ({"retention_state": RetentionState.EXPIRED}, {}, "AUTHZ_RETENTION_DENIED"),
        ({"legal_hold_state": LegalHoldState.UNAVAILABLE}, {}, "AUTHZ_LEGAL_HOLD_UNAVAILABLE"),
        ({"resource_state": ResourceState.QUARANTINED}, {}, "AUTHZ_RESOURCE_UNAVAILABLE"),
        ({"dependencies_available": False}, {}, "AUTHZ_DEPENDENCY_UNAVAILABLE"),
        ({"policy_version": None}, {}, "AUTHZ_POLICY_UNAVAILABLE"),
        ({"policy_version": "rbac_policy_unknown"}, {}, "AUTHZ_POLICY_UNAVAILABLE"),
        ({}, {"tenant_id": _uuid(51)}, "AUTHZ_TENANT_SCOPE_DENIED"),
        (
            {},
            {"valid_until": NOW - timedelta(seconds=1)},
            "AUTHZ_ASSIGNMENT_EXPIRED",
        ),
    ],
)
def test_each_singly_missing_or_stale_boundary_denies(
    request_overrides: dict[str, object],
    scope_overrides: dict[str, object],
    reason: str,
) -> None:
    decision = evaluate_authorization(
        request(**request_overrides),
        scope(**scope_overrides),
        CATALOG,
    )

    assert not decision.allowed
    assert decision.internal_reason_code == reason
    if reason in {"AUTHZ_DEPENDENCY_UNAVAILABLE", "AUTHZ_POLICY_UNAVAILABLE"}:
        assert (decision.public_http_status, decision.public_error_code) == (
            503,
            "AUTHZ_POLICY_UNAVAILABLE",
        )
    else:
        assert (decision.public_http_status, decision.public_error_code) == (404, "AUTHZ_DENIED")


def test_missing_and_foreign_direct_id_have_identical_public_response() -> None:
    missing = evaluate_authorization(request(resource_exists=False), scope(), CATALOG)
    foreign = evaluate_authorization(request(class_id=_uuid(90)), scope(), CATALOG)

    assert (missing.public_http_status, missing.public_error_code) == (
        foreign.public_http_status,
        foreign.public_error_code,
    )
    assert missing.public_error_code == "AUTHZ_DENIED"


def test_ui_hidden_but_api_reachable_without_permission_is_denied() -> None:
    api_request = request(actor_permission_codes=frozenset())

    assert not evaluate_authorization(api_request, scope(), CATALOG).allowed


def test_legal_hold_does_not_grant_and_blocks_delete_request() -> None:
    delete_request = request(
        actor_permission_codes=frozenset({"evidence.delete_request"}),
        permission_code="evidence.delete_request",
        resource_type="evidence",
        action="delete_request",
        class_id=None,
        legal_hold_state=LegalHoldState.ACTIVE,
        purpose_code="retention_management",
        approval_status="approved",
    )
    school_scope = scope(
        dimension=ScopeDimension.SCHOOL,
        scope_ids=frozenset({_uuid(5)}),
    )

    decision = evaluate_authorization(delete_request, school_scope, CATALOG)

    assert not decision.allowed
    assert decision.internal_reason_code == "AUTHZ_LEGAL_HOLD_ACTIVE"
