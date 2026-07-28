from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from camera_ai_audit import AuditIntent
from notification_service.application.lifecycle import DeliveryApplicationService
from notification_service.domain.errors import NotificationError
from notification_service.domain.models import (
    Channel,
    ConsentDecision,
    ContentClass,
    DeliveryAttempt,
    DeliveryState,
    DeliveryWorkItem,
    NotificationCommand,
    NotificationIntent,
    NotificationOutcome,
    ProtectedEndpoint,
    ProviderResultCategory,
    RecipientAuthorization,
    RecipientDelivery,
    RenderedContent,
    TrustedSourceContext,
)

NOW = datetime(2026, 7, 28, tzinfo=UTC)


def _uuid(suffix: int) -> UUID:
    return UUID(f"00000000-0000-4000-8000-{suffix:012d}")


def work_item(*, state: DeliveryState = DeliveryState.PENDING) -> DeliveryWorkItem:
    command = NotificationCommand(
        source_event_id=_uuid(1),
        idempotency_key="ntf_synthetic_000001",
        tenant_id=_uuid(2),
        school_id=_uuid(3),
        subject_ref=_uuid(4),
        resource_ref=_uuid(5),
        content_class=ContentClass.ATTENDANCE_UPDATE,
        template_code="notification.attendance.generic",
        template_version=1,
        source_state="confirmed",
        source_expires_at=NOW + timedelta(hours=2),
        notification_expires_at=NOW + timedelta(hours=1),
        recipient_refs=(_uuid(6),),
        channels=(Channel.IN_APP,),
        request_id="req_synthetic_0001",
        correlation_id="cor_synthetic_0001",
    )
    intent = NotificationIntent(
        notification_id=_uuid(7),
        command=command,
        purpose_code="attendance_notification",
        policy_version="notification_privacy_policy_v1",
        created_at=NOW,
    )
    delivery = RecipientDelivery(
        delivery_id=_uuid(8),
        notification_id=intent.notification_id,
        recipient_ref=_uuid(6),
        channel=Channel.IN_APP,
        content=RenderedContent(
            Channel.IN_APP,
            {
                "template_code": command.template_code,
                "opaque_notification_ref": "synthetic",
            },
        ),
        state=state,
        attempt_count=0,
        next_attempt_at=None,
        expires_at=NOW + timedelta(hours=1),
        created_at=NOW,
    )
    return DeliveryWorkItem(intent=intent, delivery=delivery)


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
    def __init__(self, decision: RecipientAuthorization) -> None:
        self.decision = decision
        self.calls = 0

    def evaluate(
        self, command: NotificationCommand
    ) -> Mapping[tuple[UUID, Channel], RecipientAuthorization]:
        self.calls += 1
        return {(command.recipient_refs[0], command.channels[0]): self.decision}


class FakeRepository:
    def __init__(self, item: DeliveryWorkItem) -> None:
        self.item = item
        self.attempts: list[DeliveryAttempt] = []
        self.audits: list[AuditIntent] = []
        self.cancelled = False

    def load_delivery(self, delivery_id: UUID) -> DeliveryWorkItem | None:
        return self.item if delivery_id == self.item.delivery.delivery_id else None

    def load_notification(self, notification_id: UUID) -> NotificationIntent | None:
        return self.item.intent if notification_id == self.item.intent.notification_id else None

    def append_audit(self, audit_intent: AuditIntent, *, recorded_at: datetime) -> None:
        del recorded_at
        self.audits.append(audit_intent)

    def record_attempt(
        self,
        *,
        work_item: DeliveryWorkItem,
        attempt: DeliveryAttempt,
        next_state: DeliveryState,
        audit_intent: AuditIntent,
    ) -> bool:
        if self.item.delivery.state not in {
            DeliveryState.PENDING,
            DeliveryState.RETRY_SCHEDULED,
            DeliveryState.DEAD_LETTERED,
        }:
            return False
        self.attempts.append(attempt)
        self.audits.append(audit_intent)
        self.item = replace(
            work_item,
            delivery=replace(
                work_item.delivery,
                state=next_state,
                attempt_count=attempt.attempt_number,
                next_attempt_at=attempt.next_attempt_at,
            ),
        )
        return True

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
        del notification_id, trigger_code, owner_service, request_id, occurred_at
        if self.cancelled:
            return 0
        self.cancelled = True
        self.audits.append(audit_intent)
        self.item = replace(
            self.item,
            delivery=replace(self.item.delivery, state=DeliveryState.CANCELLED),
        )
        return 1

    def save_intent(
        self,
        *,
        intent: NotificationIntent,
        deliveries: Sequence[RecipientDelivery],
        audit_intents: Sequence[AuditIntent],
        content_fingerprint: bytes,
        denied_recipients: int,
    ) -> NotificationOutcome:
        raise AssertionError(
            (intent, deliveries, audit_intents, content_fingerprint, denied_recipients)
        )

    def save_endpoint(
        self,
        endpoint: ProtectedEndpoint,
        *,
        audit_intent: AuditIntent,
        recorded_at: datetime,
    ) -> None:
        raise AssertionError((endpoint, audit_intent, recorded_at))

    def revoke_endpoint(
        self,
        *,
        endpoint_id: UUID,
        tenant_id: UUID,
        recipient_ref: UUID,
        occurred_at: datetime,
        audit_intent: AuditIntent,
    ) -> bool:
        raise AssertionError((endpoint_id, tenant_id, recipient_ref, occurred_at, audit_intent))


def test_retry_reauthorizes_and_emits_no_content_in_dead_letter_envelope() -> None:
    repository = FakeRepository(work_item())
    authorizer = FakeAuthorizer(authorization())
    service = DeliveryApplicationService(
        repository,
        authorizer,
        clock=lambda: NOW + timedelta(seconds=1),
    )

    assert (
        service.record_provider_result(
            delivery_id=_uuid(8),
            category=ProviderResultCategory.TEMPORARY_UNAVAILABLE,
            retry_backlog=4_999,
        )
        is None
    )
    assert authorizer.calls == 1
    assert repository.item.delivery.state is DeliveryState.RETRY_SCHEDULED

    repository.item = replace(
        repository.item,
        delivery=replace(
            repository.item.delivery,
            state=DeliveryState.RETRY_SCHEDULED,
            attempt_count=4,
            next_attempt_at=NOW + timedelta(seconds=2),
        ),
    )
    envelope = service.record_provider_result(
        delivery_id=_uuid(8),
        category=ProviderResultCategory.RATE_LIMITED,
        retry_backlog=4_999,
    )
    assert envelope is not None
    assert set(envelope.__dataclass_fields__) == {
        "delivery_id",
        "notification_id",
        "attempt_count",
        "reason_category",
        "occurred_at",
    }
    assert repository.item.delivery.state is DeliveryState.DEAD_LETTERED
    assert authorizer.calls == 2


def test_retry_storm_bound_fails_closed_before_recording_attempt() -> None:
    repository = FakeRepository(work_item())
    service = DeliveryApplicationService(
        repository,
        FakeAuthorizer(authorization()),
        clock=lambda: NOW + timedelta(seconds=1),
    )
    with pytest.raises(NotificationError, match="NOTIFICATION_RETRY_DENIED"):
        service.record_provider_result(
            delivery_id=_uuid(8),
            category=ProviderResultCategory.RATE_LIMITED,
            retry_backlog=5_000,
        )
    assert repository.attempts == []


def test_retry_withdrawn_consent_audits_and_cancels_stale_work() -> None:
    repository = FakeRepository(work_item())
    service = DeliveryApplicationService(
        repository,
        FakeAuthorizer(authorization(consent=ConsentDecision.BLOCKED)),
        clock=lambda: NOW + timedelta(seconds=1),
    )

    with pytest.raises(NotificationError, match="NOTIFICATION_CONSENT_DENIED"):
        service.record_provider_result(
            delivery_id=_uuid(8),
            category=ProviderResultCategory.ACCEPTED,
            retry_backlog=0,
        )

    assert repository.item.delivery.state is DeliveryState.CANCELLED
    assert {audit.action for audit in repository.audits} == {
        "NOTIFICATION_DISPATCH_DENIED",
        "NOTIFICATION_CANCELLED",
    }


def test_open_rechecks_current_consent_and_conceals_stale_record() -> None:
    repository = FakeRepository(work_item())
    allowed = DeliveryApplicationService(
        repository,
        FakeAuthorizer(authorization()),
        clock=lambda: NOW + timedelta(seconds=1),
    )
    assert allowed.authorize_open(
        delivery_id=_uuid(8), recipient_ref=_uuid(6)
    ).resource_ref == _uuid(5)

    denied = DeliveryApplicationService(
        repository,
        FakeAuthorizer(authorization(consent=ConsentDecision.BLOCKED)),
        clock=lambda: NOW + timedelta(seconds=1),
    )
    with pytest.raises(NotificationError, match="NOTIFICATION_NOT_AVAILABLE"):
        denied.authorize_open(delivery_id=_uuid(8), recipient_ref=_uuid(6))
    assert repository.audits[-1].action == "NOTIFICATION_OPEN_DENIED"


def test_source_cancellation_is_idempotent_and_stops_pending_work() -> None:
    repository = FakeRepository(work_item())
    service = DeliveryApplicationService(
        repository,
        FakeAuthorizer(authorization()),
        clock=lambda: NOW + timedelta(seconds=1),
    )
    context = TrustedSourceContext(
        source_service="attendance-service",
        tenant_id=_uuid(2),
        school_id=_uuid(3),
        trusted_identity=True,
        permission_codes=frozenset({"service.notification.request"}),
        delegation_authorized=True,
        runtime_approvals_complete=True,
        policy_version="notification_privacy_policy_v1",
    )

    assert (
        service.cancel(
            notification_id=_uuid(7),
            trigger_code="consent_withdrawn",
            context=context,
        )
        == 1
    )
    assert (
        service.cancel(
            notification_id=_uuid(7),
            trigger_code="consent_withdrawn",
            context=context,
        )
        == 0
    )
    assert repository.item.delivery.state is DeliveryState.CANCELLED
