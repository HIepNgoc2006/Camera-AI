"""Recipient endpoint registration through the ENCV1/LOOKUP-V1 boundary."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID, uuid4, uuid5

from camera_ai_audit import AuditIntent, IntentResult

from notification_service.application.ports import EndpointProtector, EndpointRepository
from notification_service.domain.errors import NotificationError
from notification_service.domain.models import (
    EndpointKind,
    EndpointState,
    ProtectedEndpoint,
    TrustedSourceContext,
)


class EndpointApplicationService:
    def __init__(
        self,
        repository: EndpointRepository,
        protector: EndpointProtector,
        *,
        clock: Callable[[], datetime] | None = None,
        identifier_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._repository = repository
        self._protector = protector
        self._clock = clock or (lambda: datetime.now(UTC))
        self._identifier_factory = identifier_factory

    def register(
        self,
        *,
        tenant_id: UUID,
        recipient_ref: UUID,
        kind: EndpointKind,
        value: str | bytes,
        context: TrustedSourceContext,
        request_id: str,
        correlation_id: str,
    ) -> ProtectedEndpoint:
        self._authorize_context(tenant_id, context)
        endpoint_id = self._identifier_factory()
        now = self._clock()
        ciphertext, lookup_digest = self._protector.protect(
            endpoint_id=endpoint_id,
            tenant_id=tenant_id,
            recipient_ref=recipient_ref,
            kind=kind.value,
            value=value,
        )
        endpoint = ProtectedEndpoint(
            endpoint_id=endpoint_id,
            tenant_id=tenant_id,
            recipient_ref=recipient_ref,
            kind=kind,
            ciphertext=ciphertext,
            lookup_digest=lookup_digest,
            state=EndpointState.ACTIVE,
            verified_at=now,
            created_at=now,
        )
        self._repository.save_endpoint(
            endpoint,
            audit_intent=self._audit(
                endpoint.endpoint_id,
                context=context,
                action="DEVICE_ENDPOINT_CHANGED",
                request_id=request_id,
                correlation_id=correlation_id,
                now=now,
            ),
            recorded_at=now,
        )
        return endpoint

    def revoke(
        self,
        *,
        endpoint_id: UUID,
        tenant_id: UUID,
        recipient_ref: UUID,
        context: TrustedSourceContext,
        request_id: str,
        correlation_id: str,
    ) -> None:
        self._authorize_context(tenant_id, context)
        now = self._clock()
        revoked = self._repository.revoke_endpoint(
            endpoint_id=endpoint_id,
            tenant_id=tenant_id,
            recipient_ref=recipient_ref,
            occurred_at=now,
            audit_intent=self._audit(
                endpoint_id,
                context=context,
                action="DEVICE_ENDPOINT_REVOKED",
                request_id=request_id,
                correlation_id=correlation_id,
                now=now,
            ),
        )
        if not revoked:
            raise NotificationError("NOTIFICATION_NOT_AVAILABLE")

    @staticmethod
    def _authorize_context(tenant_id: UUID, context: TrustedSourceContext) -> None:
        if (
            not context.trusted_identity
            or context.tenant_id != tenant_id
            or "service.notification.endpoint.manage" not in context.permission_codes
            or not context.delegation_authorized
            or not context.runtime_approvals_complete
            or context.policy_version != "notification_privacy_policy_v1"
        ):
            raise NotificationError("NOTIFICATION_ENDPOINT_DENIED")

    @staticmethod
    def _audit(
        endpoint_id: UUID,
        *,
        context: TrustedSourceContext,
        action: str,
        request_id: str,
        correlation_id: str,
        now: datetime,
    ) -> AuditIntent:
        return AuditIntent(
            source_service="notification-service",
            source_event_id=uuid5(endpoint_id, action.casefold()),
            action=action,
            resource_type="device_endpoint",
            resource_id=endpoint_id,
            request_id=request_id,
            correlation_id=correlation_id,
            school_id=context.school_id,
            result=IntentResult.SUCCESS,
            occurred_at=now,
            reference_ids=(("endpoint_id", endpoint_id),),
            policy_versions=(("notification_policy", context.policy_version),),
        )
