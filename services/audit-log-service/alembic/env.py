"""Alembic environment for the Audit Log Service-owned schema."""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from audit_log_service.config import load_database_settings
from sqlalchemy import Connection, Engine, create_engine, pool

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = None
VERSION_TABLE = "alembic_version_audit_log_service"


def _configure(connection: Connection | None = None) -> None:
    settings = load_database_settings()
    options: dict[str, object] = {
        "target_metadata": target_metadata,
        "compare_type": True,
        "version_table": VERSION_TABLE,
    }
    if connection is None:
        options.update(
            {
                "url": settings.database_url,
                "literal_binds": True,
                "dialect_opts": {"paramstyle": "named"},
            }
        )
    else:
        options["connection"] = connection
    context.configure(**options)


def run_migrations_offline() -> None:
    """Render SQL without opening a database connection."""

    _configure()
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations using the injected PostgreSQL URL without logging it."""

    settings = load_database_settings()
    connectable: Engine = create_engine(settings.database_url, poolclass=pool.NullPool)
    try:
        with connectable.connect() as connection:
            _configure(connection)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
