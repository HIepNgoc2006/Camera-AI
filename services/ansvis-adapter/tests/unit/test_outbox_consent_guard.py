"""Dispatch-path consent guard: terminal refusal, audit-before-persist, batch isolation."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from ansvis_adapter.application.outbox import DispatchOutboxMessage, DrainOutboxBatch
from ansvis_adapter.domain.ingestion import DispatchOutcome, PendingOutboxMessage

NOW = datetime(2026, 7, 27, 9, 0, tzinfo=UTC)
TOKEN = UUID("00000000-0000-4000-8000-000000000901")


def biometric_message(index: int = 0, *, status: str | None = None) -> PendingOutboxMessage:
    payload: dict[str, object] = {
        "schema_version": "normalized_outbox_v1",
        "event_type": "attendance.face.observed",
        "index": index,
    }
    if status is not None:
        payload["consent_gate_status"] = status
    return PendingOutboxMessage(
        outbox_message_id=UUID(f"00000000-0000-4000-8000-0000000009{index:02d}"),
        normalized_event_id=uuid4(),
        claim_token=TOKEN,
        topic="camera_ai.events.attendance_face_observed.v1",
        contract_version="normalized_outbox_v1",
        payload=payload,
        attempt_count=0,
        recorded_at=NOW - timedelta(seconds=10),
    )


def health_message(index: int) -> PendingOutboxMessage:
    return PendingOutboxMessage(
        outbox_message_id=UUID(f"00000000-0000-4000-8000-0000000009{index:02d}"),
        normalized_event_id=uuid4(),
        claim_token=TOKEN,
        topic="camera_ai.events.camera_health_changed.v1",
        contract_version="normalized_outbox_v1",
        payload={
            "schema_version": "normalized_outbox_v1",
            "event_type": "camera.health.changed",
            "index": index,
        },
        attempt_count=0,
        recorded_at=NOW - timedelta(seconds=10),
    )


class GuardRepository:
    def __init__(self, messages: Sequence[PendingOutboxMessage]) -> None:
        self.messages = tuple(messages)
        self.refused: list[UUID] = []
        self.acks: list[tuple[UUID, UUID]] = []
        self.failures: list[UUID] = []

    def claim_next(self, *, now: datetime) -> PendingOutboxMessage | None:
        del now
        return self.messages[0] if self.messages else None

    def claim_batch(self, *, now: datetime, limit: int) -> tuple[PendingOutboxMessage, ...]:
        del now
        return self.messages[:limit]

    def mark_published(
        self, message_id: UUID, claim_token: UUID, *, published_at: datetime
    ) -> None:
        del published_at
        self.acks.append((message_id, claim_token))

    def mark_published_batch(
        self,
        confirmations: Sequence[tuple[UUID, UUID]],
        *,
        published_at: datetime,
    ) -> None:
        del published_at
        self.acks.extend(confirmations)

    def record_failure(
        self,
        message: PendingOutboxMessage,
        *,
        failed_at: datetime,
        next_retry_at: datetime | None,
        error_code: str,
    ) -> bool:
        del failed_at, next_retry_at, error_code
        self.failures.append(message.outbox_message_id)
        return False

    def replay_failed(
        self,
        message_id: UUID,
        *,
        actor_id: UUID,
        reason_code: str,
        authorized_at: datetime,
    ) -> None:
        raise AssertionError("replay is not exercised by the guard tests")

    def refuse_consent_blocked(
        self,
        message: PendingOutboxMessage,
        *,
        refused_at: datetime,
    ) -> None:
        assert refused_at.tzinfo is not None
        self.refused.append(message.outbox_message_id)


class RecordingPublisher:
    def __init__(self) -> None:
        self.topics: list[str] = []

    def publish(self, *, topic: str, payload: object) -> None:
        del payload
        self.topics.append(topic)


class FakeMetrics:
    def __init__(self) -> None:
        self.values: list[tuple[str, str]] = []

    def increment(self, metric: str, *, outcome: str) -> None:
        self.values.append((metric, outcome))

    def observe(self, metric: str, *, seconds: float) -> None:
        self.values.append((metric, "observed"))

    def set_gauge(self, metric: str, *, value: float) -> None:
        self.values.append((metric, "gauge"))


@pytest.mark.parametrize("status", [None, "blocked", "not_evaluated"])
def test_single_dispatch_refuses_biometric_payload_without_allow(status: str | None) -> None:
    repository = GuardRepository([biometric_message(status=status)])
    publisher = RecordingPublisher()
    metrics = FakeMetrics()
    hook_calls: list[UUID] = []
    outcome = DispatchOutboxMessage(
        repository,
        publisher,
        metrics=metrics,
        now=lambda: NOW,
        jitter=lambda _: 0,
        on_consent_refused=lambda message: hook_calls.append(message.outbox_message_id),
    ).execute()

    assert outcome is DispatchOutcome.REFUSED
    assert publisher.topics == []
    assert repository.refused == [repository.messages[0].outbox_message_id]
    assert repository.failures == []
    assert hook_calls == repository.refused
    assert ("event_outbox_dispatch_total", "refused") in metrics.values


def test_single_dispatch_publishes_biometric_payload_with_allow() -> None:
    repository = GuardRepository([biometric_message(status="allowed")])
    publisher = RecordingPublisher()
    outcome = DispatchOutboxMessage(
        repository, publisher, now=lambda: NOW, jitter=lambda _: 0
    ).execute()
    assert outcome is DispatchOutcome.PUBLISHED
    assert publisher.topics == ["camera_ai.events.attendance_face_observed.v1"]
    assert repository.refused == []


def test_refusal_audit_hook_failure_aborts_before_any_persistence() -> None:
    repository = GuardRepository([biometric_message(status="blocked")])
    publisher = RecordingPublisher()

    def failing_hook(message: PendingOutboxMessage) -> None:
        raise RuntimeError("synthetic audit outage stays masked")

    with pytest.raises(RuntimeError):
        DispatchOutboxMessage(
            repository,
            publisher,
            now=lambda: NOW,
            jitter=lambda _: 0,
            on_consent_refused=failing_hook,
        ).execute()
    assert repository.refused == []
    assert publisher.topics == []


def test_batch_drain_refuses_only_unproven_messages_and_reconciles_counts() -> None:
    messages = [
        biometric_message(1, status="blocked"),
        health_message(2),
        biometric_message(3, status="allowed"),
        biometric_message(4),
    ]
    repository = GuardRepository(messages)
    publisher = RecordingPublisher()
    metrics = FakeMetrics()
    hook_calls: list[UUID] = []
    result = DrainOutboxBatch(
        repository,
        publisher,
        metrics=metrics,
        now=lambda: NOW,
        jitter=lambda _: 0,
        on_consent_refused=lambda message: hook_calls.append(message.outbox_message_id),
    ).execute()

    assert result.claimed == 4
    assert result.refused == 2
    assert result.published == 2
    assert result.retry_scheduled == 0
    assert result.dead_lettered == 0
    assert repository.refused == [messages[0].outbox_message_id, messages[3].outbox_message_id]
    assert hook_calls == repository.refused
    assert len(repository.acks) == 2
    assert metrics.values.count(("event_outbox_dispatch_total", "refused")) == 2


def test_batch_counters_must_reconcile_with_refused() -> None:
    from ansvis_adapter.application.outbox import BatchDrainResult

    with pytest.raises(ValueError, match="reconcile"):
        BatchDrainResult(claimed=3, published=1, retry_scheduled=0, dead_lettered=0, refused=1)
    result = BatchDrainResult(claimed=3, published=1, retry_scheduled=0, dead_lettered=0, refused=2)
    assert result.empty is False
