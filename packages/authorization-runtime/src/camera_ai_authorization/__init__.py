"""Public authorization runtime API."""

from camera_ai_authorization.audit import (
    AuditedAuthorizationService,
    AuthorizationAuditUnavailableError,
    denial_audit_intent,
    permission_change_audit_intent,
)
from camera_ai_authorization.catalog import (
    POLICY_VERSION,
    AuthorizationCatalog,
    AuthorizationCatalogError,
    OperationRule,
    PermissionRule,
    load_catalog,
    validate_catalog,
)
from camera_ai_authorization.decision import evaluate_authorization
from camera_ai_authorization.filters import RowScopeColumns, build_row_scope_filter
from camera_ai_authorization.models import (
    AuthorizationDecision,
    AuthorizationInputError,
    AuthorizationRequest,
    ConsentState,
    LegalHoldState,
    ResourceState,
    RetentionState,
    ScopeDimension,
    ScopeGrant,
)

__all__ = [
    "POLICY_VERSION",
    "AuditedAuthorizationService",
    "AuthorizationAuditUnavailableError",
    "AuthorizationCatalog",
    "AuthorizationCatalogError",
    "AuthorizationDecision",
    "AuthorizationInputError",
    "AuthorizationRequest",
    "ConsentState",
    "LegalHoldState",
    "OperationRule",
    "PermissionRule",
    "ResourceState",
    "RetentionState",
    "RowScopeColumns",
    "ScopeDimension",
    "ScopeGrant",
    "build_row_scope_filter",
    "denial_audit_intent",
    "evaluate_authorization",
    "load_catalog",
    "permission_change_audit_intent",
    "validate_catalog",
]
