"""Create the audit-intent transport outbox owned by the adapter.

This is a transport table (Issue #138), not audit evidence: rows carry shape-validated
AuditEventV1 publisher payloads until the delivery worker appends them to the owning
audit-log-service. Delivered rows keep their terminal status for reconciliation; the immutable
evidence lives only in `audit.audit_events`.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260726_0002"
down_revision: str | Sequence[str] | None = "20260721_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audit_outbox",
        sa.Column("audit_outbox_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_service", sa.Text(), nullable=False),
        sa.Column("source_event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("school_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("publish_status", sa.Text(), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claim_token", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("claim_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.Text(), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "source_service", "source_event_id", name="uq_events_audit_outbox_source"
        ),
        sa.CheckConstraint(
            "source_service ~ '^[a-z][a-z0-9-]{1,62}[a-z0-9]$'",
            name="ck_events_audit_outbox_service",
        ),
        sa.CheckConstraint(
            "publish_status IN ('pending', 'delivered', 'failed')",
            name="ck_events_audit_outbox_status",
        ),
        sa.CheckConstraint(
            "attempt_count >= 0 AND attempt_count <= 5",
            name="ck_events_audit_outbox_attempts",
        ),
        sa.CheckConstraint(
            "payload ? 'event_schema_version' AND payload ? 'action'"
            " AND payload ? 'source_event_id' AND payload ? 'request_id'"
            " AND payload ? 'result' AND payload ? 'occurred_at'"
            " AND NOT (payload ? 'image_base64') AND NOT (payload ? 'face_embedding')"
            " AND NOT (payload ? 'token') AND NOT (payload ? 'message')",
            name="ck_events_audit_outbox_payload_shape",
        ),
        schema="events",
    )
    op.create_index(
        "ix_events_audit_outbox_status_due",
        "audit_outbox",
        ["publish_status", "next_attempt_at", "recorded_at"],
        schema="events",
    )


def downgrade() -> None:
    op.drop_index("ix_events_audit_outbox_status_due", table_name="audit_outbox", schema="events")
    op.drop_table("audit_outbox", schema="events")
