from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError

SERVICE_ROOT = Path(__file__).resolve().parents[2]

EXPECTED_TABLES = {"audit_outbox", "evidence_links", "evidence_objects"}
FORBIDDEN_COLUMNS = {
    "image_binary",
    "video_binary",
    "image_base64",
    "signed_url",
    "upload_url",
    "object_key",
    "provider_version_id",
}


def _test_database_uri() -> str:
    raw_uri = os.environ.get("EVIDENCE_DATABASE_URI", "").strip()
    if not raw_uri:
        pytest.skip("EVIDENCE_DATABASE_URI is required for isolated evidence integration checks")
    url = make_url(raw_uri)
    database_name = (url.database or "").casefold()
    if (
        url.drivername != "postgresql+psycopg"
        or url.host not in {"127.0.0.1", "localhost"}
        or url.port in {None, 5432}
        or not database_name.endswith("_test")
    ):
        pytest.fail("evidence integration test requires an isolated loopback non-5432 *_test DB")
    return raw_uri


@contextmanager
def _redact_database_failures() -> Iterator[None]:
    try:
        yield
    except DBAPIError:
        pytest.fail(
            "isolated evidence database operation failed; connection details suppressed",
            pytrace=False,
        )


def test_database_failure_output_suppresses_driver_details() -> None:
    sensitive_marker = "synthetic-sensitive-driver-detail"

    with (
        pytest.raises(pytest.fail.Exception) as failure,
        _redact_database_failures(),
    ):
        raise sa.exc.OperationalError(
            "synthetic statement",
            {},
            RuntimeError(sensitive_marker),
        )

    assert sensitive_marker not in str(failure.value)
    assert str(failure.value) == (
        "isolated evidence database operation failed; connection details suppressed"
    )


def test_migration_applies_private_metadata_contract_and_downgrades_cleanly() -> None:
    database_uri = _test_database_uri()
    engine = sa.create_engine(database_uri, poolclass=sa.pool.NullPool)
    config = Config(str(SERVICE_ROOT / "alembic.ini"))
    upgraded = False
    with _redact_database_failures():
        try:
            command.downgrade(config, "base")
            assert inspect(engine).has_schema("evidence") is False
            command.upgrade(config, "head")
            upgraded = True

            inspector = inspect(engine)
            assert set(inspector.get_table_names(schema="evidence")) == EXPECTED_TABLES
            object_columns = {
                column["name"]
                for column in inspector.get_columns("evidence_objects", schema="evidence")
            }
            assert not object_columns & FORBIDDEN_COLUMNS
            assert {
                "object_key_ciphertext",
                "provider_version_ciphertext",
                "encryption_key_version_ref",
                "sha256",
                "captured_at",
                "received_at",
                "created_actor_id",
                "retention_expires_at",
                "retention_days",
                "legal_hold_state",
                "reconciliation_state",
                "upload_attempt_count",
                "reconciliation_attempt_count",
                "delete_attempt_count",
            } <= object_columns

            with pytest.raises(DBAPIError), engine.begin() as connection:
                connection.execute(
                    sa.text(
                        "INSERT INTO evidence.evidence_objects "
                        "(evidence_id, tenant_id, school_id, source_event_id, "
                        "captured_at, received_at, object_key_ciphertext, bucket_ref, "
                        "encryption_key_version_ref, media_kind, content_type, "
                        "original_extension, size_bytes, sensitivity, purpose_code, state, "
                        "scan_state, reconciliation_state, retention_policy_version, "
                        "retention_days, retention_expires_at, legal_hold_state, "
                        "created_actor_id, created_at, updated_at, row_version) "
                        "VALUES "
                        "('00000000-0000-4000-8000-000000006741', "
                        "'00000000-0000-4000-8000-000000006742', "
                        "'00000000-0000-4000-8000-000000006743', "
                        "'00000000-0000-4000-8000-000000006744', "
                        "now(), now(), decode('706c61696e74657874', 'hex'), "
                        "'evidence-private-v1', 'synthetic-kek-v1', "
                        "'image', 'image/png', 'png', 1024, 'critical', "
                        "'student_attendance', 'pending_upload', 'pending', 'pending', "
                        "'attendance_retention_v1', 30, now() + interval '30 days', "
                        "'none', '00000000-0000-4000-8000-000000006745', "
                        "now(), now(), 1)"
                    )
                )

            command.downgrade(config, "base")
            upgraded = False
            assert inspect(engine).has_schema("evidence") is False
        finally:
            if upgraded:
                command.downgrade(config, "base")
            engine.dispose()
