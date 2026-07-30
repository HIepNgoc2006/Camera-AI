from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from ansvis_adapter.application.outbox import DispatchOutboxMessage
from ansvis_adapter.application.telemetry import NullMetricsSink
from ansvis_adapter.domain.errors import AnsvisAdapterError
from ansvis_adapter.domain.ingestion import (
    DispatchOutcome,
    PendingOutboxMessage,
    ReplayAuthorization,
)

NOW = datetime(2026, 7, 21, 10, 0, tzinfo=UTC)
MESSAGE_ID = UUID("00000000-0000-4000-8000-000000000611")
EVENT_ID = UUID("00000000-0000-4000-8000-000000000612")
CLAIM_TOKEN = UUID("00000000-0000-4000-8000-000000000613")
ACTOR_ID = UUID("00000000-0000-4000-8000-000000000614")


def pending_message(attempt_count: int = 0) -> PendingOutboxMessage:
    return PendingOutboxMessage(
        outbox_message_id=MESSAGE_ID,
        normalized_event_id=EVENT_ID,
        claim_token=CLAIM_TOKEN,
        topic="camera_ai.events.camera_health_changed.v1",
        contract_version="normalized_outbox_v1",
        payload={
            "schema_version": "normalized_outbox_v1",
            "event_type": "camera.health.changed",
        },
        attempt_count=attempt_count,
        recorded_at=NOW - timedelta(seconds=30),
    )


class FakeRepository:
    def __init__(self, message: PendingOutboxMessage | None) -> None:
        self.message = message
        self.claim_times: list[datetime] = []
        self.published: list[tuple[UUID, UUID, datetime]] = []
        self.failures: list[tuple[PendingOutboxMessage, datetime, datetime | None, str]] = []
        self.replays: list[tuple[UUID, UUID, str, datetime]] = []
        self.force_failure_state: bool | None = None

    def claim_next(self, *, now: datetime) -> PendingOutboxMessage | None:
        self.claim_times.append(now)
        return self.message

    def claim_batch(self, *, now: datetime, limit: int) -> tuple[PendingOutboxMessage, ...]:
        del limit
        self.claim_times.append(now)
        return () if self.message is None else (self.message,)

    def mark_published(
        self, message_id: UUID, claim_token: UUID, *, published_at: datetime
    ) -> None:
        self.published.append((message_id, claim_token, published_at))

    def mark_published_batch(
        self,
        confirmations: Sequence[tuple[UUID, UUID]],
        *,
        published_at: datetime,
    ) -> None:
        for message_id, claim_token in confirmations:
            self.published.append((message_id, claim_token, published_at))

    def record_failure(
        self,
        message: PendingOutboxMessage,
        *,
        failed_at: datetime,
        next_retry_at: datetime | None,
        error_code: str,
    ) -> bool:
        self.failures.append((message, failed_at, next_retry_at, error_code))
        if self.force_failure_state is not None:
            return self.force_failure_state
        return next_retry_at is None

    def replay_failed(
        self,
        message_id: UUID,
        *,
        actor_id: UUID,
        reason_code: str,
        authorized_at: datetime,
    ) -> None:
        self.replays.append((message_id, actor_id, reason_code, authorized_at))

    def refuse_consent_blocked(
        self,
        message: PendingOutboxMessage,
        *,
        refused_at: datetime,
    ) -> None:
        raise AssertionError("consent guard must not fire for permitted payloads")


class FakePublisher:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.published: list[tuple[str, object]] = []

    def publish(self, *, topic: str, payload: object) -> None:
        if self.fail:
            raise RuntimeError("synthetic payload details must stay masked")
        self.published.append((topic, payload))


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


def test_empty_and_successful_dispatch_use_bounded_metrics() -> None:
    empty_repository = FakeRepository(None)
    empty_metrics = FakeMetrics()
    assert (
        DispatchOutboxMessage(
            empty_repository,
            FakePublisher(),
            metrics=empty_metrics,
            now=lambda: NOW,
            jitter=lambda _: 0,
        ).execute()
        is DispatchOutcome.EMPTY
    )
    assert empty_metrics.values == [("event_outbox_dispatch_total", "empty")]

    repository = FakeRepository(pending_message())
    publisher = FakePublisher()
    metrics = FakeMetrics()
    outcome = DispatchOutboxMessage(
        repository, publisher, metrics=metrics, now=lambda: NOW, jitter=lambda _: 0
    ).execute()

    assert outcome is DispatchOutcome.PUBLISHED
    assert publisher.published == [
        (
            "camera_ai.events.camera_health_changed.v1",
            {
                "schema_version": "normalized_outbox_v1",
                "event_type": "camera.health.changed",
            },
        )
    ]
    assert repository.published == [(MESSAGE_ID, CLAIM_TOKEN, NOW)]
    assert repository.failures == []
    assert metrics.values == [("event_outbox_dispatch_total", "published")]


@pytest.mark.parametrize(
    ("attempt_count", "expected_delay", "expected_outcome"),
    [
        (0, 5, DispatchOutcome.RETRY_SCHEDULED),
        (1, 10, DispatchOutcome.RETRY_SCHEDULED),
        (2, 20, DispatchOutcome.RETRY_SCHEDULED),
        (3, 40, DispatchOutcome.RETRY_SCHEDULED),
        (4, None, DispatchOutcome.DEAD_LETTERED),
    ],
)
def test_failure_uses_fixed_exponential_backoff_and_dead_letters_at_five(
    attempt_count: int,
    expected_delay: int | None,
    expected_outcome: DispatchOutcome,
) -> None:
    repository = FakeRepository(pending_message(attempt_count))
    metrics = FakeMetrics()

    outcome = DispatchOutboxMessage(
        repository,
        FakePublisher(fail=True),
        metrics=metrics,
        now=lambda: NOW,
        jitter=lambda _: 0,
    ).execute()

    assert outcome is expected_outcome
    message, failed_at, retry_at, error_code = repository.failures[0]
    assert message.attempt_count == attempt_count
    assert failed_at == NOW
    assert retry_at == (None if expected_delay is None else NOW + timedelta(seconds=expected_delay))
    assert error_code == "EVENT_OUTBOX_PUBLISH_FAILED"
    assert "synthetic payload" not in error_code
    assert metrics.values == [("event_outbox_dispatch_total", expected_outcome.value)]


def test_poison_message_is_quarantined_then_replayed_only_with_authorization() -> None:
    repository = FakeRepository(pending_message(attempt_count=4))
    metrics = FakeMetrics()
    dispatcher = DispatchOutboxMessage(
        repository,
        FakePublisher(fail=True),
        metrics=metrics,
        now=lambda: NOW,
        jitter=lambda _: 0,
    )

    assert dispatcher.execute() is DispatchOutcome.DEAD_LETTERED
    assert repository.failures[0][2] is None
    authorization = ReplayAuthorization(
        actor_id=ACTOR_ID,
        reason_code="OPERATOR_REVIEWED",
        approved=True,
        authorized_at=NOW,
    )
    dispatcher.replay(MESSAGE_ID, authorization)

    assert repository.replays == [(MESSAGE_ID, ACTOR_ID, "OPERATOR_REVIEWED", NOW)]
    assert metrics.values == [
        ("event_outbox_dispatch_total", "dead_lettered"),
        ("event_outbox_replay_total", "replayed"),
    ]


def test_repository_state_mismatch_and_naive_clock_fail_closed() -> None:
    repository = FakeRepository(pending_message())
    repository.force_failure_state = True
    with pytest.raises(AnsvisAdapterError, match="EVENT_DURABLE_RECEIPT_UNAVAILABLE"):
        DispatchOutboxMessage(
            repository,
            FakePublisher(fail=True),
            now=lambda: NOW,
            jitter=lambda _: 0,
        ).execute()

    naive = NOW.replace(tzinfo=None)
    with pytest.raises(AnsvisAdapterError, match="TIME_SOURCE_UNHEALTHY"):
        DispatchOutboxMessage(
            FakeRepository(None), FakePublisher(), now=lambda: naive, jitter=lambda _: 0
        ).execute()
    with pytest.raises(ValueError, match="invalid pending outbox message"):
        pending_message(attempt_count=5)
    with pytest.raises(AnsvisAdapterError, match="EVENT_DURABLE_RECEIPT_UNAVAILABLE"):
        DispatchOutboxMessage(
            FakeRepository(pending_message()),
            FakePublisher(fail=True),
            now=lambda: NOW,
            jitter=lambda maximum: maximum + 1,
        ).execute()


def test_replay_requires_explicit_typed_authorization() -> None:
    repository = FakeRepository(None)
    metrics = FakeMetrics()
    dispatcher = DispatchOutboxMessage(
        repository,
        FakePublisher(),
        metrics=metrics,
        now=lambda: NOW,
        jitter=lambda _: 0,
    )
    authorization = ReplayAuthorization(
        actor_id=ACTOR_ID,
        reason_code="OPERATOR_REVIEWED",
        approved=True,
        authorized_at=NOW,
    )

    dispatcher.replay(MESSAGE_ID, authorization)

    assert repository.replays == [(MESSAGE_ID, ACTOR_ID, "OPERATOR_REVIEWED", NOW)]
    assert metrics.values == [("event_outbox_replay_total", "replayed")]
    with pytest.raises(ValueError, match="invalid replay authorization"):
        ReplayAuthorization(
            actor_id=ACTOR_ID,
            reason_code="free form reason",
            approved=True,
            authorized_at=NOW,
        )


def test_null_metrics_sink_rejects_unbounded_names_and_labels() -> None:
    metrics = NullMetricsSink()
    metrics.increment("event_outbox_dispatch_total", outcome="published")
    with pytest.raises(ValueError, match="not registered"):
        metrics.increment("event_id_611", outcome="published")
    with pytest.raises(ValueError, match="allowlisted"):
        metrics.increment("event_outbox_dispatch_total", outcome="camera_611")
    with pytest.raises(ValueError, match="not a registered histogram"):
        metrics.observe("event_outbox_dispatch_total", seconds=0.1)
    with pytest.raises(ValueError, match="not a registered gauge"):
        metrics.set_gauge("event_ingestion_ack_seconds", value=1.0)
