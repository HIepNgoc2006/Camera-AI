from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from camera_ai_audit import AuditIntent
from notification_service.application.service import NotificationApplicationService
from notification_service.domain.models import (
    Channel,
    ConsentDecision,
    NotificationCommand,
    NotificationIntent,
    NotificationOutcome,
    ProtectedEndpoint,
    RecipientAuthorization,
    RecipientDelivery,
    TrustedSourceContext,
)

NOW = datetime(2026, 7, 28, tzinfo=UTC)


def _uuid(suffix: int) -> UUID:
    return UUID(f"00000000-0000-4000-8000-{suffix:012d}")


def payload() -> dict[str, object]:
    return {
        "schema_version": 1,
        "source_event_id": _uuid(1),
        "idempotency_key": "ntf_synthetic_000001",
        "tenant_id": _uuid(2),
        "school_id": _uuid(3),
        "subject_ref": _uuid(4),
        "resource_ref": _uuid(5),
        "content_class": "attendance_update",
        "template_code": "notification.attendance.generic",
        "template_version": 1,
        "source_state": "confirmed",
        "source_expires_at": NOW + timedelta(hours=2),
        "notification_expires_at": NOW + timedelta(hours=1),
        "recipient_refs": (_uuid(6),),
        "channels": ("in_app", "push", "email"),
        "request_id": "req_synthetic_0001",
        "correlation_id": "cor_synthetic_0001",
    }


def source_context() -> TrustedSourceContext:
    return TrustedSourceContext(
        source_service="attendance-service",
        tenant_id=_uuid(2),
        school_id=_uuid(3),
        trusted_identity=True,
        permission_codes=frozenset({"service.notification.request"}),
        delegation_authorized=True,
        runtime_approvals_complete=True,
        policy_version="notification_privacy_policy_v1",
    )


def authorization(*, consent: ConsentDecision = ConsentDecision.ALLOWED) -> RecipientAuthorization:
    return RecipientAuthorization(
        recipient_ref=_uuid(6),
        tenant_id=_uuid(2),
        school_id=_uuid(3),
        recipient_role="parent_guardian",
        relationship_code="active_linked_child",
        permission_code="notification.attendance.receive",
        purpose_code="attendance_notification",
        recipient_active=True,
        relationship_current=True,
        permission_current=True,
        purpose_active=True,
        consent_decision=consent,
        source_current=True,
        endpoint_active=True,
        endpoint_verified=True,
        endpoint_owned=True,
        channel_preference_enabled=True,
        dependencies_available=True,
    )


class FakeAuthorizer:
    def __init__(self, value: RecipientAuthorization) -> None:
        self.value = value
        self.calls = 0

    def evaluate(
        self, command: NotificationCommand
    ) -> Mapping[tuple[UUID, Channel], RecipientAuthorization]:
        self.calls += 1
        return {
            (recipient, channel): self.value
            for recipient in command.recipient_refs
            for channel in command.channels
        }


class FakeRepository:
    def __init__(self) -> None:
        self.intent: NotificationIntent | None = None
        self.deliveries: list[RecipientDelivery] = []
        self.audit: list[AuditIntent] = []
        self.fingerprint: bytes | None = None

    def save_intent(
        self,
        *,
        intent: NotificationIntent,
        deliveries: Sequence[RecipientDelivery],
        audit_intents: Sequence[AuditIntent],
        content_fingerprint: bytes,
        denied_recipients: int,
    ) -> NotificationOutcome:
        duplicate = self.fingerprint is not None
        self.intent = intent
        self.deliveries = list(deliveries)
        self.audit = list(audit_intents)
        self.fingerprint = content_fingerprint
        return NotificationOutcome(
            notification_id=intent.notification_id,
            queued_deliveries=len(deliveries),
            denied_recipients=denied_recipients,
            duplicate=duplicate,
        )

    def save_endpoint(
        self,
        endpoint: ProtectedEndpoint,
        *,
        audit_intent: AuditIntent,
        recorded_at: datetime,
    ) -> None:
        del endpoint, audit_intent, recorded_at


class FakeMetrics:
    def __init__(self) -> None:
        self.counters: list[tuple[str, str]] = []
        self.observations: list[tuple[str, float]] = []

    def increment(self, metric: str, *, outcome: str) -> None:
        self.counters.append((metric, outcome))

    def observe(self, metric: str, *, seconds: float) -> None:
        self.observations.append((metric, seconds))

    def set_gauge(self, metric: str, *, value: float) -> None:
        del metric, value


def test_accept_intent_queues_all_channels_with_minimized_audit_and_content() -> None:
    repository = FakeRepository()
    authorizer = FakeAuthorizer(authorization())
    metrics = FakeMetrics()
    service = NotificationApplicationService(
        repository,
        authorizer,
        metrics=metrics,
        clock=lambda: NOW,
        timer=iter((1.0, 1.025)).__next__,
    )

    result = service.accept_intent(payload(), source_context())

    assert result.queued_deliveries == 3
    assert result.denied_recipients == 0
    assert authorizer.calls == 1
    assert {delivery.channel for delivery in repository.deliveries} == set(Channel)
    serialized = repr(
        [dict(delivery.content.fields) for delivery in repository.deliveries]
        + [intent.publisher_payload() for intent in repository.audit]
    ).casefold()
    for forbidden in (
        "student_name",
        "device_token",
        "endpoint_ciphertext",
        "signed_url",
        "message_text",
        "image_base64",
    ):
        assert forbidden not in serialized
    assert metrics.observations[0][0] == "notification_reauthorization_seconds"
    assert metrics.observations[0][1] == pytest.approx(0.025)
    assert ("notification_dispatch_total", "queued") in metrics.counters


def test_withdrawn_consent_denies_every_channel_and_audits_without_delivery() -> None:
    repository = FakeRepository()
    service = NotificationApplicationService(
        repository,
        FakeAuthorizer(authorization(consent=ConsentDecision.BLOCKED)),
        clock=lambda: NOW,
    )

    result = service.accept_intent(payload(), source_context())

    assert result.queued_deliveries == 0
    assert result.denied_recipients == 3
    assert len(repository.audit) == 3
    assert {audit.action for audit in repository.audit} == {"NOTIFICATION_DISPATCH_DENIED"}
    assert {audit.reason_code for audit in repository.audit} == {"NOTIFICATION_CONSENT_DENIED"}


def test_identical_retry_returns_duplicate_without_second_authorization_bypass() -> None:
    repository = FakeRepository()
    authorizer = FakeAuthorizer(authorization())
    service = NotificationApplicationService(repository, authorizer, clock=lambda: NOW)

    assert not service.accept_intent(payload(), source_context()).duplicate
    assert service.accept_intent(payload(), source_context()).duplicate
    assert authorizer.calls == 2
