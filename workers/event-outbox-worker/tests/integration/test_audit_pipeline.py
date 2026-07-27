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
from ansvis_adapter.application.outbox import DrainOutboxBatch
from ansvis_adapter.application.ports import AuthenticatedSource
from ansvis_adapter.domain.consent import ConsentGateDecision, ConsentGateRequest, ConsentGateStatus
from ansvis_adapter.domain.ingestion import ResolvedEventScope
from ansvis_adapter.infrastructure.audit_outbox import PostgresAuditOutbox
from ansvis_adapter.infrastructure.event_store import PostgresEventIngestionRepository
from ansvis_adapter.infrastructure.idempotency import ContractIdempotencyDeriver
from ansvis_adapter.schemas.events import parse_and_normalize_event
from audit_log_service.application.service import AppendAuditEventService
from audit_log_service.infrastructure.integrity import HmacSha256IntegritySigner
from audit_log_service.infrastructure.repository import SqlAlchemyAuditRepository
from camera_ai_audit import AuditIntent, IntentResult
from event_outbox_worker.__main__ import TrustedContextAppender, build_consent_refusal_hook
from event_outbox_worker.audit_delivery import DeliverAuditIntents
from sqlalchemy.engine import make_url

REPO_ROOT = Path(__file__).resolve().parents[4]
ADAPTER_ROOT = REPO_ROOT / "services" / "ansvis-adapter"
AUDIT_ROOT = REPO_ROOT / "services" / "audit-log-service"
SIGNING_KEY = b"synthetic-audit-integrity-key-32b!"
EVENT_ID = UUID("00000000-0000-4000-8000-000000000911")
CONSENT_NOW = datetime(2026, 7, 27, 9, 30, tzinfo=UTC)
CONSENT_SCHOOL_ID = UUID("00000000-0000-4000-8000-000000000921")
CONSENT_SOURCE_ID = UUID("00000000-0000-4000-8000-000000000922")
CONSENT_CAMERA_ID = UUID("00000000-0000-4000-8000-000000000923")
CONSENT_TASK_ID = UUID("00000000-0000-4000-8000-000000000924")

CONSENT_SOURCE = AuthenticatedSource(
    source_namespace="ansvis.test.source",
    subject_ref="source_subject_test_0001",
    tenant_ref="tenant_test_0001",
    school_ref="school_test_0001",
)


class ConsentScopes:
    def resolve(self, event: object, source: AuthenticatedSource) -> ResolvedEventScope:
        del event, source
        return ResolvedEventScope(
            school_id=CONSENT_SCHOOL_ID,
            source_id=CONSENT_SOURCE_ID,
            camera_id=CONSENT_CAMERA_ID,
            task_id=CONSENT_TASK_ID,
            verified=True,
        )


class ConsentPrimaryOnlyKeys:
    def key_for(self, version: str) -> bytes | None:
        raise AssertionError(f"unexpected fallback key request for {version}")


class FixedGate:
    def __init__(self, decision: ConsentGateDecision) -> None:
        self.decision = decision

    def evaluate(self, request: ConsentGateRequest) -> ConsentGateDecision:
        del request
        return self.decision


class ConfirmingPublisher:
    def publish(self, *, topic: str, payload: object) -> None:
        del topic, payload


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


def denial_intent_b() -> AuditIntent:
    return AuditIntent(
        source_service="ansvis-adapter-service",
        source_event_id=UUID("00000000-0000-4000-8000-000000000912"),
        action="ANSVIS_SOURCE_AUTH_DENIED",
        resource_type="ansvis_source",
        request_id="req_test_audit_pipeline_0002",
        result=IntentResult.DENIED,
        reason_code="EVENT_AUTH_TOKEN_INVALID",
        occurred_at=datetime(2026, 7, 26, 13, 5, tzinfo=UTC),
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

        # A retried delivery of the SAME leased row is duplicate-as-success:
        # identical semantics, one evidence row, no conflict and no error.
        assert outbox.claim_batch(now=datetime.now(UTC), limit=1) == ()
        second = denial_intent_b()
        outbox.record(second)
        (leased,) = outbox.claim_batch(now=datetime.now(UTC), limit=1)
        assert appender.append(leased) is False
        assert appender.append(leased) is True  # simulated redelivery after a crash
        outbox.mark_delivered_batch(
            [(leased.audit_outbox_id, leased.claim_token)],
            delivered_at=datetime.now(UTC),
        )
        with audit_engine.connect() as connection:
            total = connection.execute(
                sa.text("SELECT count(*) FROM audit.audit_events")
            ).scalar_one()
        assert total == 2
    finally:
        if upgraded:
            command.downgrade(audit_config, "base")
            command.downgrade(adapter_config, "base")
        audit_engine.dispose()
        event_engine.dispose()


def test_consent_denial_evidence_flows_from_gate_and_guard_to_audit_store() -> None:
    """Issue #139: blocked ingestion and guard refusal both land as immutable
    EVENT_CONSENT_DENIED evidence through the authoritative action policy."""

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

        deriver = ContractIdempotencyDeriver(fallback_keys=ConsentPrimaryOnlyKeys())

        def face_payload(marker: str) -> dict[str, object]:
            return {
                "schema_version": "ansvis_http_trigger_v1",
                "source_namespace": "ansvis.test.source",
                "source_event_id": f"event_test_consent_{marker}",
                "event_type": "attendance.face.observed",
                "tenant_ref": "tenant_test_0001",
                "school_ref": "school_test_0001",
                "camera_external_id": "camera_test_0001",
                "task_external_id": "task_test_0001",
                "event_time": "2026-07-27T09:30:00Z",
                "correlation_id": f"corr_test_consent_{marker}",
                "attributes": {
                    "subject_external_id": "synthetic_subject_reference",
                    "confidence": 0.9,
                    "model_version": "face_model_v1",
                    "config_version": "camera_config_v1",
                },
            }

        blocked_store = PostgresEventIngestionRepository(
            event_engine,
            scopes=ConsentScopes(),
            consent_gate=FixedGate(
                ConsentGateDecision(
                    status=ConsentGateStatus.BLOCKED,
                    reason_code="CONSENT_WITHDRAWN",
                    policy_version="consent_policy_v1",
                )
            ),
            retention_days=30,
            now=lambda: CONSENT_NOW,
        )
        blocked_event = parse_and_normalize_event(face_payload("blocked"))
        blocked_store.record(
            blocked_event, CONSENT_SOURCE, deriver.derive(blocked_event, CONSENT_SOURCE)
        )

        allowed_store = PostgresEventIngestionRepository(
            event_engine,
            scopes=ConsentScopes(),
            consent_gate=FixedGate(
                ConsentGateDecision(
                    status=ConsentGateStatus.ALLOWED,
                    reason_code="CONSENT_ALLOWED",
                    policy_version="consent_policy_v1",
                )
            ),
            retention_days=30,
            now=lambda: CONSENT_NOW,
        )
        legacy_event = parse_and_normalize_event(face_payload("legacy"))
        allowed_store.record(
            legacy_event, CONSENT_SOURCE, deriver.derive(legacy_event, CONSENT_SOURCE)
        )
        with event_engine.begin() as connection:
            connection.execute(
                sa.text(
                    "UPDATE events.outbox_messages SET payload = jsonb_set("
                    "payload, '{consent_gate_status}', '\"not_evaluated\"'::jsonb, true)"
                )
            )

        audit_outbox = PostgresAuditOutbox(event_engine)
        drain = DrainOutboxBatch(
            allowed_store,
            ConfirmingPublisher(),
            now=lambda: CONSENT_NOW,
            jitter=lambda _: 0,
            on_consent_refused=build_consent_refusal_hook(event_engine, audit_outbox),
        )
        result = drain.execute()
        assert result.claimed == 1
        assert result.refused == 1

        appender = TrustedContextAppender(
            AppendAuditEventService(
                SqlAlchemyAuditRepository(audit_engine),
                HmacSha256IntegritySigner(SIGNING_KEY),
            ),
            retention_days=1_825,
        )
        audit_drain = DeliverAuditIntents(audit_outbox, appender)
        delivered = audit_drain.execute()
        assert delivered.claimed == 2
        assert delivered.published == 2
        assert audit_drain.execute().empty is True

        with audit_engine.connect() as connection:
            rows = (
                connection.execute(
                    sa.text(
                        "SELECT source_service, action, result, reason_code, school_id,"
                        " purpose_code FROM audit.audit_events ORDER BY occurred_at, reason_code"
                    )
                )
                .mappings()
                .all()
            )
        assert len(rows) == 2
        reasons = {row["reason_code"] for row in rows}
        assert reasons == {"CONSENT_WITHDRAWN", "EVENT_CONSENT_BLOCKED"}
        for row in rows:
            assert row["source_service"] == "event-ingestion-service"
            assert row["action"] == "EVENT_CONSENT_DENIED"
            assert row["result"] == "denied"
            assert row["school_id"] == CONSENT_SCHOOL_ID
    finally:
        if upgraded:
            command.downgrade(audit_config, "base")
            command.downgrade(adapter_config, "base")
        audit_engine.dispose()
        event_engine.dispose()
