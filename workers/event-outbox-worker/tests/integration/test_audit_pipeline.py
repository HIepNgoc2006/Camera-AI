"""End-to-end audit delivery: intent enqueue -> trusted append -> immutable evidence.

Requires the isolated CI/test PostgreSQL (both URIs may point at the same *_test database).
All identifiers and keys are synthetic.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from ansvis_adapter.infrastructure.audit_outbox import PendingAuditIntent, PostgresAuditOutbox
from audit_log_service.application.service import AppendAuditEventService
from audit_log_service.infrastructure.integrity import HmacSha256IntegritySigner
from audit_log_service.infrastructure.repository import SqlAlchemyAuditRepository
from camera_ai_audit import AuditIntent, IntentResult
from event_outbox_worker.__main__ import TrustedContextAppender
from event_outbox_worker.audit_delivery import DeliverAuditIntents
from sqlalchemy.engine import make_url

REPO_ROOT = Path(__file__).resolve().parents[4]
ADAPTER_ROOT = REPO_ROOT / "services" / "ansvis-adapter"
AUDIT_ROOT = REPO_ROOT / "services" / "audit-log-service"
SIGNING_KEY = b"synthetic-audit-integrity-key-32b!"
EVENT_ID = UUID("00000000-0000-4000-8000-000000000911")


def _database_uri(name: str) -> str:
    raw_uri = os.environ.get(name, "").strip()
    if not raw_uri:
        pytest.skip(f"{name} is required for audit pipeline verification")
    url = make_url(raw_uri)
    if (
        url.drivername != "postgresql+psycopg"
        or url.host not in {"127.0.0.1", "localhost"}
        or url.port in {None, 5432}
        or not (url.database or "").casefold().endswith("_test")
    ):
        pytest.fail(f"{name} must be an isolated loopback non-5432 *_test database")
    return raw_uri


def denial_intent() -> AuditIntent:
    return AuditIntent(
        source_service="ansvis-adapter-service",
        source_event_id=EVENT_ID,
        action="ANSVIS_SOURCE_AUTH_DENIED",
        resource_type="ansvis_source",
        request_id="req_test_audit_pipeline_0001",
        result=IntentResult.DENIED,
        reason_code="EVENT_SOURCE_UNAUTHORIZED",
        occurred_at=datetime(2026, 7, 26, 13, 0, tzinfo=UTC),
    )


def test_intent_flows_into_immutable_audit_evidence_exactly_once() -> None:
    event_uri = _database_uri("EVENT_DATABASE_URI")
    audit_uri = _database_uri("AUDIT_DATABASE_URI")
    event_engine = sa.create_engine(event_uri, poolclass=sa.pool.NullPool)
    audit_engine = sa.create_engine(audit_uri, poolclass=sa.pool.NullPool)
    adapter_config = Config(str(ADAPTER_ROOT / "alembic.ini"))
    audit_config = Config(str(AUDIT_ROOT / "alembic.ini"))
    upgraded = False
    try:
        command.downgrade(adapter_config, "base")
        command.downgrade(audit_config, "base")
        command.upgrade(adapter_config, "head")
        command.upgrade(audit_config, "head")
        upgraded = True

        outbox = PostgresAuditOutbox(event_engine)
        outbox.record(denial_intent())
        outbox.record(denial_intent())  # replay is a no-op, not a second row
        with event_engine.connect() as connection:
            pending = connection.execute(
                sa.text("SELECT count(*) FROM events.audit_outbox")
            ).scalar_one()
        assert pending == 1

        appender = TrustedContextAppender(
            AppendAuditEventService(
                SqlAlchemyAuditRepository(audit_engine),
                HmacSha256IntegritySigner(SIGNING_KEY),
            ),
            retention_days=1_825,
        )
        drain = DeliverAuditIntents(outbox, appender)

        first = drain.execute()
        assert first.claimed == 1 and first.published == 1
        assert drain.execute().empty is True

        with audit_engine.connect() as connection:
            row = (
                connection.execute(
                    sa.text(
                        "SELECT source_service, action, result, reason_code, school_id"
                        " FROM audit.audit_events"
                    )
                )
                .mappings()
                .one()
            )
        assert row["source_service"] == "ansvis-adapter-service"
        assert row["action"] == "ANSVIS_SOURCE_AUTH_DENIED"
        assert row["result"] == "denied"
        assert row["reason_code"] == "EVENT_SOURCE_UNAUTHORIZED"
        assert row["school_id"] is None

        # A re-appended intent is duplicate-as-success: one evidence row, no error.
        claimed = outbox.claim_batch(now=datetime.now(UTC), limit=1)
        assert claimed == ()  # already delivered; nothing pending
        assert appender.append(_redeliver_view()) is True
        with audit_engine.connect() as connection:
            total = connection.execute(
                sa.text("SELECT count(*) FROM audit.audit_events")
            ).scalar_one()
        assert total == 1
    finally:
        if upgraded:
            command.downgrade(audit_config, "base")
            command.downgrade(adapter_config, "base")
        audit_engine.dispose()
        event_engine.dispose()


def _redeliver_view() -> PendingAuditIntent:
    from uuid import uuid4

    intent = denial_intent()
    return PendingAuditIntent(
        audit_outbox_id=uuid4(),
        claim_token=uuid4(),
        source_service=intent.source_service,
        source_event_id=intent.source_event_id,
        school_id=None,
        payload=intent.publisher_payload(),
        attempt_count=0,
        recorded_at=datetime.now(UTC),
    )
