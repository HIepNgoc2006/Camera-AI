"""Bounded outbox dispatch and replay orchestration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from secrets import randbelow
from uuid import UUID

from ansvis_adapter.application.ports import EventPublisher, MetricsSink, OutboxRepository
from ansvis_adapter.application.telemetry import NullMetricsSink
from ansvis_adapter.domain.errors import AnsvisAdapterError
from ansvis_adapter.domain.ingestion import (
    DispatchOutcome,
    PendingOutboxMessage,
    ReplayAuthorization,
)


def system_utc_now() -> datetime:
    return datetime.now(UTC)


def bounded_jitter(maximum_seconds: int) -> int:
    return randbelow(maximum_seconds + 1)


def _compute_retry_at(
    message: PendingOutboxMessage,
    *,
    now: datetime,
    jitter: Callable[[int], int],
    max_attempts: int,
    base_backoff_seconds: int,
) -> tuple[bool, datetime | None]:
    """Return `(dead_lettered, retry_at)` under the normalized_outbox_v1 backoff policy."""

    next_attempt = message.attempt_count + 1
    dead_lettered = next_attempt >= max_attempts
    if dead_lettered:
        return True, None
    base_delay = base_backoff_seconds * (2 ** (next_attempt - 1))
    maximum_jitter = max(1, base_delay // 5)
    try:
        jitter_seconds = jitter(maximum_jitter)
    except Exception:
        raise AnsvisAdapterError("EVENT_DURABLE_RECEIPT_UNAVAILABLE") from None
    if not 0 <= jitter_seconds <= maximum_jitter:
        raise AnsvisAdapterError("EVENT_DURABLE_RECEIPT_UNAVAILABLE") from None
    return False, now + timedelta(seconds=base_delay + jitter_seconds)


class DispatchOutboxMessage:
    """Dispatch one message with deterministic backoff and a bounded dead-letter transition."""

    def __init__(
        self,
        repository: OutboxRepository,
        publisher: EventPublisher,
        *,
        metrics: MetricsSink | None = None,
        now: Callable[[], datetime] = system_utc_now,
        jitter: Callable[[int], int] = bounded_jitter,
        max_attempts: int = 5,
        base_backoff_seconds: int = 5,
    ) -> None:
        if max_attempts != 5 or base_backoff_seconds != 5:
            raise ValueError("outbox retry policy must match normalized_outbox_v1")
        self._repository = repository
        self._publisher = publisher
        self._metrics = metrics or NullMetricsSink()
        self._now = now
        self._jitter = jitter
        self._max_attempts = max_attempts
        self._base_backoff_seconds = base_backoff_seconds

    def execute(self) -> DispatchOutcome:
        now = self._aware_now()
        message = self._repository.claim_next(now=now)
        if message is None:
            self._metric("empty")
            return DispatchOutcome.EMPTY
        try:
            self._publisher.publish(topic=message.topic, payload=message.payload)
        except Exception:
            dead_lettered, retry_at = _compute_retry_at(
                message,
                now=now,
                jitter=self._jitter,
                max_attempts=self._max_attempts,
                base_backoff_seconds=self._base_backoff_seconds,
            )
            persisted_dead_letter = self._repository.record_failure(
                message,
                failed_at=now,
                next_retry_at=retry_at,
                error_code="EVENT_OUTBOX_PUBLISH_FAILED",
            )
            if persisted_dead_letter != dead_lettered:
                raise AnsvisAdapterError("EVENT_DURABLE_RECEIPT_UNAVAILABLE") from None
            outcome = "dead_lettered" if dead_lettered else "retry_scheduled"
            self._metric(outcome)
            return DispatchOutcome(outcome)
        self._repository.mark_published(
            message.outbox_message_id,
            message.claim_token,
            published_at=now,
        )
        self._metric("published")
        return DispatchOutcome.PUBLISHED

    def replay(self, message_id: UUID, authorization: ReplayAuthorization) -> None:
        self._repository.replay_failed(
            message_id,
            actor_id=authorization.actor_id,
            reason_code=authorization.reason_code,
            authorized_at=authorization.authorized_at,
        )
        self._increment("event_outbox_replay_total", "replayed")

    def _metric(self, outcome: str) -> None:
        self._increment("event_outbox_dispatch_total", outcome)

    def _increment(self, metric: str, outcome: str) -> None:
        try:
            self._metrics.increment(metric, outcome=outcome)
        except Exception:
            return

    def _aware_now(self) -> datetime:
        value = self._now()
        if value.tzinfo is None or value.utcoffset() is None:
            raise AnsvisAdapterError("TIME_SOURCE_UNHEALTHY")
        return value.astimezone(UTC)


@dataclass(frozen=True, slots=True, kw_only=True)
class BatchDrainResult:
    """Identifier-free counts from one batch drain iteration."""

    claimed: int
    published: int
    retry_scheduled: int
    dead_lettered: int

    def __post_init__(self) -> None:
        if (
            min(self.claimed, self.published, self.retry_scheduled, self.dead_lettered) < 0
            or self.published + self.retry_scheduled + self.dead_lettered != self.claimed
        ):
            raise ValueError("batch drain counters must reconcile")

    @property
    def empty(self) -> bool:
        return self.claimed == 0


class DrainOutboxBatch:
    """Claim up to fifty due messages, publish each, and batch-acknowledge the successes.

    Failures follow exactly the same `normalized_outbox_v1` retry/dead-letter policy as the
    single-message dispatcher; one poison message never blocks the rest of its batch.
    """

    def __init__(
        self,
        repository: OutboxRepository,
        publisher: EventPublisher,
        *,
        metrics: MetricsSink | None = None,
        now: Callable[[], datetime] = system_utc_now,
        jitter: Callable[[int], int] = bounded_jitter,
        batch_size: int = 50,
        max_attempts: int = 5,
        base_backoff_seconds: int = 5,
    ) -> None:
        if max_attempts != 5 or base_backoff_seconds != 5:
            raise ValueError("outbox retry policy must match normalized_outbox_v1")
        if not 1 <= batch_size <= 50:
            raise ValueError("outbox drain batch size must stay within 1..50")
        self._repository = repository
        self._publisher = publisher
        self._metrics = metrics or NullMetricsSink()
        self._now = now
        self._jitter = jitter
        self._batch_size = batch_size
        self._max_attempts = max_attempts
        self._base_backoff_seconds = base_backoff_seconds

    def execute(self) -> BatchDrainResult:
        now = self._aware_now()
        messages = self._repository.claim_batch(now=now, limit=self._batch_size)
        if not messages:
            self._metric("empty")
            return BatchDrainResult(claimed=0, published=0, retry_scheduled=0, dead_lettered=0)

        published: list[tuple[UUID, UUID]] = []
        retry_scheduled = 0
        dead_lettered = 0
        for message in messages:
            try:
                self._publisher.publish(topic=message.topic, payload=message.payload)
            except Exception:
                message_dead, retry_at = _compute_retry_at(
                    message,
                    now=now,
                    jitter=self._jitter,
                    max_attempts=self._max_attempts,
                    base_backoff_seconds=self._base_backoff_seconds,
                )
                persisted_dead_letter = self._repository.record_failure(
                    message,
                    failed_at=now,
                    next_retry_at=retry_at,
                    error_code="EVENT_OUTBOX_PUBLISH_FAILED",
                )
                if persisted_dead_letter != message_dead:
                    raise AnsvisAdapterError("EVENT_DURABLE_RECEIPT_UNAVAILABLE") from None
                if message_dead:
                    dead_lettered += 1
                    self._metric("dead_lettered")
                else:
                    retry_scheduled += 1
                    self._metric("retry_scheduled")
            else:
                published.append((message.outbox_message_id, message.claim_token))
                self._metric("published")

        if published:
            self._repository.mark_published_batch(published, published_at=self._aware_now())
        return BatchDrainResult(
            claimed=len(messages),
            published=len(published),
            retry_scheduled=retry_scheduled,
            dead_lettered=dead_lettered,
        )

    def _metric(self, outcome: str) -> None:
        self._increment("event_outbox_dispatch_total", outcome)

    def _increment(self, metric: str, outcome: str) -> None:
        try:
            self._metrics.increment(metric, outcome=outcome)
        except Exception:
            return

    def _aware_now(self) -> datetime:
        value = self._now()
        if value.tzinfo is None or value.utcoffset() is None:
            raise AnsvisAdapterError("TIME_SOURCE_UNHEALTHY")
        return value.astimezone(UTC)
