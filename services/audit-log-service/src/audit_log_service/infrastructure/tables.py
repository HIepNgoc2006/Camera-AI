"""Audit Log Service-owned SQLAlchemy table metadata."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

metadata = sa.MetaData(schema="audit")

audit_events = sa.Table(
    "audit_events",
    metadata,
    sa.Column("audit_event_id", postgresql.UUID(as_uuid=True), primary_key=True),
    sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("school_id", postgresql.UUID(as_uuid=True), nullable=True),
    sa.Column("event_schema_version", sa.SmallInteger(), nullable=False),
    sa.Column("source_service", sa.Text(), nullable=False),
    sa.Column("source_event_id", sa.Text(), nullable=False),
    sa.Column("correlation_id", sa.Text(), nullable=True),
    sa.Column("actor_type", sa.Text(), nullable=False),
    sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
    sa.Column("actor_role", sa.Text(), nullable=True),
    sa.Column("action", sa.Text(), nullable=False),
    sa.Column("purpose_code", sa.Text(), nullable=True),
    sa.Column("resource_type", sa.Text(), nullable=False),
    sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=True),
    sa.Column("resource_ref", sa.Text(), nullable=True),
    sa.Column("request_id", sa.Text(), nullable=False),
    sa.Column("result", sa.Text(), nullable=False),
    sa.Column("reason_code", sa.Text(), nullable=True),
    sa.Column("ip_prefix", postgresql.INET(), nullable=True),
    sa.Column("user_agent_family", sa.Text(), nullable=True),
    sa.Column("changes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column("integrity_partition", sa.Text(), nullable=False),
    sa.Column("hash_version", sa.SmallInteger(), nullable=False),
    sa.Column("previous_event_hash", postgresql.BYTEA(), nullable=True),
    sa.Column("event_hash", postgresql.BYTEA(), nullable=False),
    sa.Column("retention_until", sa.DateTime(timezone=True), nullable=False),
)
