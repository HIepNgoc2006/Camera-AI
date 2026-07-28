"""Minimized authorization audit intents with fail-closed recording."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import NAMESPACE_URL, UUID, uuid5

from camera_ai_audit import AuditIntent, AuditIntentRecorder, IntentResult
from camera_ai_audit.ports import AuditRecorderUnavailableError

from camera_ai_authorization.catalog import AuthorizationCatalog
from camera_ai_authorization.decision import evaluate_authorization
from camera_ai_authorization.models import (
    AuthorizationDecision,
    AuthorizationRequest,
    ScopeGrant,
)


class AuthorizationAuditUnavailableError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("AUTHZ_AUDIT_UNAVAILABLE")


def denial_audit_intent(
    request: AuthorizationRequest,
    decision: AuthorizationDecision,
) -> AuditIntent:
    if decision.allowed:
        raise ValueError("AUTHZ_REQUEST_INVALID")
    return AuditIntent(
        source_service=request.source_service,
        source_event_id=request.decision_id,
        action="AUTHORIZATION_DECISION_DENIED",
        resource_type="authorization_decision",
        resource_id=request.decision_id,
        request_id=request.request_id,
        correlation_id=request.correlation_id,
        result=IntentResult.DENIED,
        reason_code=decision.internal_reason_code,
        purpose_code=request.purpose_code,
        school_id=request.school_id,
        occurred_at=request.now,
        reference_ids=(
            ("actor_id", request.actor_id),
            ("protected_resource_id", request.resource_id),
        ),
        policy_versions=(("rbac_policy", request.policy_version or "missing"),),
    )


def permission_change_audit_intent(
    *,
    permission_id: UUID,
    actor_id: UUID,
    school_id: UUID,
    request_id: str,
    correlation_id: str,
    occurred_at: datetime,
) -> AuditIntent:
    return AuditIntent(
        source_service="identity-service",
        source_event_id=uuid5(
            NAMESPACE_URL,
            f"camera-ai:permission-change:{permission_id}:{request_id}",
        ),
        action="PERMISSION_CHANGED",
        resource_type="permission",
        resource_id=permission_id,
        request_id=request_id,
        correlation_id=correlation_id,
        result=IntentResult.SUCCESS,
        school_id=school_id,
        occurred_at=occurred_at,
        reference_ids=(("actor_id", actor_id), ("permission_id", permission_id)),
        policy_versions=(("rbac_policy", "rbac_policy_v1"),),
    )


@dataclass(frozen=True, slots=True)
class AuditedAuthorizationService:
    catalog: AuthorizationCatalog
    audit_recorder: AuditIntentRecorder

    def decide(
        self,
        request: AuthorizationRequest,
        scope: ScopeGrant,
    ) -> AuthorizationDecision:
        decision = evaluate_authorization(request, scope, self.catalog)
        if decision.allowed:
            return decision
        try:
            self.audit_recorder.record(denial_audit_intent(request, decision))
        except AuditRecorderUnavailableError:
            raise AuthorizationAuditUnavailableError from None
        except Exception:
            raise AuthorizationAuditUnavailableError from None
        return decision
