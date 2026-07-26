"""Deliver leased audit intents to the owning audit-log-service append use case.

The worker is the trusted delivery boundary: it builds the `TrustedAuditContext` (service
actor, approved retention) around each publisher payload and treats a duplicate append as
success-already-recorded, so retries can never create double evidence or retry storms.
Delivery failures follow the same bounded `normalized_outbox_v1` retry policy as event
dispatch; a row that keeps failing lands in terminal `failed` for operator triage.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from ansvis_adapter.application.outbox import (
    BatchDrainResult,
    _compute_retry_at,
    bounded_jitter,
    system_utc_now,
)
from ansvis_adapter.application.ports import MetricsSink
from ansvis_adapter.application.telemetry import NullMetricsSink
from ansvis_adapter.domain.errors import AnsvisAdapterError
from ansvis_adapter.infrastructure.audit_outbox import PendingAuditIntent

DELIVERY_METRIC = "event_audit_delivery_total"


class AuditOutboxPort(Protocol):
    def claim_batch(self, *, now: datetime, limit: int) -> tuple[PendingAuditIntent, ...]: ...

    def mark_delivered_batch(
        self, confirmations: Sequence[tuple[UUID, UUID]], *, delivered_at: datetime
    ) -> None: ...

    def record_failure(
        self,
        intent: PendingAuditIntent,
        *,
        failed_at: datetime,
        next_retry_at: datetime | None,
        error_code: str,
    ) -> bool: ...


class AuditAppender(Protocol):
    def append(self, intent: PendingAuditIntent) -> bool:
        """Durably append one intent; return True when it was already recorded."""


class DeliverAuditIntents:
    """Claim up to fifty intents, append each, and batch-acknowledge the successes."""

    def __init__(
        self,
        outbox: AuditOutboxPort,
        appender: AuditAppender,
        *,
        metrics: MetricsSink | None = None,
        now: Callable[[], datetime] = system_utc_now,
        jitter: Callable[[int], int] = bounded_jitter,
        batch_size: int = 50,
    ) -> None:
        if not 1 <= batch_size <= 50:
            raise ValueError("audit delivery batch size must stay within 1..50")
        self._outbox = outbox
        self._appender = appender
        self._metrics = metrics or NullMetricsSink()
        self._now = now
        self._jitter = jitter
        self._batch_size = batch_size

    def execute(self) -> BatchDrainResult:
        now = self._aware_now()
        intents = self._outbox.claim_batch(now=now, limit=self._batch_size)
        if not intents:
            self._metric("empty")
            return BatchDrainResult(claimed=0, published=0, retry_scheduled=0, dead_lettered=0)

        delivered: list[tuple[UUID, UUID]] = []
        retry_scheduled = 0
        dead_lettered = 0
        for intent in intents:
            try:
                duplicate = self._appender.append(intent)
            except Exception:
                dead, retry_at = _compute_retry_at(
                    attempt_count=intent.attempt_count,
                    now=now,
                    jitter=self._jitter,
                    max_attempts=5,
                    base_backoff_seconds=5,
                )
                persisted_dead = self._outbox.record_failure(
                    intent,
                    failed_at=now,
                    next_retry_at=retry_at,
                    error_code="AUDIT_DELIVERY_FAILED",
                )
                if persisted_dead != dead:
                    raise AnsvisAdapterError("AUDIT_OUTBOX_UNAVAILABLE") from None
                if dead:
                    dead_lettered += 1
                    self._metric("dead_lettered")
                else:
                    retry_scheduled += 1
                    self._metric("retry_scheduled")
            else:
                delivered.append((intent.audit_outbox_id, intent.claim_token))
                self._metric("duplicate" if duplicate else "delivered")

        if delivered:
            self._outbox.mark_delivered_batch(delivered, delivered_at=self._aware_now())
        return BatchDrainResult(
            claimed=len(intents),
            published=len(delivered),
            retry_scheduled=retry_scheduled,
            dead_lettered=dead_lettered,
        )

    def _metric(self, outcome: str) -> None:
        try:
            self._metrics.increment(DELIVERY_METRIC, outcome=outcome)
        except Exception:
            return

    def _aware_now(self) -> datetime:
        value = self._now()
        if value.tzinfo is None or value.utcoffset() is None:
            raise AnsvisAdapterError("TIME_SOURCE_UNHEALTHY")
        return value.astimezone(UTC)


class DrainLike(Protocol):
    def execute(self) -> BatchDrainResult: ...


class CompositeDrain:
    """Run several drains in order and report their element-wise combined counts."""

    def __init__(self, drains: Sequence[DrainLike]) -> None:
        if not drains:
            raise ValueError("composite drain requires at least one drain")
        self._drains = tuple(drains)

    def execute(self) -> BatchDrainResult:
        claimed = published = retry = dead = 0
        for drain in self._drains:
            result = drain.execute()
            claimed += result.claimed
            published += result.published
            retry += result.retry_scheduled
            dead += result.dead_lettered
        return BatchDrainResult(
            claimed=claimed,
            published=published,
            retry_scheduled=retry,
            dead_lettered=dead,
        )
