"""Audit delivery drain: duplicate-as-success, bounded retries, composite summing."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from ansvis_adapter.application.outbox import BatchDrainResult
from ansvis_adapter.domain.errors import AnsvisAdapterError
from ansvis_adapter.infrastructure.audit_outbox import PendingAuditIntent
from event_outbox_worker.audit_delivery import CompositeDrain, DeliverAuditIntents

NOW = datetime(2026, 7, 26, 14, 30, tzinfo=UTC)
TOKEN = UUID("00000000-0000-4000-8000-000000000901")


def intent(index: int, *, attempt_count: int = 0) -> PendingAuditIntent:
    return PendingAuditIntent(
        audit_outbox_id=UUID(f"00000000-0000-4000-8000-0000000009{index:02d}"),
        claim_token=TOKEN,
        source_service="ansvis-adapter-service",
        source_event_id=uuid4(),
        school_id=None,
        payload={"event_schema_version": 1, "action": "ANSVIS_SOURCE_AUTH_DENIED"},
        attempt_count=attempt_count,
        recorded_at=NOW - timedelta(seconds=20),
    )


class FakeAuditOutbox:
    def __init__(self, intents: Sequence[PendingAuditIntent]) -> None:
        self.intents = tuple(intents)
        self.delivered: list[tuple[tuple[UUID, UUID], ...]] = []
        self.failures: list[tuple[UUID, datetime | None, str]] = []

    def claim_batch(self, *, now: datetime, limit: int) -> tuple[PendingAuditIntent, ...]:
        del now
        return self.intents[:limit]

    def mark_delivered_batch(
        self, confirmations: Sequence[tuple[UUID, UUID]], *, delivered_at: datetime
    ) -> None:
        del delivered_at
        self.delivered.append(tuple(confirmations))

    def record_failure(
        self,
        intent: PendingAuditIntent,
        *,
        failed_at: datetime,
        next_retry_at: datetime | None,
        error_code: str,
    ) -> bool:
        del failed_at
        self.failures.append((intent.audit_outbox_id, next_retry_at, error_code))
        return next_retry_at is None


class ScriptedAppender:
    def __init__(
        self, *, duplicates: frozenset[int] = frozenset(), failing: frozenset[int] = frozenset()
    ) -> None:
        self.duplicates = duplicates
        self.failing = failing
        self.calls = 0

    def append(self, intent: PendingAuditIntent) -> bool:
        index = int(intent.audit_outbox_id.hex[-2:])
        self.calls += 1
        if index in self.failing:
            raise RuntimeError("synthetic append failure; evidence content stays masked")
        return index in self.duplicates


class FakeMetrics:
    def __init__(self) -> None:
        self.values: list[tuple[str, str]] = []

    def increment(self, metric: str, *, outcome: str) -> None:
        self.values.append((metric, outcome))

    def observe(self, metric: str, *, seconds: float) -> None:
        del metric, seconds

    def set_gauge(self, metric: str, *, value: float) -> None:
        del metric, value


def test_delivery_treats_duplicates_as_success_and_acknowledges_once() -> None:
    outbox = FakeAuditOutbox([intent(0), intent(1)])
    metrics = FakeMetrics()
    drain = DeliverAuditIntents(
        outbox,
        ScriptedAppender(duplicates=frozenset({1})),
        metrics=metrics,
        now=lambda: NOW,
        jitter=lambda maximum: 0,
    )

    result = drain.execute()

    assert result == BatchDrainResult(claimed=2, published=2, retry_scheduled=0, dead_lettered=0)
    assert len(outbox.delivered) == 1 and len(outbox.delivered[0]) == 2
    assert ("event_audit_delivery_total", "delivered") in metrics.values
    assert ("event_audit_delivery_total", "duplicate") in metrics.values


def test_append_failure_retries_with_bounded_policy_and_dead_letters_at_five() -> None:
    outbox = FakeAuditOutbox([intent(0), intent(1, attempt_count=4)])
    drain = DeliverAuditIntents(
        outbox,
        ScriptedAppender(failing=frozenset({0, 1})),
        now=lambda: NOW,
        jitter=lambda maximum: 0,
    )

    result = drain.execute()

    assert result.retry_scheduled == 1
    assert result.dead_lettered == 1
    assert outbox.delivered == []
    first, second = outbox.failures
    assert first == (intent(0).audit_outbox_id, NOW + timedelta(seconds=5), "AUDIT_DELIVERY_FAILED")
    assert second == (intent(1).audit_outbox_id, None, "AUDIT_DELIVERY_FAILED")


def test_outbox_state_disagreement_fails_closed() -> None:
    class Disagreeing(FakeAuditOutbox):
        def record_failure(
            self,
            intent: PendingAuditIntent,
            *,
            failed_at: datetime,
            next_retry_at: datetime | None,
            error_code: str,
        ) -> bool:
            del failed_at, error_code
            return next_retry_at is not None  # inverted on purpose

    drain = DeliverAuditIntents(
        Disagreeing([intent(0)]),
        ScriptedAppender(failing=frozenset({0})),
        now=lambda: NOW,
        jitter=lambda maximum: 0,
    )

    with pytest.raises(AnsvisAdapterError, match="AUDIT_OUTBOX_UNAVAILABLE"):
        drain.execute()


def test_empty_claim_and_batch_bounds() -> None:
    metrics = FakeMetrics()
    drain = DeliverAuditIntents(
        FakeAuditOutbox([]), ScriptedAppender(), metrics=metrics, now=lambda: NOW
    )

    assert drain.execute().empty is True
    assert ("event_audit_delivery_total", "empty") in metrics.values
    with pytest.raises(ValueError, match="1..50"):
        DeliverAuditIntents(FakeAuditOutbox([]), ScriptedAppender(), batch_size=0)


def test_composite_drain_sums_results_in_order() -> None:
    class Static:
        def __init__(self, result: BatchDrainResult) -> None:
            self.result = result

        def execute(self) -> BatchDrainResult:
            return self.result

    combined = CompositeDrain(
        (
            Static(
                BatchDrainResult(
                    claimed=5, published=2, retry_scheduled=1, dead_lettered=1, refused=1
                )
            ),
            Static(
                BatchDrainResult(
                    claimed=3, published=2, retry_scheduled=0, dead_lettered=0, refused=1
                )
            ),
        )
    ).execute()

    assert combined == BatchDrainResult(
        claimed=8, published=4, retry_scheduled=1, dead_lettered=1, refused=2
    )
    with pytest.raises(ValueError, match="at least one"):
        CompositeDrain(())
