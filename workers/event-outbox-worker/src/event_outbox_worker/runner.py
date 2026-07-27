"""Supervised drain loop: broker-gated batches, graceful shutdown, heartbeat logging.

The loop never claims messages while the broker is unreachable — claiming would burn bounded
retry attempts on an outage that is not the message's fault. Shutdown finishes the in-flight
batch and exits cleanly; the database lease expiry recovers anything left by a hard crash.
An optional housekeeping callable runs on its own interval for snapshot gauges and the approved
operational alert evaluation; its failures never stop the drain loop.
"""

from __future__ import annotations

import logging
import signal
import threading
import time
from collections.abc import Callable
from typing import Protocol

from ansvis_adapter.application.outbox import BatchDrainResult

HEARTBEAT_EVERY_ITERATIONS = 60


class DrainUseCase(Protocol):
    def execute(self) -> BatchDrainResult: ...


class BrokerHealth(Protocol):
    def ensure_connected(self) -> bool: ...


class WorkerRunner:
    """Run drain iterations until stopped; every sleep is interruptible by the stop event."""

    def __init__(
        self,
        drain: DrainUseCase,
        broker: BrokerHealth,
        *,
        logger: logging.Logger,
        idle_sleep_seconds: float,
        broker_retry_seconds: float,
        stop_event: threading.Event | None = None,
        max_iterations: int | None = None,
        housekeeping: Callable[[], None] | None = None,
        housekeeping_interval_seconds: float = 60.0,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        if idle_sleep_seconds <= 0 or broker_retry_seconds <= 0:
            raise ValueError("runner sleep intervals must be positive")
        if max_iterations is not None and max_iterations < 1:
            raise ValueError("max_iterations must be positive when bounded")
        if housekeeping_interval_seconds <= 0:
            raise ValueError("housekeeping interval must be positive")
        self._drain = drain
        self._broker = broker
        self._logger = logger
        self._idle_sleep_seconds = idle_sleep_seconds
        self._broker_retry_seconds = broker_retry_seconds
        self._stop = stop_event or threading.Event()
        self._max_iterations = max_iterations
        self._housekeeping = housekeeping
        self._housekeeping_interval = housekeeping_interval_seconds
        self._monotonic = monotonic
        self._last_housekeeping = float("-inf")

    @property
    def stop_event(self) -> threading.Event:
        return self._stop

    def request_stop(self) -> None:
        self._stop.set()

    def run(self) -> int:
        """Drain until stopped; return a process exit code."""

        self._logger.info("worker start", extra={"event": "worker_started"})
        iterations = 0
        quiet_iterations = 0
        while not self._stop.is_set():
            if self._max_iterations is not None and iterations >= self._max_iterations:
                break
            iterations += 1
            self._run_housekeeping()
            if not self._broker.ensure_connected():
                self._logger.warning(
                    "broker unavailable",
                    extra={"event": "broker_unavailable", "error_code": "EVENT_BROKER_UNAVAILABLE"},
                )
                self._stop.wait(self._broker_retry_seconds)
                continue
            try:
                result = self._drain.execute()
            except Exception as error:
                self._logger.error(
                    "drain failed",
                    extra={"event": "drain_failed", "error_code": _stable_code(error)},
                )
                self._stop.wait(self._broker_retry_seconds)
                continue
            if result.empty:
                quiet_iterations += 1
                if quiet_iterations % HEARTBEAT_EVERY_ITERATIONS == 0:
                    self._log_result("worker_idle", result)
                self._stop.wait(self._idle_sleep_seconds)
            else:
                quiet_iterations = 0
                self._log_result("batch_drained", result)
        self._logger.info("worker stop", extra={"event": "worker_stopped"})
        return 0

    def _run_housekeeping(self) -> None:
        if self._housekeeping is None:
            return
        now = self._monotonic()
        if now - self._last_housekeeping < self._housekeeping_interval:
            return
        self._last_housekeeping = now
        try:
            self._housekeeping()
        except Exception as error:
            self._logger.warning(
                "housekeeping failed",
                extra={"event": "housekeeping_failed", "error_code": _stable_code(error)},
            )

    def _log_result(self, event: str, result: BatchDrainResult) -> None:
        self._logger.info(
            event,
            extra={
                "event": event,
                "claimed": result.claimed,
                "published": result.published,
                "retry_scheduled": result.retry_scheduled,
                "dead_lettered": result.dead_lettered,
                "refused": result.refused,
            },
        )


def install_signal_handlers(runner: WorkerRunner) -> None:
    """Route SIGINT/SIGTERM to a graceful stop request."""

    def _handle(signum: int, frame: object) -> None:
        del signum, frame
        runner.request_stop()

    signal.signal(signal.SIGINT, _handle)
    signal.signal(signal.SIGTERM, _handle)


def _stable_code(error: Exception) -> str:
    text = str(error)
    if text.isupper() and " " not in text and 0 < len(text) <= 64:
        return text
    return "EVENT_OUTBOX_DRAIN_FAILED"
