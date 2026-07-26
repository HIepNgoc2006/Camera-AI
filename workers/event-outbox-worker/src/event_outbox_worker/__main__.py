"""Process bootstrap: wire settings, event store, publisher, metrics, drain and runner.

The worker only drains the outbox: it never records events, never resolves scopes and never
touches retention. The event store's write-path collaborators are therefore wired fail-closed.
Housekeeping refreshes the approved backlog gauges and evaluates the operational alert
thresholds on a bounded interval, logging only stable codes and counters.
"""

from __future__ import annotations

import contextlib
import logging
import sys
from collections.abc import Callable
from datetime import UTC, datetime

import sqlalchemy as sa
from ansvis_adapter.application.outbox import DrainOutboxBatch
from ansvis_adapter.application.ports import (
    AuthenticatedSource,
    EventScopeResolver,
    MetricsSink,
    OperationalStatusRepository,
)
from ansvis_adapter.application.telemetry import EvaluateOperationalAlerts
from ansvis_adapter.config import load_event_database_settings, load_settings
from ansvis_adapter.domain.errors import AnsvisAdapterError
from ansvis_adapter.domain.ingestion import AlertSeverity, ResolvedEventScope
from ansvis_adapter.domain.models import NormalizedAnsvisEvent
from ansvis_adapter.infrastructure.event_store import PostgresEventIngestionRepository
from camera_ai_metrics import PrometheusMetricsSink, start_internal_metrics_server

from event_outbox_worker.config import WorkerSettings, load_worker_settings
from event_outbox_worker.logging import configure_logging
from event_outbox_worker.publisher import RabbitMqEventPublisher
from event_outbox_worker.runner import WorkerRunner, install_signal_handlers

# The drain paths never write events, so retention input is irrelevant here; the store
# constructor still demands a bounded value. Kept explicit and far from any real policy.
_UNUSED_RETENTION_DAYS = 365


class DrainOnlyScopeResolver(EventScopeResolver):
    """Fail closed if any write path is ever reached from the drain worker."""

    def resolve(
        self, event: NormalizedAnsvisEvent, source: AuthenticatedSource
    ) -> ResolvedEventScope:
        del event, source
        raise AnsvisAdapterError("EVENT_DURABLE_RECEIPT_UNAVAILABLE")


def build_housekeeping(
    status: OperationalStatusRepository,
    metrics: MetricsSink,
    logger: logging.Logger,
    *,
    alerts: EvaluateOperationalAlerts | None = None,
) -> Callable[[], None]:
    """Return the interval task refreshing gauges and evaluating approved alerts."""

    evaluator = alerts or EvaluateOperationalAlerts()

    def run() -> None:
        snapshot = status.snapshot(now=datetime.now(UTC))
        metrics.set_gauge("event_outbox_backlog_messages", value=snapshot.pending_messages)
        metrics.set_gauge(
            "event_outbox_oldest_pending_seconds", value=snapshot.oldest_pending_seconds
        )
        for alert in evaluator.execute(snapshot):
            with contextlib.suppress(Exception):
                metrics.increment("event_operational_alerts_total", outcome=alert.code.lower())
            log = logger.critical if alert.severity is AlertSeverity.CRITICAL else logger.warning
            log(
                "operational alert",
                extra={"event": "operational_alert", "error_code": alert.code},
            )

    return run


def main() -> int:
    settings = load_settings()
    worker: WorkerSettings = load_worker_settings()
    logger = configure_logging(settings.log_level, settings.environment)
    database = load_event_database_settings()
    engine = sa.create_engine(database.database_url, pool_pre_ping=True)
    store = PostgresEventIngestionRepository(
        engine,
        scopes=DrainOnlyScopeResolver(),
        retention_days=_UNUSED_RETENTION_DAYS,
    )
    metrics = PrometheusMetricsSink()
    metrics_server = None
    if worker.metrics_port != 0:
        metrics_server = start_internal_metrics_server(metrics, port=worker.metrics_port)
    publisher = RabbitMqEventPublisher(worker.broker_url)
    drain = DrainOutboxBatch(store, publisher, metrics=metrics, batch_size=worker.batch_size)
    housekeeping = build_housekeeping(store, metrics, logger)
    runner = WorkerRunner(
        drain,
        publisher,
        logger=logger,
        idle_sleep_seconds=worker.idle_sleep_seconds,
        broker_retry_seconds=worker.broker_retry_seconds,
        housekeeping=housekeeping,
        housekeeping_interval_seconds=worker.snapshot_interval_seconds,
    )
    install_signal_handlers(runner)
    try:
        return runner.run()
    finally:
        publisher.close()
        if metrics_server is not None:
            metrics_server.shutdown()
        engine.dispose()


if __name__ == "__main__":
    sys.exit(main())
