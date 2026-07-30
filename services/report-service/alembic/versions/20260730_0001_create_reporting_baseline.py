"""Create fail-closed reporting and export baseline."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260730_0001"
down_revision = None
branch_labels = None
depends_on = None
SCHEMA = "reporting"


def upgrade() -> None:
    op.execute(sa.schema.CreateSchema(SCHEMA))
    op.create_table(
        "report_aggregates",
        sa.Column("aggregate_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("school_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("class_id", postgresql.UUID(as_uuid=True)),
        sa.Column("report_type", sa.Text(), nullable=False),
        sa.Column("category_code", sa.Text(), nullable=False),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column("value_count", sa.Integer()),
        sa.Column("suppressed", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("policy_version", sa.Text(), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("retention_until", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "sample_count >= 0 AND (suppressed OR value_count IS NOT NULL)",
            name="ck_report_aggregate_suppression",
        ),
        schema=SCHEMA,
    )
    op.create_table(
        "report_exports",
        sa.Column("export_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scope_fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("report_type", sa.Text(), nullable=False),
        sa.Column("reason_code", sa.Text(), nullable=False),
        sa.Column("format_code", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("row_count", sa.Integer()),
        sa.Column("artifact_ref", postgresql.UUID(as_uuid=True)),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "octet_length(scope_fingerprint) = 32", name="ck_report_export_scope_fingerprint"
        ),
        sa.CheckConstraint("format_code IN ('csv','json')", name="ck_report_export_format"),
        sa.CheckConstraint(
            "state IN ('queued','generating','available','failed','expired')",
            name="ck_report_export_state",
        ),
        sa.CheckConstraint(
            "(state = 'available') = (artifact_ref IS NOT NULL)", name="ck_report_export_artifact"
        ),
        sa.CheckConstraint(
            "expires_at = created_at + interval '7 days'", name="ck_report_export_ttl"
        ),
        sa.UniqueConstraint("tenant_id", "idempotency_key", name="uq_report_exports_idempotency"),
        schema=SCHEMA,
    )
    op.create_table(
        "audit_outbox",
        sa.Column("audit_outbox_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_event_id", postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("publish_status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "NOT (payload ?| ARRAY['content','subject_id','artifact_ref','signed_url','object_key','credential']::text[])",
            name="ck_report_audit_payload",
        ),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("audit_outbox", schema=SCHEMA)
    op.drop_table("report_exports", schema=SCHEMA)
    op.drop_table("report_aggregates", schema=SCHEMA)
    op.execute(sa.schema.DropSchema(SCHEMA))
