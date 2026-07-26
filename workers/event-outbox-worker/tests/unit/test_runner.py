"""Runner loop behaviour: broker gating, drain errors, graceful stop, heartbeat counts."""

from __future__ import annotations

import logging
import threading

import pytest
from ansvis_adapter.application.outbox import BatchDrainResult
from ansvis_adapter.domain.errors import AnsvisAdapterError
from event_outbox_worker.runner import WorkerRunner, _stable_code


def result(claimed: int = 0, published: int = 0, retry: int = 0, dead: int = 0) -> BatchDrainResult:
    return BatchDrainResult(
        claimed=claimed, published=published, retry_scheduled=retry, dead_lettered=dead
    )


class ScriptedDrain:
    def __init__(self, results: list[BatchDrainResult | Exception]) -> None:
        self.results = results
        self.calls = 0

    def execute(self) -> BatchDrainResult:
        index = min(self.calls, len(self.results) - 1)
        self.calls += 1
        outcome = self.results[index]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class ScriptedBroker:
    def __init__(self, answers: list[bool]) -> None:
        self.answers = answers
        self.calls = 0

    def ensure_connected(self) -> bool:
        index = min(self.calls, len(self.answers) - 1)
        self.calls += 1
        return self.answers[index]


def make_runner(
    drain: ScriptedDrain,
    broker: ScriptedBroker,
    *,
    max_iterations: int,
    stop_event: threading.Event | None = None,
) -> WorkerRunner:
    return WorkerRunner(
        drain,
        broker,
        logger=logging.getLogger("event-outbox-worker-test"),
        idle_sleep_seconds=0.001,
        broker_retry_seconds=0.001,
        stop_event=stop_event,
        max_iterations=max_iterations,
    )


def test_no_claim_happens_while_broker_is_unavailable() -> None:
    drain = ScriptedDrain([result()])
    broker = ScriptedBroker([False, False, False])

    exit_code = make_runner(drain, broker, max_iterations=3).run()

    assert exit_code == 0
    assert broker.calls == 3
    assert drain.calls == 0  # attempts are never burned during an outage


def test_drain_runs_once_broker_recovers() -> None:
    drain = ScriptedDrain([result(claimed=2, published=2)])
    broker = ScriptedBroker([False, True])

    make_runner(drain, broker, max_iterations=2).run()

    assert drain.calls == 1


def test_drain_exception_is_survived_and_loop_continues() -> None:
    drain = ScriptedDrain(
        [AnsvisAdapterError("EVENT_DURABLE_RECEIPT_UNAVAILABLE"), result(claimed=1, published=1)]
    )
    broker = ScriptedBroker([True])

    exit_code = make_runner(drain, broker, max_iterations=2).run()

    assert exit_code == 0
    assert drain.calls == 2


def test_stop_event_ends_the_loop_before_further_iterations() -> None:
    stop = threading.Event()
    stop.set()
    drain = ScriptedDrain([result(claimed=1, published=1)])
    broker = ScriptedBroker([True])

    exit_code = make_runner(drain, broker, max_iterations=10, stop_event=stop).run()

    assert exit_code == 0
    assert drain.calls == 0
    assert broker.calls == 0


def test_runner_rejects_non_positive_intervals() -> None:
    drain = ScriptedDrain([result()])
    broker = ScriptedBroker([True])
    with pytest.raises(ValueError, match="positive"):
        WorkerRunner(
            drain,
            broker,
            logger=logging.getLogger("event-outbox-worker-test"),
            idle_sleep_seconds=0,
            broker_retry_seconds=1,
        )


def test_stable_code_extraction_is_conservative() -> None:
    assert _stable_code(AnsvisAdapterError("EVENT_DURABLE_RECEIPT_UNAVAILABLE")) == (
        "EVENT_DURABLE_RECEIPT_UNAVAILABLE"
    )
    assert _stable_code(RuntimeError("boom with details")) == "EVENT_OUTBOX_DRAIN_FAILED"
    assert _stable_code(RuntimeError("secret=abc UPPER")) == "EVENT_OUTBOX_DRAIN_FAILED"
