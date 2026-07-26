"""Batch drain behaviour: mixed outcomes, poison isolation, batch acknowledgement."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from ansvis_adapter.application.outbox import BatchDrainResult, DrainOutboxBatch
from ansvis_adapter.domain.errors import AnsvisAdapterError
from ansvis_adapter.domain.ingestion import PendingOutboxMessage

NOW = datetime(2026, 7, 26, 12, 0, tzinfo=UTC)
TOKEN = UUID("00000000-0000-4000-8000-000000000701")


def message(index: int, *, attempt_count: int = 0) -> PendingOutboxMessage:
    return PendingOutboxMessage(
        outbox_message_id=UUID(f"00000000-0000-4000-8000-0000000007{index:02d}"),
        normalized_event_id=uuid4(),
        claim_token=TOKEN,
        topic="camera_ai.events.camera_health_changed.v1",
        contract_version="normalized_outbox_v1",
        payload={"schema_version": "normalized_outbox_v1", "index": index},
        attempt_count=attempt_count,
        recorded_at=NOW - timedelta(seconds=45),
    )


class FakeBatchRepository:
    def __init__(self, messages: Sequence[PendingOutboxMessage]) -> None:
        self.messages = tuple(messages)
        self.requested_limits: list[int] = []
        self.batch_acks: list[tuple[tuple[tuple[UUID, UUID], ...], datetime]] = []
        self.failures: list[tuple[UUID, datetime | None]] = []

    def claim_next(self, *, now: datetime) -> PendingOutboxMessage | None:
        raise AssertionError("batch drain must not use the single-claim path")

    def claim_batch(self, *, now: datetime, limit: int) -> tuple[PendingOutboxMessage, ...]:
        del now
        self.requested_limits.append(limit)
        return self.messages[:limit]

    def mark_published(
        self, message_id: UUID, claim_token: UUID, *, published_at: datetime
    ) -> None:
        raise AssertionError("batch drain must acknowledge in one batch call")

    def mark_published_batch(
        self,
        confirmations: Sequence[tuple[UUID, UUID]],
        *,
        published_at: datetime,
    ) -> None:
        self.batch_acks.append((tuple(confirmations), published_at))

    def record_failure(
        self,
        message: PendingOutboxMessage,
        *,
        failed_at: datetime,
        next_retry_at: datetime | None,
        error_code: str,
    ) -> bool:
        assert error_code == "EVENT_OUTBOX_PUBLISH_FAILED"
        del failed_at
        self.failures.append((message.outbox_message_id, next_retry_at))
        return next_retry_at is None

    def replay_failed(
        self,
        message_id: UUID,
        *,
        actor_id: UUID,
        reason_code: str,
        authorized_at: datetime,
    ) -> None:
        raise AssertionError("replay is not part of batch drain")


class SelectivePublisher:
    def __init__(self, failing_indexes: frozenset[int]) -> None:
        self.failing_indexes = failing_indexes
        self.topics: list[str] = []

    def publish(self, *, topic: str, payload: object) -> None:
        assert isinstance(payload, dict)
        self.topics.append(topic)
        if payload["index"] in self.failing_indexes:
            raise RuntimeError("synthetic broker failure; payload stays masked")


class FakeMetrics:
    def __init__(self) -> None:
        self.values: list[tuple[str, str]] = []
        self.observations: list[tuple[str, float]] = []
        self.gauges: list[tuple[str, float]] = []

    def increment(self, metric: str, *, outcome: str) -> None:
        self.values.append((metric, outcome))

    def observe(self, metric: str, *, seconds: float) -> None:
        self.observations.append((metric, seconds))

    def set_gauge(self, metric: str, *, value: float) -> None:
        self.gauges.append((metric, value))


def drain(
    repository: FakeBatchRepository,
    publisher: SelectivePublisher,
    *,
    metrics: FakeMetrics | None = None,
    batch_size: int = 50,
) -> DrainOutboxBatch:
    return DrainOutboxBatch(
        repository,
        publisher,
        metrics=metrics,
        now=lambda: NOW,
        jitter=lambda maximum: 0,
        batch_size=batch_size,
    )


def test_full_batch_publishes_and_acknowledges_once() -> None:
    repository = FakeBatchRepository([message(i) for i in range(5)])
    publisher = SelectivePublisher(frozenset())
    metrics = FakeMetrics()

    result = drain(repository, publisher, metrics=metrics).execute()

    assert result == BatchDrainResult(claimed=5, published=5, retry_scheduled=0, dead_lettered=0)
    assert repository.requested_limits == [50]
    assert len(repository.batch_acks) == 1
    confirmations, _ = repository.batch_acks[0]
    assert len(confirmations) == 5
    assert all(token == TOKEN for _, token in confirmations)
    assert metrics.values.count(("event_outbox_dispatch_total", "published")) == 5


def test_poison_message_does_not_block_the_rest_of_the_batch() -> None:
    repository = FakeBatchRepository([message(0), message(1), message(2)])
    publisher = SelectivePublisher(frozenset({1}))

    result = drain(repository, publisher).execute()

    assert result.claimed == 3
    assert result.published == 2
    assert result.retry_scheduled == 1
    assert result.dead_lettered == 0
    assert [failure[0] for failure in repository.failures] == [message(1).outbox_message_id]
    confirmations, _ = repository.batch_acks[0]
    assert message(1).outbox_message_id not in {message_id for message_id, _ in confirmations}


def test_final_attempt_failure_dead_letters_within_the_batch() -> None:
    repository = FakeBatchRepository([message(0, attempt_count=4)])
    publisher = SelectivePublisher(frozenset({0}))

    result = drain(repository, publisher).execute()

    assert result == BatchDrainResult(claimed=1, published=0, retry_scheduled=0, dead_lettered=1)
    assert repository.failures == [(message(0).outbox_message_id, None)]
    assert repository.batch_acks == []


def test_empty_claim_emits_empty_metric_and_no_acknowledgement() -> None:
    repository = FakeBatchRepository([])
    metrics = FakeMetrics()

    result = drain(repository, SelectivePublisher(frozenset()), metrics=metrics).execute()

    assert result.empty is True
    assert repository.batch_acks == []
    assert ("event_outbox_dispatch_total", "empty") in metrics.values


def test_retry_policy_and_batch_size_are_pinned() -> None:
    repository = FakeBatchRepository([])
    publisher = SelectivePublisher(frozenset())
    with pytest.raises(ValueError, match="normalized_outbox_v1"):
        DrainOutboxBatch(repository, publisher, max_attempts=3)
    with pytest.raises(ValueError, match="1..50"):
        DrainOutboxBatch(repository, publisher, batch_size=51)


def test_repository_dead_letter_disagreement_fails_closed() -> None:
    class DisagreeingRepository(FakeBatchRepository):
        def record_failure(
            self,
            message: PendingOutboxMessage,
            *,
            failed_at: datetime,
            next_retry_at: datetime | None,
            error_code: str,
        ) -> bool:
            del failed_at, error_code
            self.failures.append((message.outbox_message_id, next_retry_at))
            return next_retry_at is not None  # deliberately inverted

    repository = DisagreeingRepository([message(0)])
    publisher = SelectivePublisher(frozenset({0}))

    with pytest.raises(AnsvisAdapterError, match="EVENT_DURABLE_RECEIPT_UNAVAILABLE"):
        drain(repository, publisher).execute()


def test_counter_reconciliation_is_enforced() -> None:
    with pytest.raises(ValueError, match="reconcile"):
        BatchDrainResult(claimed=2, published=1, retry_scheduled=0, dead_lettered=0)
