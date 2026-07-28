"""Ports for authorization, persistence, endpoint protection and telemetry."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Protocol
from uuid import UUID

from camera_ai_audit import AuditIntent

from notification_service.domain.errors import NotificationError
from notification_service.domain.models import (
    Channel,
    DeliveryAttempt,
    DeliveryState,
    DeliveryWorkItem,
    NotificationCommand,
    NotificationIntent,
    NotificationOutcome,
    ProtectedEndpoint,
    RecipientAuthorization,
    RecipientDelivery,
)


class AuthorizationBatchEvaluator(Protocol):
    def evaluate(
        self,
        command: NotificationCommand,
    ) -> Mapping[tuple[UUID, Channel], RecipientAuthorization]:
        """Return fresh per-recipient/channel authorization; never cache a positive decision."""


class NotificationRepository(Protocol):
    def save_intent(
        self,
        *,
        intent: NotificationIntent,
        deliveries: Sequence[RecipientDelivery],
        audit_intents: Sequence[AuditIntent],
        content_fingerprint: bytes,
        denied_recipients: int,
    ) -> NotificationOutcome:
        """Persist the intent, deliveries and audit outbox atomically or return an identical retry."""


class EndpointRepository(Protocol):
    def save_endpoint(
        self,
        endpoint: ProtectedEndpoint,
        *,
        audit_intent: AuditIntent,
        recorded_at: datetime,
    ) -> None:
        """Persist a protected endpoint and minimized audit atomically."""

    def revoke_endpoint(
        self,
        *,
        endpoint_id: UUID,
        tenant_id: UUID,
        recipient_ref: UUID,
        occurred_at: datetime,
        audit_intent: AuditIntent,
    ) -> bool:
        """Owner-bound endpoint revocation that also stops matching remote-channel work."""


class DeliveryLifecycleRepository(Protocol):
    def load_delivery(self, delivery_id: UUID) -> DeliveryWorkItem | None:
        """Load only this service's aggregate; never join another service schema."""

    def load_notification(self, notification_id: UUID) -> NotificationIntent | None:
        """Load an intent for source-authorized cancellation."""

    def append_audit(self, audit_intent: AuditIntent, *, recorded_at: datetime) -> None:
        """Idempotently enqueue a minimized audit record."""

    def record_attempt(
        self,
        *,
        work_item: DeliveryWorkItem,
        attempt: DeliveryAttempt,
        next_state: DeliveryState,
        audit_intent: AuditIntent,
    ) -> bool:
        """Atomically append an attempt/audit and transition an unfinished delivery."""

    def cancel_notification(
        self,
        *,
        notification_id: UUID,
        trigger_code: str,
        owner_service: str,
        request_id: str,
        occurred_at: datetime,
        audit_intent: AuditIntent,
    ) -> int:
        """Idempotently stop pending/retry/dead-letter work and append cancellation/audit."""


class EndpointProtector(Protocol):
    def protect(
        self,
        *,
        endpoint_id: UUID,
        tenant_id: UUID,
        recipient_ref: UUID,
        kind: str,
        value: str | bytes,
    ) -> tuple[bytes, bytes]:
        """Return ENCV1 ciphertext and LOOKUP-V1 digest."""


class MetricsSink(Protocol):
    def increment(self, metric: str, *, outcome: str) -> None: ...

    def observe(self, metric: str, *, seconds: float) -> None: ...

    def set_gauge(self, metric: str, *, value: float) -> None: ...


class NullMetricsSink:
    def increment(self, metric: str, *, outcome: str) -> None:
        del metric, outcome

    def observe(self, metric: str, *, seconds: float) -> None:
        del metric, seconds

    def set_gauge(self, metric: str, *, value: float) -> None:
        del metric, value


class UnavailableAuthorizationBatchEvaluator:
    def evaluate(
        self, command: NotificationCommand
    ) -> Mapping[tuple[UUID, Channel], RecipientAuthorization]:
        del command
        raise NotificationError("NOTIFICATION_DEPENDENCY_UNAVAILABLE")


class UnavailableEndpointProtector:
    def protect(
        self,
        *,
        endpoint_id: UUID,
        tenant_id: UUID,
        recipient_ref: UUID,
        kind: str,
        value: str | bytes,
    ) -> tuple[bytes, bytes]:
        del endpoint_id, tenant_id, recipient_ref, kind, value
        raise NotificationError("NOTIFICATION_DEPENDENCY_UNAVAILABLE")
