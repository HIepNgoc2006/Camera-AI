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
from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_URL, uuid5

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
from ansvis_adapter.domain.consent import CONSENT_BLOCKED, CONSENT_GATE_POLICY_VERSION
from ansvis_adapter.domain.errors import AnsvisAdapterError
from ansvis_adapter.domain.ingestion import (
    AlertSeverity,
    PendingOutboxMessage,
    ResolvedEventScope,
)
from ansvis_adapter.domain.models import NormalizedAnsvisEvent
from ansvis_adapter.infrastructure.audit_outbox import (
    PendingAuditIntent,
    PostgresAuditOutbox,
    school_for_event,
)
from ansvis_adapter.infrastructure.event_store import (
    AUDIT_SOURCE_SERVICE,
    CONSENT_AUDIT_ACTION,
    PostgresEventIngestionRepository,
)
from ansvis_adapter.infrastructure.unavailable import UnavailableConsentGate
from audit_log_service.application.service import AppendAuditEventService
from audit_log_service.config import load_database_settings as load_audit_database_settings
from audit_log_service.domain.models import ActorType, TrustedAuditContext
from audit_log_service.infrastructure.integrity import HmacSha256IntegritySigner
from audit_log_service.infrastructure.repository import SqlAlchemyAuditRepository
from camera_ai_audit import AuditIntent, IntentResult
from camera_ai_metrics import PrometheusMetricsSink, start_internal_metrics_server

from event_outbox_worker.audit_delivery import CompositeDrain, DeliverAuditIntents
from event_outbox_worker.config import (
    WorkerSettings,
    load_audit_delivery_settings,
    load_worker_settings,
)
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
    audit_outbox: PostgresAuditOutbox | None = None,
) -> Callable[[], None]:
    """Return the interval task refreshing gauges and evaluating approved alerts."""

    evaluator = alerts or EvaluateOperationalAlerts()

    def run() -> None:
        snapshot = status.snapshot(now=datetime.now(UTC))
        metrics.set_gauge("event_outbox_backlog_messages", value=snapshot.pending_messages)
        metrics.set_gauge(
            "event_outbox_oldest_pending_seconds", value=snapshot.oldest_pending_seconds
        )
        if audit_outbox is not None:
            metrics.set_gauge(
                "event_audit_outbox_oldest_pending_seconds",
                value=audit_outbox.oldest_pending_seconds(now=datetime.now(UTC)),
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


class TrustedContextAppender:
    """Bind trusted service context around each intent and append it as evidence."""

    def __init__(self, service: AppendAuditEventService, *, retention_days: int) -> None:
        self._service = service
        self._retention_days = retention_days

    def append(self, intent: PendingAuditIntent) -> bool:
        # Retention derives from the outbox row's stable timestamp, never the delivery clock:
        # a retried delivery must produce byte-identical semantics so the audit store can
        # recognize it as the same evidence instead of a conflicting one.
        context = TrustedAuditContext(
            source_service=intent.source_service,
            actor_type=ActorType.SERVICE,
            retention_until=intent.recorded_at + timedelta(days=self._retention_days),
            school_id=intent.school_id,
        )
        outcome = self._service.append(dict(intent.payload), context)
        return outcome.duplicate


def build_dead_letter_hook(
    engine: sa.Engine, audit_outbox: PostgresAuditOutbox
) -> Callable[[PendingOutboxMessage], None]:
    """Audit-before-persist hook: enqueue dead-letter evidence or abort the transition."""

    def hook(message: PendingOutboxMessage) -> None:
        attempt = message.attempt_count + 1
        audit_outbox.record(
            AuditIntent(
                source_service="event-ingestion-service",
                source_event_id=uuid5(
                    NAMESPACE_URL,
                    f"camera-ai:dead-letter:{message.outbox_message_id}:{attempt}",
                ),
                action="EVENT_PROCESSING_DEAD_LETTERED",
                resource_type="event",
                resource_id=message.normalized_event_id,
                request_id=f"req_outbox_{message.outbox_message_id.hex}",
                result=IntentResult.FAILED,
                reason_code="EVENT_OUTBOX_PUBLISH_FAILED",
                occurred_at=datetime.now(UTC),
                school_id=school_for_event(engine, message.normalized_event_id),
                reference_ids=(
                    ("event_id", message.normalized_event_id),
                    ("outbox_id", message.outbox_message_id),
                ),
                count_summary=(("attempt_count", attempt),),
                policy_versions=(("event_contract", "normalized_outbox_v1"),),
            )
        )

    return hook


def build_consent_refusal_hook(
    engine: sa.Engine, audit_outbox: PostgresAuditOutbox
) -> Callable[[PendingOutboxMessage], None]:
    """Audit-before-persist hook for the consent fan-out guard (Issue #139).

    A pending message that reaches dispatch without an allow/not-required
    consent status is refused terminally; the deterministic intent identity
    keeps re-claimed replays from producing duplicate evidence.
    """

    def hook(message: PendingOutboxMessage) -> None:
        audit_outbox.record(
            AuditIntent(
                source_service=AUDIT_SOURCE_SERVICE,
                source_event_id=uuid5(
                    NAMESPACE_URL,
                    f"camera-ai:consent-refused:{message.outbox_message_id}",
                ),
                action=CONSENT_AUDIT_ACTION,
                resource_type="event",
                resource_id=message.normalized_event_id,
                request_id=f"req_outbox_{message.outbox_message_id.hex}",
                result=IntentResult.DENIED,
                reason_code=CONSENT_BLOCKED,
                occurred_at=datetime.now(UTC),
                school_id=school_for_event(engine, message.normalized_event_id),
                reference_ids=(
                    ("event_id", message.normalized_event_id),
                    ("outbox_id", message.outbox_message_id),
                ),
                policy_versions=(("consent_policy", CONSENT_GATE_POLICY_VERSION),),
            )
        )

    return hook


def main() -> int:
    settings = load_settings()
    worker: WorkerSettings = load_worker_settings()
    audit_settings = load_audit_delivery_settings()
    logger = configure_logging(settings.log_level, settings.environment)
    database = load_event_database_settings()
    audit_database = load_audit_database_settings()
    engine = sa.create_engine(
        database.database_url,
        pool_pre_ping=True,
        pool_size=worker.event_db_pool_size,
        max_overflow=worker.event_db_max_overflow,
        pool_timeout=worker.db_pool_timeout_seconds,
    )
    audit_engine = sa.create_engine(
        audit_database.database_url,
        pool_pre_ping=True,
        pool_size=worker.audit_db_pool_size,
        max_overflow=worker.audit_db_max_overflow,
        pool_timeout=worker.db_pool_timeout_seconds,
    )
    store = PostgresEventIngestionRepository(
        engine,
        scopes=DrainOnlyScopeResolver(),
        consent_gate=UnavailableConsentGate(),
        retention_days=_UNUSED_RETENTION_DAYS,
    )
    audit_outbox = PostgresAuditOutbox(engine)
    metrics = PrometheusMetricsSink()
    metrics_server = None
    if worker.metrics_port != 0:
        metrics_server = start_internal_metrics_server(metrics, port=worker.metrics_port)
    publisher = RabbitMqEventPublisher(worker.broker_url)
    event_drain = DrainOutboxBatch(
        store,
        publisher,
        metrics=metrics,
        batch_size=worker.batch_size,
        on_dead_letter=build_dead_letter_hook(engine, audit_outbox),
        on_consent_refused=build_consent_refusal_hook(engine, audit_outbox),
    )
    appender = TrustedContextAppender(
        AppendAuditEventService(
            SqlAlchemyAuditRepository(audit_engine),
            HmacSha256IntegritySigner(audit_settings.integrity_key),
        ),
        retention_days=audit_settings.retention_days,
    )
    audit_drain = DeliverAuditIntents(
        audit_outbox, appender, metrics=metrics, batch_size=worker.batch_size
    )
    housekeeping = build_housekeeping(store, metrics, logger, audit_outbox=audit_outbox)
    runner = WorkerRunner(
        CompositeDrain((event_drain, audit_drain)),
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
        audit_engine.dispose()
        engine.dispose()


if __name__ == "__main__":
    sys.exit(main())
