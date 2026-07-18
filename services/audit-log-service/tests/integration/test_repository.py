from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from audit_log_service.application.service import AppendAuditEventService
from audit_log_service.domain.errors import AuditError
from audit_log_service.domain.models import ActorType, TrustedAuditContext
from audit_log_service.infrastructure.repository import SqlAlchemyAuditRepository
from sqlalchemy import Engine, inspect
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError

SERVICE_ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)
SCHOOL_ID = UUID("00000000-0000-4000-8000-000000000101")
ACTOR_ID = UUID("00000000-0000-4000-8000-000000000102")
EXPECTED_COLUMNS = {
    "audit_event_id",
    "occurred_at",
    "recorded_at",
    "school_id",
    "event_schema_version",
    "source_service",
    "source_event_id",
    "correlation_id",
    "actor_type",
    "actor_id",
    "actor_role",
    "action",
    "purpose_code",
    "resource_type",
    "resource_id",
    "resource_ref",
    "request_id",
    "result",
    "reason_code",
    "ip_prefix",
    "user_agent_family",
    "changes",
    "integrity_partition",
    "hash_version",
    "previous_event_hash",
    "event_hash",
    "retention_until",
}
EXPECTED_INDEXES = {
    "ix_audit_events_action_result_occurred",
    "ix_audit_events_actor_occurred",
    "ix_audit_events_integrity_order",
    "ix_audit_events_resource_id_occurred",
    "ix_audit_events_resource_ref_occurred",
    "ix_audit_events_retention_until",
    "ix_audit_events_school_occurred",
    "uq_audit_events_source_identity",
}
EXPECTED_CHECKS = {
    "ck_audit_events_action",
    "ck_audit_events_actor_role",
    "ck_audit_events_actor_type",
    "ck_audit_events_changes",
    "ck_audit_events_correlation_id",
    "ck_audit_events_event_hash",
    "ck_audit_events_hash_version",
    "ck_audit_events_integrity_partition",
    "ck_audit_events_ip_prefix",
    "ck_audit_events_previous_hash",
    "ck_audit_events_purpose_code",
    "ck_audit_events_reason_code",
    "ck_audit_events_request_id",
    "ck_audit_events_resource_identity",
    "ck_audit_events_resource_ref",
    "ck_audit_events_resource_type",
    "ck_audit_events_result",
    "ck_audit_events_retention_window",
    "ck_audit_events_schema_version",
    "ck_audit_events_source_event_id",
    "ck_audit_events_source_service",
    "ck_audit_events_user_actor_id",
    "ck_audit_events_user_agent_family",
}


class FakeSigner:
    def sign(self, message: bytes) -> bytes:
        return sha256(b"fake-test-signer\0" + message).digest()


def _test_database_uri() -> str:
    raw_uri = os.environ.get("AUDIT_DATABASE_URI", "").strip()
    if not raw_uri:
        pytest.skip("AUDIT_DATABASE_URI is required for isolated audit integration verification")

    url = make_url(raw_uri)
    database_name = (url.database or "").casefold()
    if (
        url.drivername != "postgresql+psycopg"
        or url.host not in {"127.0.0.1", "localhost"}
        or url.port in {None, 5432}
        or not database_name.endswith("_test")
    ):
        pytest.fail("audit integration test requires an isolated loopback non-5432 *_test DB")
    return raw_uri


def _alembic_config() -> Config:
    return Config(str(SERVICE_ROOT / "alembic.ini"))


def _context() -> TrustedAuditContext:
    return TrustedAuditContext(
        source_service="identity-service",
        actor_type=ActorType.USER,
        actor_id=ACTOR_ID,
        actor_role="system_admin",
        school_id=SCHOOL_ID,
        retention_until=NOW + timedelta(days=30),
    )


def _payload(source_event_id: UUID, resource_id: UUID, request_suffix: str) -> dict[str, object]:
    return {
        "event_schema_version": 1,
        "source_service": "identity-service",
        "source_event_id": str(source_event_id),
        "correlation_id": f"cor_{request_suffix}",
        "action": "ROLE_ASSIGNMENT_CHANGED",
        "resource_type": "role_assignment",
        "resource_id": str(resource_id),
        "request_id": f"req_{request_suffix}",
        "result": "success",
        "occurred_at": NOW.isoformat(),
        "ip_prefix": "192.0.2.0/24",
        "user_agent_family": "service_client",
        "changes": {
            "schema_version": "audit_changes_v1",
            "changed_fields": ["status"],
            "state_before_codes": {"status": "pending"},
            "state_after_codes": {"status": "active"},
            "reference_ids": {"role_id": str(resource_id)},
            "policy_versions": {"rbac_policy": "rbac_v1"},
        },
    }


def _assert_inventory(engine: Engine) -> None:
    inspector = inspect(engine)
    assert inspector.has_schema("audit")
    assert inspector.get_table_names(schema="audit") == ["audit_events"]
    columns = {column["name"] for column in inspector.get_columns("audit_events", schema="audit")}
    assert columns == EXPECTED_COLUMNS
    indexes = {index["name"] for index in inspector.get_indexes("audit_events", schema="audit")}
    assert indexes == EXPECTED_INDEXES
    unique_constraints = {
        constraint["name"]
        for constraint in inspector.get_unique_constraints("audit_events", schema="audit")
    }
    assert unique_constraints == {"uq_audit_events_source_identity"}
    checks = {
        constraint["name"]
        for constraint in inspector.get_check_constraints("audit_events", schema="audit")
    }
    assert checks == EXPECTED_CHECKS
    primary_key = inspector.get_pk_constraint("audit_events", schema="audit")
    assert primary_key["name"] == "audit_events_pkey"
    assert primary_key["constrained_columns"] == ["audit_event_id"]
    assert inspector.get_foreign_keys("audit_events", schema="audit") == []
    assert inspector.get_view_names(schema="audit") == []

    with engine.connect() as connection:
        triggers = set(
            connection.scalars(
                sa.text(
                    "SELECT tgname FROM pg_trigger "
                    "WHERE tgrelid = 'audit.audit_events'::regclass AND NOT tgisinternal"
                )
            )
        )
        functions = set(
            connection.scalars(
                sa.text(
                    "SELECT p.proname FROM pg_proc p "
                    "JOIN pg_namespace n ON n.oid = p.pronamespace "
                    "WHERE n.nspname = 'audit'"
                )
            )
        )
    assert triggers == {"audit_events_reject_update_delete", "audit_events_reject_truncate"}
    assert functions == {"reject_audit_event_mutation"}


def test_migration_append_idempotency_chain_and_tamper_detection() -> None:
    database_uri = _test_database_uri()
    engine = sa.create_engine(database_uri, poolclass=sa.pool.NullPool)
    config = _alembic_config()
    upgraded = False
    try:
        command.downgrade(config, "base")
        assert inspect(engine).has_schema("audit") is False

        command.upgrade(config, "head")
        upgraded = True
        _assert_inventory(engine)

        repository = SqlAlchemyAuditRepository(engine)
        signer = FakeSigner()
        service = AppendAuditEventService(repository, signer, clock=lambda: NOW)
        # UUIDv7 publisher identities must remain valid opaque IDs.
        source_event_id = UUID("0190f4c7-6d42-7000-8000-000000000201")
        resource_id = UUID("00000000-0000-4000-8000-000000000301")
        payload = _payload(source_event_id, resource_id, "0123456789abcdef")

        first = service.append(payload, _context())
        duplicate = service.append(payload, _context())
        assert first.duplicate is False
        assert duplicate.duplicate is True
        assert duplicate.event.audit_event_id == first.event.audit_event_id

        conflict = dict(payload)
        conflict["request_id"] = "req_fedcba9876543210"
        with pytest.raises(AuditError, match="AUDIT_DUPLICATE_CONFLICT"):
            service.append(conflict, _context())

        concurrent_inputs = (
            _payload(uuid4(), uuid4(), "1111111111111111"),
            _payload(uuid4(), uuid4(), "2222222222222222"),
        )
        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(
                executor.map(lambda item: service.append(item, _context()), concurrent_inputs)
            )
        assert all(not outcome.duplicate for outcome in outcomes)

        partition = first.event.integrity_partition
        repository.verify_partition(partition, signer)
        with engine.connect() as connection:
            count = connection.scalar(sa.text("SELECT count(*) FROM audit.audit_events"))
        assert count == 3

        with pytest.raises(DBAPIError), engine.begin() as connection:
            connection.execute(
                sa.text(
                    "UPDATE audit.audit_events SET result = 'failed' "
                    "WHERE audit_event_id = :audit_event_id"
                ),
                {"audit_event_id": first.event.audit_event_id},
            )
        with pytest.raises(DBAPIError), engine.begin() as connection:
            connection.execute(
                sa.text("DELETE FROM audit.audit_events WHERE audit_event_id = :audit_event_id"),
                {"audit_event_id": first.event.audit_event_id},
            )

        with engine.begin() as connection:
            connection.execute(
                sa.text(
                    "ALTER TABLE audit.audit_events "
                    "DISABLE TRIGGER audit_events_reject_update_delete"
                )
            )
            connection.execute(
                sa.text(
                    "UPDATE audit.audit_events SET event_hash = :tampered "
                    "WHERE audit_event_id = :audit_event_id"
                ),
                {"tampered": bytes([1]) * 32, "audit_event_id": first.event.audit_event_id},
            )
            connection.execute(
                sa.text(
                    "ALTER TABLE audit.audit_events "
                    "ENABLE ALWAYS TRIGGER audit_events_reject_update_delete"
                )
            )
        with pytest.raises(AuditError, match="AUDIT_INTEGRITY_FAILED"):
            repository.verify_partition(partition, signer)

        command.downgrade(config, "base")
        upgraded = False
        assert inspect(engine).has_schema("audit") is False
    finally:
        if upgraded:
            command.downgrade(config, "base")
        engine.dispose()
