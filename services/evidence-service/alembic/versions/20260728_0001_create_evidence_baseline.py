"""Create the private Evidence Storage metadata baseline.

Revision ID: 20260728_0001_evidence
Revises: None
Create Date: 2026-07-28 00:00:00+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from camera_ai_crypto import encv1_check_constraint
from sqlalchemy.dialects import postgresql

revision: str = "20260728_0001_evidence"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "evidence"


def _create_objects() -> None:
    key_constraint, key_sql = encv1_check_constraint("evidence_objects", "object_key_ciphertext")
    version_constraint, version_sql = encv1_check_constraint(
        "evidence_objects", "provider_version_ciphertext"
    )
    op.create_table(
        "evidence_objects",
        sa.Column("evidence_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("school_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("camera_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("object_key_ciphertext", postgresql.BYTEA(), nullable=False),
        sa.Column("bucket_ref", sa.Text(), nullable=False),
        sa.Column("provider_version_ciphertext", postgresql.BYTEA(), nullable=True),
        sa.Column("encryption_key_version_ref", sa.Text(), nullable=False),
        sa.Column("media_kind", sa.Text(), nullable=False),
        sa.Column("content_type", sa.Text(), nullable=False),
        sa.Column("original_extension", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.Text(), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.BigInteger(), nullable=True),
        sa.Column("sensitivity", sa.Text(), nullable=False),
        sa.Column("purpose_code", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("scan_state", sa.Text(), nullable=False),
        sa.Column("upload_attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_upload_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_upload_error_code", sa.Text(), nullable=True),
        sa.Column(
            "reconciliation_state",
            sa.Text(),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "reconciliation_attempt_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("next_reconciliation_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_reconciliation_error_code", sa.Text(), nullable=True),
        sa.Column("last_reconciled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retention_policy_version", sa.Text(), nullable=False),
        sa.Column("retention_days", sa.Integer(), nullable=False),
        sa.Column("retention_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("legal_hold_state", sa.Text(), nullable=False),
        sa.Column("legal_hold_ref", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("delete_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delete_attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_delete_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_delete_error_code", sa.Text(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deletion_reason_code", sa.Text(), nullable=True),
        sa.Column("deletion_job_ref", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("deletion_request_id", sa.Text(), nullable=True),
        sa.Column("deletion_correlation_id", sa.Text(), nullable=True),
        sa.Column("row_version", sa.BigInteger(), nullable=False, server_default="1"),
        sa.CheckConstraint(key_sql, name=key_constraint),
        sa.CheckConstraint(
            f"provider_version_ciphertext IS NULL OR ({version_sql})",
            name=version_constraint,
        ),
        sa.CheckConstraint(
            "bucket_ref = 'evidence-private-v1'",
            name="ck_evidence_objects_bucket_ref",
        ),
        sa.CheckConstraint(
            "encryption_key_version_ref ~ '^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$'",
            name="ck_evidence_objects_key_version",
        ),
        sa.CheckConstraint(
            "media_kind IN ('image', 'video')",
            name="ck_evidence_objects_media_kind",
        ),
        sa.CheckConstraint(
            "content_type IN ('image/jpeg', 'image/png', 'image/webp', 'video/mp4')",
            name="ck_evidence_objects_content_type",
        ),
        sa.CheckConstraint(
            "(content_type = 'image/jpeg' AND original_extension IN ('jpg', 'jpeg'))"
            " OR (content_type = 'image/png' AND original_extension = 'png')"
            " OR (content_type = 'image/webp' AND original_extension = 'webp')"
            " OR (content_type = 'video/mp4' AND original_extension = 'mp4')",
            name="ck_evidence_objects_extension",
        ),
        sa.CheckConstraint(
            "(media_kind = 'image' AND size_bytes BETWEEN 1 AND 10485760)"
            " OR (media_kind = 'video' AND size_bytes BETWEEN 1 AND 262144000)",
            name="ck_evidence_objects_size",
        ),
        sa.CheckConstraint(
            "sha256 IS NULL OR sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_evidence_objects_sha256",
        ),
        sa.CheckConstraint(
            "(width IS NULL AND height IS NULL)"
            " OR (width BETWEEN 1 AND 32768 AND height BETWEEN 1 AND 32768)",
            name="ck_evidence_objects_dimensions",
        ),
        sa.CheckConstraint(
            "(media_kind = 'image' AND duration_ms IS NULL)"
            " OR (media_kind = 'video' AND (duration_ms IS NULL OR duration_ms BETWEEN 1 AND 86400000))",
            name="ck_evidence_objects_duration",
        ),
        sa.CheckConstraint(
            "sensitivity IN ('high', 'critical')",
            name="ck_evidence_objects_sensitivity",
        ),
        sa.CheckConstraint(
            "state IN ('pending_upload', 'quarantined', 'available', 'delete_pending',"
            " 'deleted', 'missing', 'failed')",
            name="ck_evidence_objects_state",
        ),
        sa.CheckConstraint(
            "scan_state IN ('pending', 'clean', 'rejected', 'unavailable')",
            name="ck_evidence_objects_scan_state",
        ),
        sa.CheckConstraint(
            "reconciliation_state IN ('pending', 'matched', 'orphan', 'missing', 'failed')",
            name="ck_evidence_objects_reconciliation",
        ),
        sa.CheckConstraint(
            "upload_attempt_count BETWEEN 0 AND 5"
            " AND reconciliation_attempt_count BETWEEN 0 AND 5"
            " AND delete_attempt_count BETWEEN 0 AND 5",
            name="ck_evidence_objects_retry_counts",
        ),
        sa.CheckConstraint(
            "(next_upload_attempt_at IS NULL) = (last_upload_error_code IS NULL)"
            " AND (next_reconciliation_at IS NULL) ="
            " (last_reconciliation_error_code IS NULL)"
            " AND (next_delete_attempt_at IS NULL) = (last_delete_error_code IS NULL)",
            name="ck_evidence_objects_retry_state",
        ),
        sa.CheckConstraint(
            "legal_hold_state IN ('none', 'active', 'unavailable')"
            " AND (legal_hold_state = 'active') = (legal_hold_ref IS NOT NULL)",
            name="ck_evidence_objects_legal_hold",
        ),
        sa.CheckConstraint(
            "captured_at <= received_at AND received_at <= created_at"
            " AND retention_expires_at > created_at AND updated_at >= created_at",
            name="ck_evidence_objects_timestamps",
        ),
        sa.CheckConstraint(
            "retention_days IN (15, 30, 180, 365)"
            " AND retention_expires_at <= created_at + make_interval(days => retention_days)",
            name="ck_evidence_objects_retention_days",
        ),
        sa.CheckConstraint(
            "(deletion_reason_code IS NULL AND deletion_job_ref IS NULL"
            " AND deletion_request_id IS NULL AND deletion_correlation_id IS NULL)"
            " OR (deletion_reason_code ~ '^[A-Z][A-Z0-9_]{2,63}$'"
            " AND deletion_job_ref IS NOT NULL"
            " AND deletion_request_id ~ '^req_[A-Za-z0-9_-]{8,120}$'"
            " AND deletion_correlation_id ~ '^cor_[A-Za-z0-9_-]{8,120}$')",
            name="ck_evidence_objects_deletion_metadata",
        ),
        sa.CheckConstraint(
            "(state NOT IN ('quarantined', 'available', 'delete_pending', 'deleted')"
            " OR (sha256 IS NOT NULL AND provider_version_ciphertext IS NOT NULL))"
            " AND (state != 'available' OR scan_state = 'clean')"
            " AND (state = 'delete_pending') = (delete_requested_at IS NOT NULL AND deleted_at IS NULL)"
            " AND (state = 'deleted') = (deleted_at IS NOT NULL)"
            " AND (state IN ('delete_pending', 'deleted')) = (deletion_reason_code IS NOT NULL)",
            name="ck_evidence_objects_lifecycle",
        ),
        sa.CheckConstraint(
            "row_version >= 1",
            name="ck_evidence_objects_row_version",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "school_id",
            "evidence_id",
            name="uq_evidence_objects_scope",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_evidence_objects_school_state_retention",
        "evidence_objects",
        ["school_id", "state", "retention_expires_at"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_evidence_objects_source_event",
        "evidence_objects",
        ["tenant_id", "source_event_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_evidence_objects_reconciliation",
        "evidence_objects",
        ["reconciliation_state", "last_reconciled_at"],
        schema=SCHEMA,
    )


def _create_links() -> None:
    op.create_table(
        "evidence_links",
        sa.Column("link_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("evidence_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("school_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("resource_type", sa.Text(), nullable=False),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("link_purpose", sa.Text(), nullable=False),
        sa.Column("sequence_role", sa.Text(), nullable=False),
        sa.Column("sequence_index", sa.Integer(), nullable=False),
        sa.Column("selection_policy_version", sa.Text(), nullable=False),
        sa.Column("linked_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id", "school_id", "evidence_id"],
            [
                "evidence.evidence_objects.tenant_id",
                "evidence.evidence_objects.school_id",
                "evidence.evidence_objects.evidence_id",
            ],
            name="fk_evidence_links_scoped_object",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "resource_type ~ '^[a-z][a-z0-9_.:-]{0,95}$'"
            " AND link_purpose ~ '^[a-z][a-z0-9_.:-]{0,95}$'"
            " AND sequence_role ~ '^[a-z][a-z0-9_.:-]{0,95}$'",
            name="ck_evidence_links_codes",
        ),
        sa.CheckConstraint(
            "sequence_index BETWEEN 0 AND 99",
            name="ck_evidence_links_sequence",
        ),
        sa.CheckConstraint(
            "selection_policy_version = 'evidence_selection_policy_v1'",
            name="ck_evidence_links_policy",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "resource_type",
            "resource_id",
            "link_purpose",
            "sequence_index",
            name="uq_evidence_links_order",
        ),
        sa.UniqueConstraint(
            "evidence_id",
            "resource_type",
            "resource_id",
            "link_purpose",
            name="uq_evidence_links_object_resource",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_evidence_links_resource_order",
        "evidence_links",
        ["tenant_id", "school_id", "resource_type", "resource_id", "sequence_index"],
        schema=SCHEMA,
    )


def _create_audit_outbox() -> None:
    op.create_table(
        "audit_outbox",
        sa.Column("audit_outbox_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_service", sa.Text(), nullable=False),
        sa.Column("source_event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("school_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("publish_status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "source_service = 'evidence-storage-service'",
            name="ck_evidence_audit_outbox_service",
        ),
        sa.CheckConstraint(
            "publish_status IN ('pending', 'delivered', 'failed')",
            name="ck_evidence_audit_outbox_status",
        ),
        sa.CheckConstraint(
            "attempt_count BETWEEN 0 AND 5",
            name="ck_evidence_audit_outbox_attempts",
        ),
        sa.CheckConstraint(
            "payload ? 'event_schema_version' AND payload ? 'action'"
            " AND payload ? 'source_event_id' AND payload ? 'request_id'"
            " AND payload ? 'result' AND payload ? 'occurred_at'"
            " AND NOT (payload ?| ARRAY['signed_url','upload_url','upload_fields','object_key',"
            "'bucket_name','provider_version_id','image_base64','face_embedding','access_token',"
            "'credential']::text[])",
            name="ck_evidence_audit_outbox_payload",
        ),
        sa.UniqueConstraint(
            "source_service",
            "source_event_id",
            name="uq_evidence_audit_outbox_source",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_evidence_audit_outbox_status_due",
        "audit_outbox",
        ["publish_status", "next_attempt_at", "recorded_at"],
        schema=SCHEMA,
    )


def _protect_rows() -> None:
    op.execute(
        sa.text(
            """
            CREATE FUNCTION evidence.reject_physical_delete()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            BEGIN
                RAISE EXCEPTION 'evidence rows use lifecycle deletion';
            END;
            $$
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE TRIGGER evidence_objects_reject_delete
            BEFORE DELETE ON evidence.evidence_objects
            FOR EACH ROW EXECUTE FUNCTION evidence.reject_physical_delete()
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE TRIGGER evidence_links_reject_delete
            BEFORE DELETE ON evidence.evidence_links
            FOR EACH ROW EXECUTE FUNCTION evidence.reject_physical_delete()
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE TRIGGER evidence_objects_reject_truncate
            BEFORE TRUNCATE ON evidence.evidence_objects
            FOR EACH STATEMENT EXECUTE FUNCTION evidence.reject_physical_delete()
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE TRIGGER evidence_links_reject_truncate
            BEFORE TRUNCATE ON evidence.evidence_links
            FOR EACH STATEMENT EXECUTE FUNCTION evidence.reject_physical_delete()
            """
        )
    )


def upgrade() -> None:
    op.execute(sa.text("CREATE SCHEMA evidence"))
    _create_objects()
    _create_links()
    _create_audit_outbox()
    _protect_rows()


def downgrade() -> None:
    op.execute(sa.text("DROP TRIGGER evidence_links_reject_truncate ON evidence.evidence_links"))
    op.execute(
        sa.text("DROP TRIGGER evidence_objects_reject_truncate ON evidence.evidence_objects")
    )
    op.execute(sa.text("DROP TRIGGER evidence_links_reject_delete ON evidence.evidence_links"))
    op.execute(sa.text("DROP TRIGGER evidence_objects_reject_delete ON evidence.evidence_objects"))
    op.execute(sa.text("DROP FUNCTION evidence.reject_physical_delete()"))
    op.drop_table("audit_outbox", schema=SCHEMA)
    op.drop_table("evidence_links", schema=SCHEMA)
    op.drop_table("evidence_objects", schema=SCHEMA)
    op.execute(sa.text("DROP SCHEMA evidence"))
