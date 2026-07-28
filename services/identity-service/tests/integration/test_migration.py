from __future__ import annotations

import os
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.engine import make_url

SERVICE_ROOT = Path(__file__).resolve().parents[2]


def _database_uri() -> str:
    raw = os.environ.get("IDENTITY_DATABASE_URI", "").strip()
    if not raw:
        pytest.skip("IDENTITY_DATABASE_URI is not set for an isolated integration database")
    url = make_url(raw)
    if (
        url.drivername != "postgresql+psycopg"
        or url.host not in {"127.0.0.1", "localhost"}
        or url.port != 55432
        or url.database != "Camera_AI_test"
    ):
        pytest.fail(
            "identity integration database must use postgresql+psycopg on "
            "loopback:55432 with exact database Camera_AI_test"
        )
    return raw


def test_identity_migration_applies_and_rolls_back_in_isolated_database() -> None:
    database_uri = _database_uri()
    config = Config(str(SERVICE_ROOT / "alembic.ini"))
    engine = sa.create_engine(database_uri)
    try:
        command.downgrade(config, "base")
        command.upgrade(config, "head")
        with engine.connect() as connection:
            table_names = set(sa.inspect(connection).get_table_names(schema="identity"))
        assert table_names == {
            "audit_outbox",
            "credentials",
            "mfa_factors",
            "refresh_tokens",
            "roles",
            "sessions",
            "user_role_assignments",
            "users",
        }

        command.downgrade(config, "base")
        with engine.connect() as connection:
            assert "identity" not in sa.inspect(connection).get_schema_names()
    finally:
        try:
            # Leave the isolated test database at the current schema even if an
            # assertion between downgrade and verification fails.
            command.upgrade(config, "head")
        finally:
            engine.dispose()
