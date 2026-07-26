from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from ansvis_adapter.application.outbox import DispatchOutboxMessage, DrainOutboxBatch
from ansvis_adapter.application.ports import AuthenticatedSource, ReceiptOutcome
from ansvis_adapter.domain.errors import AnsvisAdapterError
from ansvis_adapter.domain.ingestion import DispatchOutcome, ReplayAuthorization, ResolvedEventScope
from ansvis_adapter.infrastructure.event_store import PostgresEventIngestionRepository
from ansvis_adapter.infrastructure.idempotency import ContractIdempotencyDeriver
from ansvis_adapter.schemas.events import parse_and_normalize_event
from sqlalchemy import Engine, inspect
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError

SERVICE_ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 7, 21, 10, 0, tzinfo=UTC)
SCHOOL_ID = UUID("00000000-0000-4000-8000-000000000621")
SOURCE_ID = UUID("00000000-0000-4000-8000-000000000622")
CAMERA_ID = UUID("00000000-0000-4000-8000-000000000623")
TASK_ID = UUID("00000000-0000-4000-8000-000000000624")
ZONE_ID = UUID("00000000-0000-4000-8000-000000000625")
ACTOR_ID = UUID("00000000-0000-4000-8000-000000000626")
EXPECTED_TABLES = {
    "event_detections",
    "ingestion_receipts",
    "normalized_events",
    "outbox_messages",
    "processing_attempts",
}
FORBIDDEN_PAYLOAD_MARKERS = (
    "authorization",
    "base64",
    "face_embedding",
    "face_image",
    "media_url",
    "password",
    "raw_payload",
    "rtsp_url",
    "subject_external_id",
)


def _test_database_uri() -> str:
    raw_uri = os.environ.get("EVENT_DATABASE_URI", "").strip()
    if not raw_uri:
        pytest.skip("EVENT_DATABASE_URI is required for isolated event-store verification")
    url = make_url(raw_uri)
    database_name = (url.database or "").casefold()
    if (
        url.drivername != "postgresql+psycopg"
        or url.host not in {"127.0.0.1", "localhost"}
        or url.port in {None, 5432}
        or not database_name.endswith("_test")
    ):
        pytest.fail("event-store integration test requires an isolated loopback non-5432 *_test DB")
    return raw_uri


def _alembic_config() -> Config:
    return Config(str(SERVICE_ROOT / "alembic.ini"))


def _event_payload(*, source_event_id: str, correlation_id: str) -> dict[str, object]:
    return {
        "schema_version": "ansvis_http_trigger_v1",
        "source_namespace": "ansvis.test.source",
        "source_event_id": source_event_id,
        "event_type": "attendance.face.observed",
        "tenant_ref": "tenant_test_0001",
        "school_ref": "school_test_0001",
        "camera_external_id": "camera_test_0001",
        "task_external_id": "task_test_0001",
        "event_time": "2026-07-21T10:00:00Z",
        "correlation_id": correlation_id,
        "attributes": {
            "track_id": "track_test_0001",
            "detection_key": "detection_test_0001",
            "subject_external_id": "synthetic_subject_reference",
            "confidence": 0.875,
            "model_version": "face_model_v1",
            "config_version": "camera_config_v1",
            "detection_count": 1,
        },
    }


SOURCE = AuthenticatedSource(
    source_namespace="ansvis.test.source",
    subject_ref="source_subject_test_0001",
    tenant_ref="tenant_test_0001",
    school_ref="school_test_0001",
)


class PrimaryOnlyKeys:
    def key_for(self, version: str) -> bytes | None:
        raise AssertionError(f"unexpected fallback key request for {version}")


class StaticScopes:
    def resolve(self, event: object, source: AuthenticatedSource) -> ResolvedEventScope:
        if source != SOURCE:
            raise AnsvisAdapterError("EVENT_SOURCE_MAPPING_DENIED")
        return ResolvedEventScope(
            school_id=SCHOOL_ID,
            source_id=SOURCE_ID,
            camera_id=CAMERA_ID,
            task_id=TASK_ID,
            verified=True,
            zone_id=ZONE_ID,
        )


class FailingScopes:
    def resolve(self, event: object, source: AuthenticatedSource) -> ResolvedEventScope:
        raise RuntimeError("synthetic registry detail must stay masked")


class TogglePublisher:
    def __init__(self, *, fail: bool) -> None:
        self.fail = fail
        self.published: list[tuple[str, object]] = []

    def publish(self, *, topic: str, payload: object) -> None:
        if self.fail:
            raise RuntimeError("synthetic broker detail must stay masked")
        self.published.append((topic, payload))


class MutableClock:
    def __init__(self, value: datetime) -> None:
        self.value = value

    def __call__(self) -> datetime:
        return self.value


def _inventory(engine: Engine) -> None:
    inspector = inspect(engine)
    assert inspector.has_schema("events")
    assert set(inspector.get_table_names(schema="events")) == EXPECTED_TABLES
    for table in EXPECTED_TABLES:
        for foreign_key in inspector.get_foreign_keys(table, schema="events"):
            assert foreign_key["referred_schema"] == "events"


def test_event_store_migration_idempotency_quarantine_outbox_and_minimization() -> None:
    database_uri = _test_database_uri()
    engine = sa.create_engine(database_uri, poolclass=sa.pool.NullPool)
    config = _alembic_config()
    upgraded = False
    try:
        command.downgrade(config, "base")
        assert inspect(engine).has_schema("events") is False
        command.upgrade(config, "head")
        upgraded = True
        _inventory(engine)

        event = parse_and_normalize_event(
            _event_payload(
                source_event_id="event_test_ingestion_0001",
                correlation_id="corr_test_ingestion_0001",
            )
        )
        deriver = ContractIdempotencyDeriver(fallback_keys=PrimaryOnlyKeys())
        descriptor = deriver.derive(event, SOURCE)
        repository = PostgresEventIngestionRepository(
            engine,
            scopes=StaticScopes(),
            retention_days=30,
            now=lambda: NOW,
        )

        receipts = [repository.record(event, SOURCE, descriptor) for _ in range(10)]
        assert receipts[0].outcome is ReceiptOutcome.ACCEPTED
        assert all(receipt.outcome is ReceiptOutcome.DUPLICATE for receipt in receipts[1:])
        assert len({receipt.receipt_id for receipt in receipts}) == 1

        with engine.connect() as connection:
            counts = (
                connection.execute(
                    sa.text(
                        "SELECT "
                        "(SELECT count(*) FROM events.ingestion_receipts) AS receipts, "
                        "(SELECT count(*) FROM events.normalized_events) AS normalized, "
                        "(SELECT count(*) FROM events.event_detections) AS detections, "
                        "(SELECT count(*) FROM events.outbox_messages) AS outbox"
                    )
                )
                .mappings()
                .one()
            )
            outbox_row = (
                connection.execute(
                    sa.text("SELECT outbox_message_id, payload FROM events.outbox_messages")
                )
                .mappings()
                .one()
            )
        assert counts == {"receipts": 1, "normalized": 1, "detections": 1, "outbox": 1}
        stored_payload = outbox_row["payload"]
        serialized_payload = json.dumps(stored_payload, sort_keys=True).casefold()
        assert stored_payload["schema_version"] == "normalized_outbox_v1"
        assert stored_payload["metadata"]["schema_version"] == "event_metadata_v1"
        assert all(marker not in serialized_payload for marker in FORBIDDEN_PAYLOAD_MARKERS)

        conflict_event = replace(
            event,
            attributes=replace(event.attributes, confidence=0.5),
        )
        conflict_descriptor = deriver.derive(conflict_event, SOURCE)
        with pytest.raises(AnsvisAdapterError) as conflict:
            repository.record(conflict_event, SOURCE, conflict_descriptor)
        assert conflict.value.code == "EVENT_IDEMPOTENCY_CONFLICT"
        with engine.connect() as connection:
            conflict_attempt = (
                connection.execute(
                    sa.text(
                        "SELECT result, error_code FROM events.processing_attempts "
                        "WHERE consumer = 'ingestion-conflict'"
                    )
                )
                .mappings()
                .one()
            )
        assert conflict_attempt == {
            "result": "dead_lettered",
            "error_code": "EVENT_IDEMPOTENCY_CONFLICT",
        }

        clock = MutableClock(NOW)
        failing_publisher = TogglePublisher(fail=True)
        dispatcher = DispatchOutboxMessage(
            repository,
            failing_publisher,
            now=clock,
            jitter=lambda _: 0,
        )
        for delay in (5, 10, 20, 40):
            assert dispatcher.execute() is DispatchOutcome.RETRY_SCHEDULED
            assert dispatcher.execute() is DispatchOutcome.EMPTY
            clock.value += timedelta(seconds=delay)
        assert dispatcher.execute() is DispatchOutcome.DEAD_LETTERED
        assert "synthetic broker detail" not in str(dispatcher.execute())

        outbox_message_id = outbox_row["outbox_message_id"]
        authorization = ReplayAuthorization(
            actor_id=ACTOR_ID,
            reason_code="OPERATOR_REVIEWED",
            approved=True,
            authorized_at=clock.value,
        )
        dispatcher.replay(outbox_message_id, authorization)
        publisher = TogglePublisher(fail=False)
        published = DispatchOutboxMessage(
            repository,
            publisher,
            now=clock,
            jitter=lambda _: 0,
        ).execute()
        assert published is DispatchOutcome.PUBLISHED
        assert len(publisher.published) == 1

        concurrent_event = replace(
            event,
            source_event_id="event_test_ingestion_0002",
            correlation_id="corr_test_ingestion_0002",
        )
        concurrent_descriptor = deriver.derive(concurrent_event, SOURCE)

        def ingest_concurrently(_: int) -> ReceiptOutcome:
            return repository.record(concurrent_event, SOURCE, concurrent_descriptor).outcome

        with ThreadPoolExecutor(max_workers=8) as executor:
            outcomes = list(executor.map(ingest_concurrently, range(8)))
        assert outcomes.count(ReceiptOutcome.ACCEPTED) == 1
        assert outcomes.count(ReceiptOutcome.DUPLICATE) == 7

        unmapped_event = replace(
            event,
            source_event_id="event_test_ingestion_unmapped",
            correlation_id="corr_test_ingestion_unmapped",
        )
        unmapped_descriptor = deriver.derive(unmapped_event, SOURCE)
        denied_repository = PostgresEventIngestionRepository(
            engine,
            scopes=FailingScopes(),
            retention_days=30,
            now=lambda: NOW,
        )
        with pytest.raises(AnsvisAdapterError) as denied:
            denied_repository.record(unmapped_event, SOURCE, unmapped_descriptor)
        assert denied.value.code == "EVENT_SOURCE_MAPPING_DENIED"
        assert "synthetic registry detail" not in str(denied.value)

        with engine.connect() as connection:
            final_counts = (
                connection.execute(
                    sa.text(
                        "SELECT "
                        "(SELECT count(*) FROM events.ingestion_receipts) AS receipts, "
                        "(SELECT count(*) FROM events.normalized_events) AS normalized, "
                        "(SELECT count(*) FROM events.outbox_messages) AS outbox, "
                        "(SELECT count(*) FROM events.processing_attempts "
                        " WHERE consumer = 'outbox-publisher') AS publish_attempts, "
                        "(SELECT count(*) FROM events.processing_attempts "
                        " WHERE consumer = 'outbox-replay') AS replays"
                    )
                )
                .mappings()
                .one()
            )
        assert final_counts == {
            "receipts": 2,
            "normalized": 2,
            "outbox": 2,
            "publish_attempts": 5,
            "replays": 1,
        }
        operational = repository.snapshot(now=clock.value)
        assert operational.accepted_receipts == 2
        assert operational.pending_messages == 1
        assert operational.published_messages == 1
        assert operational.failed_messages == 0
        assert operational.retryable_attempts == 4
        assert operational.quarantined_conflicts == 1
        assert operational.delayed_messages == 0
        assert operational.oldest_pending_seconds == 75

        with pytest.raises(DBAPIError), engine.begin() as connection:
            connection.execute(
                sa.text(
                    "UPDATE events.outbox_messages "
                    "SET payload = payload || CAST(:unsafe AS jsonb) "
                    "WHERE outbox_message_id = :message_id"
                ),
                {
                    "unsafe": json.dumps({"raw_payload": "synthetic-forbidden-value"}),
                    "message_id": outbox_message_id,
                },
            )
        with pytest.raises(DBAPIError), engine.begin() as connection:
            connection.execute(
                sa.text(
                    "UPDATE events.ingestion_receipts SET result = 'duplicate' "
                    "WHERE ingestion_receipt_id = "
                    "(SELECT ingestion_receipt_id FROM events.ingestion_receipts LIMIT 1)"
                )
            )

        command.downgrade(config, "base")
        upgraded = False
        assert inspect(engine).has_schema("events") is False
    finally:
        if upgraded:
            command.downgrade(config, "base")
        engine.dispose()


def test_outbox_batch_claim_lease_isolation_and_batch_acknowledgement() -> None:
    """Batch drain against a real database: ordering, lease isolation, batch ack, recovery."""

    database_uri = _test_database_uri()
    engine = sa.create_engine(database_uri, poolclass=sa.pool.NullPool)
    config = _alembic_config()
    upgraded = False
    seeded = 60
    try:
        command.downgrade(config, "base")
        command.upgrade(config, "head")
        upgraded = True

        clock = MutableClock(NOW)
        repository = PostgresEventIngestionRepository(
            engine,
            scopes=StaticScopes(),
            retention_days=30,
            now=clock,
        )
        deriver = ContractIdempotencyDeriver(fallback_keys=PrimaryOnlyKeys())
        for index in range(seeded):
            clock.value = NOW + timedelta(seconds=index)
            event = parse_and_normalize_event(
                _event_payload(
                    source_event_id=f"event_test_batch_{index:04d}",
                    correlation_id=f"corr_test_batch_{index:04d}",
                )
            )
            receipt = repository.record(event, SOURCE, deriver.derive(event, SOURCE))
            assert receipt.outcome is ReceiptOutcome.ACCEPTED

        claim_time = NOW + timedelta(seconds=seeded)

        # Bounds are enforced before any SQL runs.
        with pytest.raises(ValueError, match="1..50"):
            repository.claim_batch(now=claim_time, limit=0)
        with pytest.raises(ValueError, match="1..50"):
            repository.claim_batch(now=claim_time, limit=51)

        first = repository.claim_batch(now=claim_time, limit=50)
        assert len(first) == 50
        second = repository.claim_batch(now=claim_time, limit=50)
        assert len(second) == 10  # leased rows are invisible to a concurrent claimer
        assert {m.outbox_message_id for m in first}.isdisjoint(
            {m.outbox_message_id for m in second}
        )

        # A foreign confirmation pair must fail the whole batch acknowledgement.
        with pytest.raises(AnsvisAdapterError, match="EVENT_DURABLE_RECEIPT_UNAVAILABLE"):
            repository.mark_published_batch(
                [(first[0].outbox_message_id, second[0].claim_token)],
                published_at=claim_time,
            )

        repository.mark_published_batch(
            [(message.outbox_message_id, message.claim_token) for message in first],
            published_at=claim_time,
        )

        # An expired lease is reclaimable; an active one is not.
        assert repository.claim_batch(now=claim_time, limit=50) == ()
        recovered = repository.claim_batch(now=claim_time + timedelta(seconds=31), limit=50)
        assert len(recovered) == 10
        repository.mark_published_batch(
            [(message.outbox_message_id, message.claim_token) for message in recovered],
            published_at=claim_time + timedelta(seconds=31),
        )

        with engine.connect() as connection:
            statuses = (
                connection.execute(
                    sa.text(
                        "SELECT publish_status, count(*) AS total"
                        " FROM events.outbox_messages GROUP BY publish_status"
                    )
                )
                .mappings()
                .all()
            )
        assert {row["publish_status"]: row["total"] for row in statuses} == {"published": seeded}

        # End-to-end drain use case over a fresh backlog, one poison message included.
        for index in range(seeded, seeded + 12):
            clock.value = NOW + timedelta(seconds=index)
            event = parse_and_normalize_event(
                _event_payload(
                    source_event_id=f"event_test_batch_{index:04d}",
                    correlation_id=f"corr_test_batch_{index:04d}",
                )
            )
            repository.record(event, SOURCE, deriver.derive(event, SOURCE))

        publisher = TogglePublisher(fail=False)
        drain = DrainOutboxBatch(
            repository,
            publisher,
            now=lambda: NOW + timedelta(seconds=200),
            jitter=lambda maximum: 0,
        )
        result = drain.execute()
        assert result.claimed == 12
        assert result.published == 12
        assert result.retry_scheduled == 0
        assert len(publisher.published) == 12
        assert drain.execute().empty is True
    finally:
        if upgraded:
            command.downgrade(config, "base")
        engine.dispose()
