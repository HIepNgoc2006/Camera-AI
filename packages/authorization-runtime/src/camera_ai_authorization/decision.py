"""Pure fail-closed RBAC/ABAC decision point."""

from __future__ import annotations

from camera_ai_authorization.catalog import (
    AuthorizationCatalog,
    AuthorizationCatalogError,
    PermissionRule,
)
from camera_ai_authorization.models import (
    AuthorizationDecision,
    AuthorizationRequest,
    ConsentState,
    LegalHoldState,
    ResourceState,
    RetentionState,
    ScopeDimension,
    ScopeGrant,
)


def _allow(request: AuthorizationRequest) -> AuthorizationDecision:
    assert request.policy_version is not None
    return AuthorizationDecision(
        allowed=True,
        internal_reason_code="AUTHZ_ALLOWED",
        public_error_code="AUTHZ_ALLOWED",
        public_http_status=0,
        required_permission_code=request.permission_code,
        policy_version=request.policy_version,
    )


def _deny(
    request: AuthorizationRequest,
    reason_code: str,
    *,
    unavailable: bool = False,
) -> AuthorizationDecision:
    return AuthorizationDecision(
        allowed=False,
        internal_reason_code=reason_code,
        public_error_code="AUTHZ_POLICY_UNAVAILABLE" if unavailable else "AUTHZ_DENIED",
        public_http_status=503 if unavailable else 404,
        required_permission_code=request.permission_code,
        policy_version=request.policy_version or "missing",
    )


def _scope_value(request: AuthorizationRequest, dimension: ScopeDimension) -> object:
    return {
        ScopeDimension.SCHOOL: request.school_id,
        ScopeDimension.CLASS: request.class_id,
        ScopeDimension.GUARDIAN_SUBJECT: request.guardian_subject_ref,
        ScopeDimension.KITCHEN_ZONE: request.kitchen_zone_id,
    }[dimension]


def _check_required_attributes(
    request: AuthorizationRequest,
    rule: PermissionRule,
) -> str | None:
    required = rule.required_attributes
    if "purpose_code" in required and request.purpose_code not in rule.allowed_purpose_codes:
        return "AUTHZ_PURPOSE_DENIED"
    if "consent_state" in required:
        if request.consent_state is ConsentState.UNAVAILABLE:
            return "AUTHZ_CONSENT_UNAVAILABLE"
        if (
            rule.consent_requirement == "required"
            and request.consent_state is not ConsentState.ALLOWED
        ):
            return "AUTHZ_CONSENT_DENIED"
        if rule.consent_requirement == "not_required" and request.consent_state not in {
            ConsentState.NOT_REQUIRED,
            ConsentState.ALLOWED,
        }:
            return "AUTHZ_CONSENT_DENIED"
        if rule.consent_requirement == "contextual" and request.consent_state not in {
            ConsentState.ALLOWED,
            ConsentState.NOT_REQUIRED,
        }:
            return "AUTHZ_CONSENT_DENIED"
    if "retention_state" in required and request.retention_state is not RetentionState.ACTIVE:
        return "AUTHZ_RETENTION_DENIED"
    if "legal_hold_state" in required:
        if request.legal_hold_state is LegalHoldState.UNAVAILABLE:
            return "AUTHZ_LEGAL_HOLD_UNAVAILABLE"
        if rule.deny_when_legal_hold_active and request.legal_hold_state is LegalHoldState.ACTIVE:
            return "AUTHZ_LEGAL_HOLD_ACTIVE"
    if "resource_state" in required and request.resource_state is not ResourceState.AVAILABLE:
        return "AUTHZ_RESOURCE_UNAVAILABLE"
    if "sensitivity" in required and request.sensitivity not in {"high", "critical"}:
        return "AUTHZ_SENSITIVITY_DENIED"
    if (
        "approval_status" in required
        and request.action in {"export", "hold_approve"}
        and request.approval_status != "approved"
    ):
        return "AUTHZ_APPROVAL_REQUIRED"
    return None


def evaluate_authorization(
    request: AuthorizationRequest,
    scope: ScopeGrant,
    catalog: AuthorizationCatalog,
) -> AuthorizationDecision:
    """Evaluate one current request; positive decisions must never be cached."""

    if request.policy_version != catalog.policy_version:
        return _deny(request, "AUTHZ_POLICY_UNAVAILABLE", unavailable=True)
    if not request.dependencies_available:
        return _deny(request, "AUTHZ_DEPENDENCY_UNAVAILABLE", unavailable=True)
    try:
        rule = catalog.permission(request.permission_code)
    except AuthorizationCatalogError:
        return _deny(request, "AUTHZ_POLICY_UNAVAILABLE", unavailable=True)
    if not request.actor_authenticated:
        return _deny(request, "AUTHZ_ACTOR_UNAUTHENTICATED")
    if not request.resource_exists:
        return _deny(request, "AUTHZ_NOT_FOUND")
    if rule.resource_type != request.resource_type or rule.action != request.action:
        return _deny(request, "AUTHZ_PERMISSION_DENIED")
    if request.permission_code not in request.actor_permission_codes:
        return _deny(request, "AUTHZ_PERMISSION_DENIED")
    if scope.tenant_id != request.tenant_id:
        return _deny(request, "AUTHZ_TENANT_SCOPE_DENIED")
    if request.school_id not in scope.school_ids:
        return _deny(request, "AUTHZ_SCHOOL_SCOPE_DENIED")
    if scope.dimension not in rule.scope_dimensions:
        return _deny(request, "AUTHZ_OBJECT_SCOPE_DENIED")
    scope_value = _scope_value(request, scope.dimension)
    if scope_value is None or scope_value not in scope.scope_ids:
        return _deny(request, "AUTHZ_OBJECT_SCOPE_DENIED")
    if not scope.is_current(request.now):
        return _deny(request, "AUTHZ_ASSIGNMENT_EXPIRED")
    missing_reason = _check_required_attributes(request, rule)
    if missing_reason is not None:
        return _deny(request, missing_reason)
    return _allow(request)
