"""Create the inactive, fail-closed Notification Service baseline.

Revision ID: 20260728_0001
Revises: None
Create Date: 2026-07-28 00:00:00+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from camera_ai_crypto import encv1_check_constraint
from sqlalchemy.dialects import postgresql

revision: str = "20260728_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "notification"
CHANNELS = ("in_app", "push", "email")
INTENT_STATES = ("pending", "denied", "cancelled", "expired")
DELIVERY_STATES = (
    "pending",
    "claimed",
    "delivered",
    "retry_scheduled",
    "dead_lettered",
    "cancelled",
    "expired",
)
ATTEMPT_RESULTS = ("delivered", "retry_scheduled", "dead_lettered", "cancelled")
CANCELLATION_TRIGGERS = (
    "consent_withdrawn",
    "permission_revoked",
    "relationship_revoked",
    "recipient_deactivated",
    "endpoint_revoked",
    "source_rejected",
    "source_expired",
    "purpose_ended",
    "policy_superseded",
)
ALLOWED_CONTENT_FIELDS = (
    "template_code",
    "template_version",
    "generic_title_code",
    "generic_subject_code",
    "generic_body_code",
    "category_code",
    "opaque_notification_ref",
    "opaque_resource_ref",
    "allowlisted_route_code",
    "created_at",
    "expires_at",
    "action_available",
)
FORBIDDEN_CONTENT_FIELDS = (
    "student_name",
    "staff_name",
    "guardian_name",
    "email_address",
    "phone_number",
    "attendance_status",
    "violation_detail",
    "emotion_label",
    "face_image",
    "image_base64",
    "media_url",
    "signed_url",
    "object_key",
    "provider_locator",
    "device_token",
    "access_token",
    "credential",
    "free_form_note",
)


def _quoted(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def _array(values: tuple[str, ...]) -> str:
    return "ARRAY[" + _quoted(values) + "]::text[]"


def _create_intents() -> None:
    op.create_table(
        "notification_intents",
        sa.Column("notification_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("content_fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("school_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subject_ref", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("resource_ref", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content_class", sa.Text(), nullable=False),
        sa.Column("template_code", sa.Text(), nullable=False),
        sa.Column("template_version", sa.Integer(), nullable=False),
        sa.Column("purpose_code", sa.Text(), nullable=False),
        sa.Column("policy_version", sa.Text(), nullable=False),
        sa.Column("source_state", sa.Text(), nullable=False),
        sa.Column("source_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_id", sa.Text(), nullable=False),
        sa.Column("correlation_id", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "idempotency_key ~ '^ntf_[A-Za-z0-9_-]{12,120}$'",
            name="ck_notification_intents_idempotency",
        ),
        sa.CheckConstraint(
            "request_id ~ '^req_[A-Za-z0-9_-]{8,120}$'"
            " AND correlation_id ~ '^cor_[A-Za-z0-9_-]{8,120}$'",
            name="ck_notification_intents_request_correlation",
        ),
        sa.CheckConstraint(
            f"state IN ({_quoted(INTENT_STATES)})",
            name="ck_notification_intents_state",
        ),
        sa.CheckConstraint(
            "template_version = 1 AND policy_version = 'notification_privacy_policy_v1'",
            name="ck_notification_intents_versions",
        ),
        sa.CheckConstraint(
            "expires_at > created_at AND expires_at <= source_expires_at",
            name="ck_notification_intents_expiry",
        ),
        sa.CheckConstraint(
            "octet_length(content_fingerprint) = 32",
            name="ck_notification_intents_fingerprint",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="uq_notification_intents_idempotency",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "source_event_id",
            "template_code",
            "template_version",
            name="uq_notification_intents_source_template",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_notification_intents_school_state_expiry",
        "notification_intents",
        ["school_id", "state", "expires_at"],
        schema=SCHEMA,
    )


def _create_deliveries() -> None:
    allowed = _array(ALLOWED_CONTENT_FIELDS)
    forbidden = _array(FORBIDDEN_CONTENT_FIELDS)
    op.create_table(
        "recipient_deliveries",
        sa.Column("delivery_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("notification_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("recipient_ref", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column("rendered_content", postgresql.JSONB(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claim_token", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("claim_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["notification_id"],
            ["notification.notification_intents.notification_id"],
            name="fk_notification_deliveries_intent",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            f"channel IN ({_quoted(CHANNELS)})",
            name="ck_notification_deliveries_channel",
        ),
        sa.CheckConstraint(
            f"state IN ({_quoted(DELIVERY_STATES)})",
            name="ck_notification_deliveries_state",
        ),
        sa.CheckConstraint(
            "attempt_count BETWEEN 0 AND 5",
            name="ck_notification_deliveries_attempts",
        ),
        sa.CheckConstraint(
            "(state = 'retry_scheduled') = (next_attempt_at IS NOT NULL)",
            name="ck_notification_deliveries_retry_state",
        ),
        sa.CheckConstraint(
            "(claim_token IS NULL) = (claim_until IS NULL)",
            name="ck_notification_deliveries_claim",
        ),
        sa.CheckConstraint(
            "expires_at > created_at AND updated_at >= created_at",
            name="ck_notification_deliveries_timestamps",
        ),
        sa.CheckConstraint(
            f"jsonb_typeof(rendered_content) = 'object'"
            f" AND rendered_content - {allowed} = '{{}}'::jsonb"
            f" AND NOT (rendered_content ?| {forbidden})"
            " AND rendered_content ? 'template_code'"
            " AND rendered_content ? 'template_version'"
            " AND rendered_content ? 'generic_body_code'"
            " AND rendered_content ? 'opaque_notification_ref'"
            " AND rendered_content ? 'expires_at'",
            name="ck_notification_deliveries_content_allowlist",
        ),
        sa.CheckConstraint(
            "channel = 'in_app' OR NOT (rendered_content ? 'opaque_resource_ref')",
            name="ck_notification_deliveries_no_remote_resource",
        ),
        sa.UniqueConstraint(
            "notification_id",
            "recipient_ref",
            "channel",
            name="uq_notification_deliveries_recipient_channel",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_notification_deliveries_state_due",
        "recipient_deliveries",
        ["state", "next_attempt_at", "created_at"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_notification_deliveries_recipient_created",
        "recipient_deliveries",
        ["recipient_ref", sa.text("created_at DESC")],
        schema=SCHEMA,
    )


def _create_attempts_and_cancellations() -> None:
    op.create_table(
        "delivery_attempts",
        sa.Column("attempt_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("delivery_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("result", sa.Text(), nullable=False),
        sa.Column("provider_result_category", sa.Text(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["delivery_id"],
            ["notification.recipient_deliveries.delivery_id"],
            name="fk_notification_attempts_delivery",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "attempt_number BETWEEN 1 AND 5",
            name="ck_notification_attempts_number",
        ),
        sa.CheckConstraint(
            f"result IN ({_quoted(ATTEMPT_RESULTS)})",
            name="ck_notification_attempts_result",
        ),
        sa.CheckConstraint(
            "(result = 'retry_scheduled') = (next_attempt_at IS NOT NULL)",
            name="ck_notification_attempts_retry",
        ),
        sa.CheckConstraint(
            "provider_result_category ~ '^[a-z][a-z0-9_.:-]{0,95}$'",
            name="ck_notification_attempts_provider_category",
        ),
        sa.UniqueConstraint(
            "delivery_id",
            "attempt_number",
            name="uq_notification_attempt_number",
        ),
        schema=SCHEMA,
    )
    op.create_table(
        "notification_cancellations",
        sa.Column("cancellation_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("notification_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("trigger_code", sa.Text(), nullable=False),
        sa.Column("owner_service", sa.Text(), nullable=False),
        sa.Column("recipient_ref", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("channel", sa.Text(), nullable=True),
        sa.Column("request_id", sa.Text(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["notification_id"],
            ["notification.notification_intents.notification_id"],
            name="fk_notification_cancellations_intent",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            f"trigger_code IN ({_quoted(CANCELLATION_TRIGGERS)})",
            name="ck_notification_cancellations_trigger",
        ),
        sa.CheckConstraint(
            "owner_service ~ '^[a-z][a-z0-9-]{1,62}[a-z0-9]$'"
            " AND request_id ~ '^req_[A-Za-z0-9_-]{8,120}$'",
            name="ck_notification_cancellations_owner_request",
        ),
        sa.CheckConstraint(
            "(recipient_ref IS NULL AND channel IS NULL)"
            f" OR (recipient_ref IS NOT NULL AND channel IN ({_quoted(CHANNELS)}))",
            name="ck_notification_cancellations_scope",
        ),
        schema=SCHEMA,
    )


def _create_endpoints() -> None:
    constraint_name, constraint_sql = encv1_check_constraint(
        "recipient_endpoints", "endpoint_ciphertext"
    )
    op.create_table(
        "recipient_endpoints",
        sa.Column("endpoint_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("recipient_ref", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("endpoint_ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("endpoint_lookup_digest", sa.LargeBinary(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "kind IN ('device_token', 'email')",
            name="ck_notification_endpoints_kind",
        ),
        sa.CheckConstraint(
            "state IN ('active', 'revoked') AND (state = 'revoked') = (revoked_at IS NOT NULL)",
            name="ck_notification_endpoints_state",
        ),
        sa.CheckConstraint(constraint_sql, name=constraint_name),
        sa.CheckConstraint(
            "octet_length(endpoint_lookup_digest) = 32",
            name="ck_notification_endpoints_lookup",
        ),
        sa.CheckConstraint(
            "verified_at >= created_at",
            name="ck_notification_endpoints_timestamps",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "kind",
            "endpoint_lookup_digest",
            name="uq_notification_endpoint_lookup",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_notification_endpoints_owner_state",
        "recipient_endpoints",
        ["tenant_id", "recipient_ref", "kind", "state"],
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
        sa.Column("claim_token", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("claim_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.Text(), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "source_service = 'notification-service'",
            name="ck_notification_audit_outbox_service",
        ),
        sa.CheckConstraint(
            "publish_status IN ('pending', 'delivered', 'failed')",
            name="ck_notification_audit_outbox_status",
        ),
        sa.CheckConstraint(
            "attempt_count BETWEEN 0 AND 5",
            name="ck_notification_audit_outbox_attempts",
        ),
        sa.CheckConstraint(
            "payload ? 'event_schema_version' AND payload ? 'action'"
            " AND payload ? 'source_event_id' AND payload ? 'request_id'"
            " AND payload ? 'result' AND payload ? 'occurred_at'"
            " AND NOT (payload ?| ARRAY['image_base64','face_embedding','device_token',"
            "'endpoint_ciphertext','message_text','access_token','credential']::text[])",
            name="ck_notification_audit_outbox_payload",
        ),
        sa.UniqueConstraint(
            "source_service",
            "source_event_id",
            name="uq_notification_audit_outbox_source",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_notification_audit_outbox_status_due",
        "audit_outbox",
        ["publish_status", "next_attempt_at", "recorded_at"],
        schema=SCHEMA,
    )


def _protect_append_only_history() -> None:
    op.execute(
        sa.text(
            """
            CREATE FUNCTION notification.reject_append_only_change()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            BEGIN
                RAISE EXCEPTION 'notification history is append-only';
            END;
            $$
            """
        )
    )
    for table in ("delivery_attempts", "notification_cancellations"):
        for operation in ("UPDATE", "DELETE", "TRUNCATE"):
            level = "STATEMENT" if operation == "TRUNCATE" else "ROW"
            op.execute(
                sa.text(
                    f"CREATE TRIGGER {table}_reject_{operation.lower()} "
                    f"BEFORE {operation} ON notification.{table} "
                    f"FOR EACH {level} EXECUTE FUNCTION "
                    "notification.reject_append_only_change()"
                )
            )
    op.execute(
        sa.text(
            "REVOKE UPDATE, DELETE, TRUNCATE ON notification.delivery_attempts, "
            "notification.notification_cancellations FROM PUBLIC"
        )
    )


def upgrade() -> None:
    op.execute(sa.schema.CreateSchema(SCHEMA))
    _create_intents()
    _create_deliveries()
    _create_attempts_and_cancellations()
    _create_endpoints()
    _create_audit_outbox()
    _protect_append_only_history()


def downgrade() -> None:
    op.drop_table("audit_outbox", schema=SCHEMA)
    op.drop_table("recipient_endpoints", schema=SCHEMA)
    op.drop_table("notification_cancellations", schema=SCHEMA)
    op.drop_table("delivery_attempts", schema=SCHEMA)
    op.drop_table("recipient_deliveries", schema=SCHEMA)
    op.drop_table("notification_intents", schema=SCHEMA)
    op.execute(sa.text("DROP FUNCTION notification.reject_append_only_change()"))
    op.execute(sa.schema.DropSchema(SCHEMA))
