"""Process bootstrap: wire settings, event store, publisher, drain and runner.

The worker only drains the outbox: it never records events, never resolves scopes and never
touches retention. The event store's write-path collaborators are therefore wired fail-closed.
"""

from __future__ import annotations

import sys

import sqlalchemy as sa
from ansvis_adapter.application.outbox import DrainOutboxBatch
from ansvis_adapter.application.ports import AuthenticatedSource, EventScopeResolver
from ansvis_adapter.config import load_event_database_settings, load_settings
from ansvis_adapter.domain.errors import AnsvisAdapterError
from ansvis_adapter.domain.ingestion import ResolvedEventScope
from ansvis_adapter.domain.models import NormalizedAnsvisEvent
from ansvis_adapter.infrastructure.event_store import PostgresEventIngestionRepository

from event_outbox_worker.config import load_worker_settings
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


def main() -> int:
    settings = load_settings()
    worker = load_worker_settings()
    logger = configure_logging(settings.log_level, settings.environment)
    database = load_event_database_settings()
    engine = sa.create_engine(database.database_url, pool_pre_ping=True)
    store = PostgresEventIngestionRepository(
        engine,
        scopes=DrainOnlyScopeResolver(),
        retention_days=_UNUSED_RETENTION_DAYS,
    )
    publisher = RabbitMqEventPublisher(worker.broker_url)
    drain = DrainOutboxBatch(store, publisher, batch_size=worker.batch_size)
    runner = WorkerRunner(
        drain,
        publisher,
        logger=logger,
        idle_sleep_seconds=worker.idle_sleep_seconds,
        broker_retry_seconds=worker.broker_retry_seconds,
    )
    install_signal_handlers(runner)
    try:
        return runner.run()
    finally:
        publisher.close()
        engine.dispose()


if __name__ == "__main__":
    sys.exit(main())
