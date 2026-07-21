"""Bounded outbox dispatch and replay orchestration."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from secrets import randbelow
from uuid import UUID

from ansvis_adapter.application.ports import EventPublisher, MetricsSink, OutboxRepository
from ansvis_adapter.application.telemetry import NullMetricsSink
from ansvis_adapter.domain.errors import AnsvisAdapterError
from ansvis_adapter.domain.ingestion import DispatchOutcome, ReplayAuthorization


def system_utc_now() -> datetime:
    return datetime.now(UTC)


def bounded_jitter(maximum_seconds: int) -> int:
    return randbelow(maximum_seconds + 1)


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
            next_attempt = message.attempt_count + 1
            dead_lettered = next_attempt >= self._max_attempts
            retry_at = None
            if not dead_lettered:
                base_delay = self._base_backoff_seconds * (2 ** (next_attempt - 1))
                maximum_jitter = max(1, base_delay // 5)
                try:
                    jitter = self._jitter(maximum_jitter)
                except Exception:
                    raise AnsvisAdapterError("EVENT_DURABLE_RECEIPT_UNAVAILABLE") from None
                if not 0 <= jitter <= maximum_jitter:
                    raise AnsvisAdapterError("EVENT_DURABLE_RECEIPT_UNAVAILABLE") from None
                delay = base_delay + jitter
                retry_at = now + timedelta(seconds=delay)
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
