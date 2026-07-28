from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

from camera_ai_audit import AuditIntent
from camera_ai_crypto import DeterministicFakeKeyProvider, EncryptionService, LookupHasher
from notification_service.application.endpoints import EndpointApplicationService
from notification_service.domain.models import (
    EndpointKind,
    NotificationIntent,
    NotificationOutcome,
    ProtectedEndpoint,
    RecipientDelivery,
    TrustedSourceContext,
)
from notification_service.infrastructure.crypto import CryptoEndpointProtector

NOW = datetime(2026, 7, 28, tzinfo=UTC)


def _uuid(suffix: int) -> UUID:
    return UUID(f"00000000-0000-4000-8000-{suffix:012d}")


class EndpointRepository:
    endpoint: ProtectedEndpoint | None = None
    audit: AuditIntent | None = None
    revoked: bool = False

    def save_endpoint(
        self,
        endpoint: ProtectedEndpoint,
        *,
        audit_intent: AuditIntent,
        recorded_at: datetime,
    ) -> None:
        del recorded_at
        self.endpoint = endpoint
        self.audit = audit_intent

    def save_intent(
        self,
        *,
        intent: NotificationIntent,
        deliveries: Sequence[RecipientDelivery],
        audit_intents: Sequence[AuditIntent],
        content_fingerprint: bytes,
        denied_recipients: int,
    ) -> NotificationOutcome:
        del deliveries, audit_intents, content_fingerprint, denied_recipients
        return NotificationOutcome(intent.notification_id, 0, 0, False)

    def revoke_endpoint(
        self,
        *,
        endpoint_id: UUID,
        tenant_id: UUID,
        recipient_ref: UUID,
        occurred_at: datetime,
        audit_intent: AuditIntent,
    ) -> bool:
        del endpoint_id, tenant_id, recipient_ref, occurred_at
        self.revoked = True
        self.audit = audit_intent
        return True


def test_device_endpoint_is_encrypted_and_lookup_tokenized_before_repository() -> None:
    repository = EndpointRepository()
    protector = CryptoEndpointProtector(
        encryption=EncryptionService(key_provider=DeterministicFakeKeyProvider(seed=b"n" * 32)),
        lookup=LookupHasher(lookup_key=b"l" * 32),
    )
    service = EndpointApplicationService(
        repository,
        protector,
        clock=lambda: NOW,
        identifier_factory=lambda: _uuid(10),
    )
    synthetic_value = b"synthetic-device-endpoint"

    endpoint = service.register(
        tenant_id=_uuid(2),
        recipient_ref=_uuid(6),
        kind=EndpointKind.DEVICE_TOKEN,
        value=synthetic_value,
        context=TrustedSourceContext(
            source_service="identity-service",
            tenant_id=_uuid(2),
            school_id=_uuid(3),
            trusted_identity=True,
            permission_codes=frozenset({"service.notification.endpoint.manage"}),
            delegation_authorized=True,
            runtime_approvals_complete=True,
            policy_version="notification_privacy_policy_v1",
        ),
        request_id="req_synthetic_0001",
        correlation_id="cor_synthetic_0001",
    )

    assert endpoint.ciphertext.startswith(b"ENCV1")
    assert synthetic_value not in endpoint.ciphertext
    assert len(endpoint.lookup_digest) == 32
    assert repository.endpoint == endpoint
    assert repository.audit is not None
    assert repository.audit.action == "DEVICE_ENDPOINT_CHANGED"
    assert synthetic_value.decode() not in repr(endpoint)


def test_endpoint_revocation_is_owner_bound_and_audited() -> None:
    repository = EndpointRepository()
    service = EndpointApplicationService(
        repository,
        CryptoEndpointProtector(
            encryption=EncryptionService(key_provider=DeterministicFakeKeyProvider(seed=b"n" * 32)),
            lookup=LookupHasher(lookup_key=b"l" * 32),
        ),
        clock=lambda: NOW,
    )
    context = TrustedSourceContext(
        source_service="identity-service",
        tenant_id=_uuid(2),
        school_id=_uuid(3),
        trusted_identity=True,
        permission_codes=frozenset({"service.notification.endpoint.manage"}),
        delegation_authorized=True,
        runtime_approvals_complete=True,
        policy_version="notification_privacy_policy_v1",
    )

    service.revoke(
        endpoint_id=_uuid(10),
        tenant_id=_uuid(2),
        recipient_ref=_uuid(6),
        context=context,
        request_id="req_synthetic_0001",
        correlation_id="cor_synthetic_0001",
    )

    assert repository.revoked
    assert repository.audit is not None
    assert repository.audit.action == "DEVICE_ENDPOINT_REVOKED"
