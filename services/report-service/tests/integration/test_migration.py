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
EXPECTED_TABLES = {"audit_outbox", "report_aggregates", "report_exports"}
FORBIDDEN_COLUMNS = {
    "student_id",
    "subject_id",
    "student_name",
    "image_base64",
    "signed_url",
    "object_key",
    "export_content",
}


def _test_database_uri() -> str:
    raw_uri = os.environ.get("REPORT_DATABASE_URI", "").strip()
    if not raw_uri:
        pytest.skip("REPORT_DATABASE_URI is required for isolated report integration checks")
    url = make_url(raw_uri)
    database_name = (url.database or "").casefold()
    if (
        url.drivername != "postgresql+psycopg"
        or url.host not in {"127.0.0.1", "localhost"}
        or url.port in {None, 5432}
        or not database_name.endswith("_test")
    ):
        pytest.fail("report integration test requires an isolated loopback non-5432 *_test DB")
    return raw_uri


@contextmanager
def _redact_database_failures() -> Iterator[None]:
    try:
        yield
    except DBAPIError:
        pytest.fail(
            "isolated report database operation failed; connection details suppressed",
            pytrace=False,
        )


def test_database_failure_output_suppresses_driver_details() -> None:
    marker = "synthetic-sensitive-driver-detail"
    with pytest.raises(pytest.fail.Exception) as failure, _redact_database_failures():
        raise sa.exc.OperationalError("synthetic statement", {}, RuntimeError(marker))
    assert marker not in str(failure.value)


def test_migration_applies_constraints_downgrades_and_reapplies() -> None:
    database_uri = _test_database_uri()
    engine = sa.create_engine(database_uri, poolclass=sa.pool.NullPool)
    config = Config(str(SERVICE_ROOT / "alembic.ini"))
    with _redact_database_failures():
        try:
            command.downgrade(config, "base")
            assert inspect(engine).has_schema("reporting") is False
            command.upgrade(config, "head")
            inspector = inspect(engine)
            assert set(inspector.get_table_names(schema="reporting")) == EXPECTED_TABLES
            columns = {
                column["name"]
                for column in inspector.get_columns("report_exports", schema="reporting")
            }
            assert not columns & FORBIDDEN_COLUMNS
            assert {"scope_fingerprint", "artifact_ref", "expires_at", "reason_code"} <= columns

            with pytest.raises(DBAPIError), engine.begin() as connection:
                connection.execute(
                    sa.text(
                        "INSERT INTO reporting.report_exports "
                        "(export_id, tenant_id, actor_id, scope_fingerprint, report_type, "
                        "reason_code, format_code, state, idempotency_key, created_at, "
                        "expires_at, updated_at) VALUES "
                        "('00000000-0000-4000-8000-000000006601', "
                        "'00000000-0000-4000-8000-000000006602', "
                        "'00000000-0000-4000-8000-000000006603', "
                        "decode(repeat('00', 32), 'hex'), 'attendance_summary', "
                        "'MANAGEMENT_REPORT', 'csv', 'available', "
                        "'fixture-key-0000000000000001', now(), now() + interval '7 days', now())"
                    )
                )

            command.downgrade(config, "base")
            assert inspect(engine).has_schema("reporting") is False
            command.upgrade(config, "head")
            assert inspect(engine).has_schema("reporting") is True
        finally:
            engine.dispose()
