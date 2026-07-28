"""Adapter from Evidence Storage context to the versioned authorization runtime."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import NAMESPACE_URL, UUID, uuid5

from camera_ai_audit import AuditIntentRecorder
from camera_ai_authorization import (
    AuditedAuthorizationService,
    AuthorizationCatalog,
    AuthorizationRequest,
    ResourceState,
    RetentionState,
    ScopeGrant,
)
from camera_ai_authorization import (
    ConsentState as AuthorizationConsentState,
)
from camera_ai_authorization import (
    LegalHoldState as AuthorizationLegalHoldState,
)

from evidence_service.domain.models import (
    AccessAction,
    ConsentState,
    EvidenceObject,
    RequestContext,
)
from evidence_service.domain.policies import permission_for


@dataclass(frozen=True, slots=True)
class ResolvedScope:
    scope: ScopeGrant
    class_id: UUID | None = None
    guardian_subject_ref: UUID | None = None
    kitchen_zone_id: UUID | None = None


class EvidenceScopeResolver(Protocol):
    def resolve(self, context: RequestContext, evidence: EvidenceObject) -> ResolvedScope: ...


@dataclass(frozen=True, slots=True)
class AuthorizationRuntimeAdapter:
    catalog: AuthorizationCatalog
    audit_recorder: AuditIntentRecorder
    scope_resolver: EvidenceScopeResolver

    def authorize(
        self,
        *,
        context: RequestContext,
        evidence: EvidenceObject,
        action: AccessAction,
        consent_state: ConsentState,
        approval_status: str,
    ) -> bool:
        resolved = self.scope_resolver.resolve(context, evidence)
        request = AuthorizationRequest(
            decision_id=uuid5(
                NAMESPACE_URL,
                f"camera-ai:evidence-authz:{context.request_id}:{evidence.evidence_id}:{action.value}",
            ),
            request_id=context.request_id,
            correlation_id=context.correlation_id,
            source_service="evidence-storage-service",
            actor_id=context.actor_id,
            actor_authenticated=context.actor_authenticated,
            actor_permission_codes=context.actor_permission_codes,
            permission_code=permission_for(action),
            resource_type="evidence",
            action=action.value,
            resource_id=evidence.evidence_id,
            resource_exists=True,
            policy_version=self.catalog.policy_version,
            tenant_id=evidence.tenant_id,
            school_id=evidence.school_id,
            class_id=resolved.class_id,
            guardian_subject_ref=resolved.guardian_subject_ref,
            kitchen_zone_id=resolved.kitchen_zone_id,
            purpose_code=context.purpose_code,
            consent_state=AuthorizationConsentState(consent_state.value),
            retention_state=(
                RetentionState.ACTIVE
                if evidence.retention_expires_at > evidence.updated_at
                else RetentionState.EXPIRED
            ),
            legal_hold_state=AuthorizationLegalHoldState(evidence.legal_hold_state.value),
            resource_state=ResourceState(evidence.state.value),
            sensitivity=evidence.sensitivity,
            approval_status=approval_status,
            dependencies_available=True,
            now=datetime.now(UTC),
        )
        return (
            AuditedAuthorizationService(self.catalog, self.audit_recorder)
            .decide(request, resolved.scope)
            .allowed
        )


class UnavailableEvidenceAuthorization:
    def authorize(
        self,
        *,
        context: RequestContext,
        evidence: EvidenceObject,
        action: AccessAction,
        consent_state: ConsentState,
        approval_status: str,
    ) -> bool:
        del context, evidence, action, consent_state, approval_status
        return False
