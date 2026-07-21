"""SQLAlchemy Core tables owned by the co-located Event Ingestion component."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

metadata = sa.MetaData(schema="events")

ingestion_receipts = sa.Table(
    "ingestion_receipts",
    metadata,
    sa.Column("ingestion_receipt_id", postgresql.UUID(as_uuid=True), primary_key=True),
    sa.Column("school_id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("idempotency_key", sa.Text(), nullable=False),
    sa.Column("payload_schema_version", sa.Text(), nullable=False),
    sa.Column("payload_checksum", postgresql.BYTEA(), nullable=False),
    sa.Column("request_id", sa.Text(), nullable=False),
    sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("result", sa.Text(), nullable=False),
    sa.Column("error_code", sa.Text(), nullable=True),
    sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
    sa.UniqueConstraint("source_id", "idempotency_key", name="uq_events_receipts_source_key"),
)

normalized_events = sa.Table(
    "normalized_events",
    metadata,
    sa.Column("normalized_event_id", postgresql.UUID(as_uuid=True), primary_key=True),
    sa.Column(
        "ingestion_receipt_id",
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey("events.ingestion_receipts.ingestion_receipt_id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    ),
    sa.Column("school_id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("camera_id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("event_type", sa.Text(), nullable=False),
    sa.Column("event_time", sa.DateTime(timezone=True), nullable=False),
    sa.Column("source_timezone", sa.Text(), nullable=False),
    sa.Column("confidence", sa.Numeric(5, 4), nullable=True),
    sa.Column("zone_ref", postgresql.UUID(as_uuid=True), nullable=True),
    sa.Column("model_version", sa.Text(), nullable=False),
    sa.Column("config_version", sa.Text(), nullable=False),
    sa.Column("correlation_id", sa.Text(), nullable=False),
    sa.Column("sanitized_metadata", postgresql.JSONB(), nullable=False),
    sa.Column("consent_gate_status", sa.Text(), nullable=False),
    sa.Column("retention_until", sa.DateTime(timezone=True), nullable=False),
    sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
)

event_detections = sa.Table(
    "event_detections",
    metadata,
    sa.Column("event_detection_id", postgresql.UUID(as_uuid=True), primary_key=True),
    sa.Column(
        "normalized_event_id",
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey("events.normalized_events.normalized_event_id", ondelete="RESTRICT"),
        nullable=False,
    ),
    sa.Column("detection_index", sa.Integer(), nullable=False),
    sa.Column("subject_type", sa.Text(), nullable=True),
    sa.Column("subject_ref", postgresql.UUID(as_uuid=True), nullable=True),
    sa.Column("subject_match_confidence", sa.Numeric(5, 4), nullable=True),
    sa.Column("emotion_label", sa.Text(), nullable=True),
    sa.Column("emotion_confidence", sa.Numeric(5, 4), nullable=True),
    sa.Column("attributes", postgresql.JSONB(), nullable=False),
    sa.Column("retention_until", sa.DateTime(timezone=True), nullable=False),
    sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
    sa.UniqueConstraint(
        "normalized_event_id", "detection_index", name="uq_events_detections_event_index"
    ),
)

processing_attempts = sa.Table(
    "processing_attempts",
    metadata,
    sa.Column("processing_attempt_id", postgresql.UUID(as_uuid=True), primary_key=True),
    sa.Column(
        "normalized_event_id",
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey("events.normalized_events.normalized_event_id", ondelete="RESTRICT"),
        nullable=False,
    ),
    sa.Column("consumer", sa.Text(), nullable=False),
    sa.Column("attempt_number", sa.Integer(), nullable=False),
    sa.Column("result", sa.Text(), nullable=False),
    sa.Column("error_code", sa.Text(), nullable=True),
    sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("duration_ms", sa.Integer(), nullable=True),
    sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
    sa.Column("reason_code", sa.Text(), nullable=True),
    sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
    sa.UniqueConstraint(
        "normalized_event_id",
        "consumer",
        "attempt_number",
        name="uq_events_attempts_event_consumer_number",
    ),
)

outbox_messages = sa.Table(
    "outbox_messages",
    metadata,
    sa.Column("outbox_message_id", postgresql.UUID(as_uuid=True), primary_key=True),
    sa.Column(
        "normalized_event_id",
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey("events.normalized_events.normalized_event_id", ondelete="RESTRICT"),
        nullable=False,
    ),
    sa.Column("topic", sa.Text(), nullable=False),
    sa.Column("contract_version", sa.Text(), nullable=False),
    sa.Column("payload", postgresql.JSONB(), nullable=False),
    sa.Column("publish_status", sa.Text(), nullable=False),
    sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("attempt_count", sa.Integer(), nullable=False),
    sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("claim_token", postgresql.UUID(as_uuid=True), nullable=True),
    sa.Column("claim_expires_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
)
