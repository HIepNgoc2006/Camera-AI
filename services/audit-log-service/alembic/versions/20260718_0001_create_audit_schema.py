"""Create the append-only Audit Log Service schema.

Revision ID: 20260718_0001
Revises:
Create Date: 2026-07-18 00:00:00+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260718_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = ("audit_log_service",)
depends_on: str | Sequence[str] | None = None

SCHEMA = "audit"


def _create_table() -> None:
    op.create_table(
        "audit_events",
        sa.Column(
            "audit_event_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("school_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "event_schema_version",
            sa.SmallInteger(),
            nullable=False,
            server_default=sa.text("1"),
        ),
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
        sa.Column(
            "changes",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("integrity_partition", sa.Text(), nullable=False),
        sa.Column(
            "hash_version",
            sa.SmallInteger(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column("previous_event_hash", postgresql.BYTEA(), nullable=True),
        sa.Column("event_hash", postgresql.BYTEA(), nullable=False),
        sa.Column("retention_until", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("event_schema_version = 1", name="ck_audit_events_schema_version"),
        sa.CheckConstraint("hash_version = 1", name="ck_audit_events_hash_version"),
        sa.CheckConstraint(
            "source_service ~ '^[a-z][a-z0-9-]{1,62}[a-z0-9]$'",
            name="ck_audit_events_source_service",
        ),
        sa.CheckConstraint(
            "source_event_id ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'",
            name="ck_audit_events_source_event_id",
        ),
        sa.CheckConstraint(
            "correlation_id IS NULL OR correlation_id ~ '^cor_[A-Za-z0-9_-]{8,120}$'",
            name="ck_audit_events_correlation_id",
        ),
        sa.CheckConstraint(
            "actor_type IN ('user', 'service', 'system')", name="ck_audit_events_actor_type"
        ),
        sa.CheckConstraint(
            "actor_type <> 'user' OR actor_id IS NOT NULL",
            name="ck_audit_events_user_actor_id",
        ),
        sa.CheckConstraint(
            "actor_role IS NULL OR actor_role ~ '^[a-z][a-z0-9_.:-]{0,63}$'",
            name="ck_audit_events_actor_role",
        ),
        sa.CheckConstraint("action ~ '^[A-Z][A-Z0-9_]{2,95}$'", name="ck_audit_events_action"),
        sa.CheckConstraint(
            "purpose_code IS NULL OR purpose_code ~ '^[a-z][a-z0-9_.:-]{0,63}$'",
            name="ck_audit_events_purpose_code",
        ),
        sa.CheckConstraint(
            "resource_type ~ '^[a-z][a-z0-9_.:-]{0,63}$'",
            name="ck_audit_events_resource_type",
        ),
        sa.CheckConstraint(
            "resource_id IS NULL OR resource_ref IS NULL",
            name="ck_audit_events_resource_identity",
        ),
        sa.CheckConstraint(
            "resource_ref IS NULL OR resource_ref ~ '^[a-z][a-z0-9_.:-]{0,127}$'",
            name="ck_audit_events_resource_ref",
        ),
        sa.CheckConstraint(
            "request_id ~ '^req_[A-Za-z0-9_-]{8,120}$'", name="ck_audit_events_request_id"
        ),
        sa.CheckConstraint(
            "result IN ('success', 'denied', 'failed')", name="ck_audit_events_result"
        ),
        sa.CheckConstraint(
            "reason_code IS NULL OR reason_code ~ '^[A-Z][A-Z0-9_]{1,63}$'",
            name="ck_audit_events_reason_code",
        ),
        sa.CheckConstraint(
            "ip_prefix IS NULL OR (family(ip_prefix) = 4 AND masklen(ip_prefix) <= 24) "
            "OR (family(ip_prefix) = 6 AND masklen(ip_prefix) <= 48)",
            name="ck_audit_events_ip_prefix",
        ),
        sa.CheckConstraint(
            "user_agent_family IS NULL OR user_agent_family ~ '^[a-z][a-z0-9_.:-]{0,63}$'",
            name="ck_audit_events_user_agent_family",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(changes) = 'object' AND octet_length(changes::text) <= 16384",
            name="ck_audit_events_changes",
        ),
        sa.CheckConstraint(
            "integrity_partition ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}:[0-9]{2}$'",
            name="ck_audit_events_integrity_partition",
        ),
        sa.CheckConstraint(
            "previous_event_hash IS NULL OR octet_length(previous_event_hash) = 32",
            name="ck_audit_events_previous_hash",
        ),
        sa.CheckConstraint("octet_length(event_hash) = 32", name="ck_audit_events_event_hash"),
        sa.CheckConstraint(
            "retention_until > recorded_at", name="ck_audit_events_retention_window"
        ),
        sa.UniqueConstraint(
            "source_service", "source_event_id", name="uq_audit_events_source_identity"
        ),
        schema=SCHEMA,
    )


def _create_indexes() -> None:
    op.create_index(
        "ix_audit_events_school_occurred",
        "audit_events",
        ["school_id", sa.text("occurred_at DESC")],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_audit_events_actor_occurred",
        "audit_events",
        ["actor_id", sa.text("occurred_at DESC")],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_audit_events_resource_id_occurred",
        "audit_events",
        ["resource_type", "resource_id", sa.text("occurred_at DESC")],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_audit_events_resource_ref_occurred",
        "audit_events",
        ["resource_type", "resource_ref", sa.text("occurred_at DESC")],
        schema=SCHEMA,
        postgresql_where=sa.text("resource_ref IS NOT NULL"),
    )
    op.create_index(
        "ix_audit_events_action_result_occurred",
        "audit_events",
        ["action", "result", sa.text("occurred_at DESC")],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_audit_events_integrity_order",
        "audit_events",
        ["integrity_partition", "recorded_at", "audit_event_id"],
        unique=True,
        schema=SCHEMA,
    )
    op.create_index(
        "ix_audit_events_retention_until",
        "audit_events",
        ["retention_until"],
        schema=SCHEMA,
    )


def _protect_append_only_boundary() -> None:
    op.execute(
        sa.text(
            """
            CREATE FUNCTION audit.reject_audit_event_mutation()
            RETURNS trigger
            LANGUAGE plpgsql
            SECURITY INVOKER
            SET search_path = pg_catalog
            AS $audit$
            BEGIN
                RAISE EXCEPTION USING
                    ERRCODE = '42501',
                    MESSAGE = 'audit events are append-only';
            END;
            $audit$
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE TRIGGER audit_events_reject_update_delete
            BEFORE UPDATE OR DELETE ON audit.audit_events
            FOR EACH ROW EXECUTE FUNCTION audit.reject_audit_event_mutation()
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE TRIGGER audit_events_reject_truncate
            BEFORE TRUNCATE ON audit.audit_events
            FOR EACH STATEMENT EXECUTE FUNCTION audit.reject_audit_event_mutation()
            """
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE audit.audit_events ENABLE ALWAYS TRIGGER audit_events_reject_update_delete"
        )
    )
    op.execute(
        sa.text("ALTER TABLE audit.audit_events ENABLE ALWAYS TRIGGER audit_events_reject_truncate")
    )
    op.execute(sa.text("REVOKE CREATE ON SCHEMA audit FROM PUBLIC"))
    op.execute(sa.text("REVOKE UPDATE, DELETE, TRUNCATE ON audit.audit_events FROM PUBLIC"))


def upgrade() -> None:
    op.execute(sa.schema.CreateSchema(SCHEMA))
    _create_table()
    _create_indexes()
    _protect_append_only_boundary()


def downgrade() -> None:
    op.drop_table("audit_events", schema=SCHEMA)
    op.execute(sa.text("DROP FUNCTION audit.reject_audit_event_mutation()"))
    op.execute(sa.schema.DropSchema(SCHEMA))
