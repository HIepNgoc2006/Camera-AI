from __future__ import annotations

import os

from alembic import context
from report_service.infrastructure.tables import metadata
from sqlalchemy import engine_from_config, pool

config = context.config
database_uri = os.getenv("REPORT_DATABASE_URI")
if database_uri:
    config.set_main_option("sqlalchemy.url", database_uri)

if context.is_offline_mode():
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section) or {},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=metadata)
        with context.begin_transaction():
            context.run_migrations()
