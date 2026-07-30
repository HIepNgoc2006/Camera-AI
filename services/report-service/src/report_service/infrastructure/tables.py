"""SQLAlchemy reporting schema tables."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

metadata = sa.MetaData(schema="reporting")

report_aggregates = sa.Table(
    "report_aggregates",
    metadata,
    sa.Column("aggregate_id", postgresql.UUID(as_uuid=True), primary_key=True),
    sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("school_id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("class_id", postgresql.UUID(as_uuid=True), nullable=True),
    sa.Column("report_type", sa.Text(), nullable=False),
    sa.Column("category_code", sa.Text(), nullable=False),
    sa.Column("sample_count", sa.Integer(), nullable=False),
    sa.Column("value_count", sa.Integer(), nullable=True),
    sa.Column("suppressed", sa.Boolean(), nullable=False, server_default=sa.true()),
    sa.Column("policy_version", sa.Text(), nullable=False),
    sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
    sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
    sa.Column("retention_until", sa.DateTime(timezone=True), nullable=False),
)

report_exports = sa.Table(
    "report_exports",
    metadata,
    sa.Column("export_id", postgresql.UUID(as_uuid=True), primary_key=True),
    sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("scope_fingerprint", sa.LargeBinary(), nullable=False),
    sa.Column("report_type", sa.Text(), nullable=False),
    sa.Column("reason_code", sa.Text(), nullable=False),
    sa.Column("format_code", sa.Text(), nullable=False),
    sa.Column("state", sa.Text(), nullable=False),
    sa.Column("row_count", sa.Integer(), nullable=True),
    sa.Column("artifact_ref", postgresql.UUID(as_uuid=True), nullable=True),
    sa.Column("idempotency_key", sa.Text(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.UniqueConstraint("tenant_id", "idempotency_key", name="uq_report_exports_idempotency"),
)

audit_outbox = sa.Table(
    "audit_outbox",
    metadata,
    sa.Column("audit_outbox_id", postgresql.UUID(as_uuid=True), primary_key=True),
    sa.Column("source_event_id", postgresql.UUID(as_uuid=True), nullable=False, unique=True),
    sa.Column("payload", postgresql.JSONB(), nullable=False),
    sa.Column("publish_status", sa.Text(), nullable=False, server_default="pending"),
    sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
)
