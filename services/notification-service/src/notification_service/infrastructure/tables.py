"""Notification Service-owned SQLAlchemy table metadata."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

metadata = sa.MetaData(schema="notification")

notification_intents = sa.Table(
    "notification_intents",
    metadata,
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
    sa.UniqueConstraint("tenant_id", "idempotency_key", name="uq_notification_intents_idempotency"),
    sa.UniqueConstraint(
        "tenant_id",
        "source_event_id",
        "template_code",
        "template_version",
        name="uq_notification_intents_source_template",
    ),
)

recipient_deliveries = sa.Table(
    "recipient_deliveries",
    metadata,
    sa.Column("delivery_id", postgresql.UUID(as_uuid=True), primary_key=True),
    sa.Column(
        "notification_id",
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey("notification.notification_intents.notification_id", ondelete="RESTRICT"),
        nullable=False,
    ),
    sa.Column("recipient_ref", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("channel", sa.Text(), nullable=False),
    sa.Column("rendered_content", postgresql.JSONB(), nullable=False),
    sa.Column("state", sa.Text(), nullable=False),
    sa.Column("attempt_count", sa.Integer(), nullable=False),
    sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("claim_token", postgresql.UUID(as_uuid=True), nullable=True),
    sa.Column("claim_until", sa.DateTime(timezone=True), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.UniqueConstraint(
        "notification_id",
        "recipient_ref",
        "channel",
        name="uq_notification_deliveries_recipient_channel",
    ),
)

delivery_attempts = sa.Table(
    "delivery_attempts",
    metadata,
    sa.Column("attempt_id", postgresql.UUID(as_uuid=True), primary_key=True),
    sa.Column(
        "delivery_id",
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey("notification.recipient_deliveries.delivery_id", ondelete="RESTRICT"),
        nullable=False,
    ),
    sa.Column("attempt_number", sa.Integer(), nullable=False),
    sa.Column("result", sa.Text(), nullable=False),
    sa.Column("provider_result_category", sa.Text(), nullable=False),
    sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
    sa.UniqueConstraint("delivery_id", "attempt_number", name="uq_notification_attempt_number"),
)

recipient_endpoints = sa.Table(
    "recipient_endpoints",
    metadata,
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
    sa.UniqueConstraint(
        "tenant_id",
        "kind",
        "endpoint_lookup_digest",
        name="uq_notification_endpoint_lookup",
    ),
)

notification_cancellations = sa.Table(
    "notification_cancellations",
    metadata,
    sa.Column("cancellation_id", postgresql.UUID(as_uuid=True), primary_key=True),
    sa.Column(
        "notification_id",
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey("notification.notification_intents.notification_id", ondelete="RESTRICT"),
        nullable=False,
    ),
    sa.Column("trigger_code", sa.Text(), nullable=False),
    sa.Column("owner_service", sa.Text(), nullable=False),
    sa.Column("recipient_ref", postgresql.UUID(as_uuid=True), nullable=True),
    sa.Column("channel", sa.Text(), nullable=True),
    sa.Column("request_id", sa.Text(), nullable=False),
    sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
)

audit_outbox = sa.Table(
    "audit_outbox",
    metadata,
    sa.Column("audit_outbox_id", postgresql.UUID(as_uuid=True), primary_key=True),
    sa.Column("source_service", sa.Text(), nullable=False),
    sa.Column("source_event_id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("school_id", postgresql.UUID(as_uuid=True), nullable=True),
    sa.Column("payload", postgresql.JSONB(), nullable=False),
    sa.Column("publish_status", sa.Text(), nullable=False),
    sa.Column("attempt_count", sa.Integer(), nullable=False),
    sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("claim_token", postgresql.UUID(as_uuid=True), nullable=True),
    sa.Column("claim_expires_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("last_error_code", sa.Text(), nullable=True),
    sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
    sa.UniqueConstraint(
        "source_service",
        "source_event_id",
        name="uq_notification_audit_outbox_source",
    ),
)
