"""Create the minimized Event Ingestion receipt, event and outbox baseline.

Revision ID: 20260721_0001
Revises: None
Create Date: 2026-07-21 10:00:00+00:00
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260721_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "events"
EVENT_TYPES = (
    "attendance.face.observed",
    "camera.health.changed",
    "insight.emotion.observed",
    "task.health.changed",
    "timekeeping.face.observed",
    "violation.littering.suspected",
    "violation.ppe.suspected",
    "violation.smoking.suspected",
    "violation.uniform.suspected",
)
CONSENT_STATES = ("not_evaluated", "allowed", "blocked", "not_required")
RECEIPT_RESULTS = ("accepted", "duplicate", "rejected")
ATTEMPT_RESULTS = ("succeeded", "retryable", "failed", "dead_lettered")
PUBLISH_STATES = ("pending", "published", "failed")
SUBJECT_TYPES = ("student", "staff", "unknown")
EMOTION_LABELS = ("happy", "neutral", "attentive", "unknown")
METADATA_KEYS = ("schema_version", "status", "rule_code", "detection_count")
DETECTION_ATTRIBUTE_KEYS = (
    "schema_version",
    "track_id",
    "detection_key",
    "rule_code",
    "detection_count",
)
OUTBOX_KEYS = (
    "schema_version",
    "normalized_event_id",
    "school_id",
    "source_id",
    "camera_id",
    "task_id",
    "event_type",
    "event_time",
    "correlation_id",
    "model_version",
    "config_version",
    "consent_gate_status",
    "confidence",
    "metadata",
)
OUTBOX_REQUIRED_KEYS = tuple(key for key in OUTBOX_KEYS if key != "confidence")


def _quoted(values: Iterable[str]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def _text_array(values: Iterable[str]) -> str:
    return f"ARRAY[{_quoted(values)}]::text[]"


def _append_only_columns(identifier: str) -> tuple[sa.Column[object], ...]:
    return (
        sa.Column(
            identifier,
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
    )


def _create_ingestion_receipts() -> None:
    identifier, occurred_at, recorded_at = _append_only_columns("ingestion_receipt_id")
    op.create_table(
        "ingestion_receipts",
        identifier,
        sa.Column("school_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("payload_schema_version", sa.Text(), nullable=False),
        sa.Column("payload_checksum", postgresql.BYTEA(), nullable=False),
        sa.Column("request_id", sa.Text(), nullable=False),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("result", sa.Text(), nullable=False),
        sa.Column("error_code", sa.Text(), nullable=True),
        occurred_at,
        recorded_at,
        sa.CheckConstraint(
            "idempotency_key ~ '^idem_(source|fallback)_v1_[a-f0-9]{64}$'",
            name="ck_events_receipts_idempotency_key",
        ),
        sa.CheckConstraint(
            "payload_schema_version = 'ansvis_http_trigger_v1'",
            name="ck_events_receipts_schema_version",
        ),
        sa.CheckConstraint(
            "octet_length(payload_checksum) = 32",
            name="ck_events_receipts_checksum",
        ),
        sa.CheckConstraint(
            "request_id ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$'",
            name="ck_events_receipts_request_id",
        ),
        sa.CheckConstraint(
            f"result IN ({_quoted(RECEIPT_RESULTS)})",
            name="ck_events_receipts_result",
        ),
        sa.CheckConstraint(
            "((result = 'rejected') = (error_code IS NOT NULL))",
            name="ck_events_receipts_error_state",
        ),
        sa.CheckConstraint(
            "error_code IS NULL OR error_code ~ '^[A-Z][A-Z0-9_]{2,63}$'",
            name="ck_events_receipts_error_code",
        ),
        sa.UniqueConstraint(
            "source_id",
            "idempotency_key",
            name="uq_events_receipts_source_key",
        ),
        sa.UniqueConstraint(
            "ingestion_receipt_id",
            "school_id",
            "source_id",
            name="uq_events_receipts_scope",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_events_receipts_school_received",
        "ingestion_receipts",
        ["school_id", sa.text("received_at DESC")],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_events_receipts_result_received",
        "ingestion_receipts",
        ["result", "received_at"],
        schema=SCHEMA,
    )


def _create_normalized_events() -> None:
    identifier, occurred_at, recorded_at = _append_only_columns("normalized_event_id")
    op.create_table(
        "normalized_events",
        identifier,
        sa.Column("ingestion_receipt_id", postgresql.UUID(as_uuid=True), nullable=False),
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
        sa.Column(
            "sanitized_metadata",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text('\'{"schema_version":"event_metadata_v1"}\'::jsonb'),
        ),
        sa.Column(
            "consent_gate_status",
            sa.Text(),
            nullable=False,
            server_default="not_evaluated",
        ),
        sa.Column("retention_until", sa.DateTime(timezone=True), nullable=False),
        occurred_at,
        recorded_at,
        sa.CheckConstraint(
            f"event_type IN ({_quoted(EVENT_TYPES)})",
            name="ck_events_normalized_type",
        ),
        sa.CheckConstraint(
            "source_timezone = 'UTC'",
            name="ck_events_normalized_timezone",
        ),
        sa.CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_events_normalized_confidence",
        ),
        sa.CheckConstraint(
            "model_version ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$' AND "
            "config_version ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$'",
            name="ck_events_normalized_versions",
        ),
        sa.CheckConstraint(
            "correlation_id ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$'",
            name="ck_events_normalized_correlation",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(sanitized_metadata) = 'object' AND "
            "sanitized_metadata ? 'schema_version' AND "
            "sanitized_metadata->>'schema_version' = 'event_metadata_v1' AND "
            f"sanitized_metadata - {_text_array(METADATA_KEYS)} = '{{}}'::jsonb",
            name="ck_events_normalized_metadata_allowlist",
        ),
        sa.CheckConstraint(
            f"consent_gate_status IN ({_quoted(CONSENT_STATES)})",
            name="ck_events_normalized_consent",
        ),
        sa.CheckConstraint(
            "retention_until > recorded_at",
            name="ck_events_normalized_retention",
        ),
        sa.ForeignKeyConstraint(
            ["ingestion_receipt_id", "school_id", "source_id"],
            [
                "events.ingestion_receipts.ingestion_receipt_id",
                "events.ingestion_receipts.school_id",
                "events.ingestion_receipts.source_id",
            ],
            name="fk_events_normalized_receipt_scope",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "ingestion_receipt_id",
            name="uq_events_normalized_receipt",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_events_normalized_school_time",
        "normalized_events",
        ["school_id", sa.text("event_time DESC")],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_events_normalized_school_type_time",
        "normalized_events",
        ["school_id", "event_type", sa.text("event_time DESC")],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_events_normalized_camera_time",
        "normalized_events",
        ["camera_id", sa.text("event_time DESC")],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_events_normalized_consent_time",
        "normalized_events",
        ["consent_gate_status", "event_time"],
        schema=SCHEMA,
    )


def _create_event_detections() -> None:
    identifier, occurred_at, recorded_at = _append_only_columns("event_detection_id")
    op.create_table(
        "event_detections",
        identifier,
        sa.Column("normalized_event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("detection_index", sa.Integer(), nullable=False),
        sa.Column("subject_type", sa.Text(), nullable=True),
        sa.Column("subject_ref", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("subject_match_confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("emotion_label", sa.Text(), nullable=True),
        sa.Column("emotion_confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column(
            "attributes",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text('\'{"schema_version":"detection_attributes_v1"}\'::jsonb'),
        ),
        sa.Column("retention_until", sa.DateTime(timezone=True), nullable=False),
        occurred_at,
        recorded_at,
        sa.CheckConstraint("detection_index >= 0", name="ck_events_detections_index"),
        sa.CheckConstraint(
            f"subject_type IS NULL OR subject_type IN ({_quoted(SUBJECT_TYPES)})",
            name="ck_events_detections_subject_type",
        ),
        sa.CheckConstraint(
            "(subject_ref IS NULL AND subject_match_confidence IS NULL) OR "
            "(subject_ref IS NOT NULL AND subject_type IN ('student', 'staff') AND "
            "subject_match_confidence >= 0 AND subject_match_confidence <= 1)",
            name="ck_events_detections_subject_link",
        ),
        sa.CheckConstraint(
            f"emotion_label IS NULL OR emotion_label IN ({_quoted(EMOTION_LABELS)})",
            name="ck_events_detections_emotion_label",
        ),
        sa.CheckConstraint(
            "emotion_confidence IS NULL OR "
            "(emotion_label IS NOT NULL AND emotion_confidence >= 0 AND emotion_confidence <= 1)",
            name="ck_events_detections_emotion_confidence",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(attributes) = 'object' AND "
            "attributes ? 'schema_version' AND "
            "attributes->>'schema_version' = 'detection_attributes_v1' AND "
            f"attributes - {_text_array(DETECTION_ATTRIBUTE_KEYS)} = '{{}}'::jsonb",
            name="ck_events_detections_attributes_allowlist",
        ),
        sa.CheckConstraint(
            "retention_until > recorded_at",
            name="ck_events_detections_retention",
        ),
        sa.ForeignKeyConstraint(
            ["normalized_event_id"],
            ["events.normalized_events.normalized_event_id"],
            name="fk_events_detections_event",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "normalized_event_id",
            "detection_index",
            name="uq_events_detections_event_index",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_events_detections_subject_time",
        "event_detections",
        ["subject_type", "subject_ref", sa.text("occurred_at DESC")],
        schema=SCHEMA,
        postgresql_where=sa.text("subject_ref IS NOT NULL"),
    )


def _create_processing_attempts() -> None:
    identifier, occurred_at, recorded_at = _append_only_columns("processing_attempt_id")
    op.create_table(
        "processing_attempts",
        identifier,
        sa.Column("normalized_event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("consumer", sa.Text(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("result", sa.Text(), nullable=False),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reason_code", sa.Text(), nullable=True),
        occurred_at,
        recorded_at,
        sa.CheckConstraint(
            "consumer ~ '^[a-z][a-z0-9-]{1,63}$'",
            name="ck_events_attempts_consumer",
        ),
        sa.CheckConstraint(
            "attempt_number > 0 AND attempt_number <= 1000",
            name="ck_events_attempts_number",
        ),
        sa.CheckConstraint(
            f"result IN ({_quoted(ATTEMPT_RESULTS)})",
            name="ck_events_attempts_result",
        ),
        sa.CheckConstraint(
            "error_code IS NULL OR error_code ~ '^[A-Z][A-Z0-9_]{2,63}$'",
            name="ck_events_attempts_error_code",
        ),
        sa.CheckConstraint(
            "(result = 'retryable') = (next_retry_at IS NOT NULL)",
            name="ck_events_attempts_retry_state",
        ),
        sa.CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0",
            name="ck_events_attempts_duration",
        ),
        sa.CheckConstraint(
            "(actor_id IS NULL AND reason_code IS NULL) OR "
            "(actor_id IS NOT NULL AND reason_code ~ '^[A-Z][A-Z0-9_]{2,63}$')",
            name="ck_events_attempts_actor_reason",
        ),
        sa.ForeignKeyConstraint(
            ["normalized_event_id"],
            ["events.normalized_events.normalized_event_id"],
            name="fk_events_attempts_event",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "normalized_event_id",
            "consumer",
            "attempt_number",
            name="uq_events_attempts_event_consumer_number",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_events_attempts_result_retry",
        "processing_attempts",
        ["result", "next_retry_at"],
        schema=SCHEMA,
    )


def _create_outbox_messages() -> None:
    identifier, occurred_at, recorded_at = _append_only_columns("outbox_message_id")
    op.create_table(
        "outbox_messages",
        identifier,
        sa.Column("normalized_event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("topic", sa.Text(), nullable=False),
        sa.Column("contract_version", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column(
            "publish_status",
            sa.Text(),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claim_token", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("claim_expires_at", sa.DateTime(timezone=True), nullable=True),
        occurred_at,
        recorded_at,
        sa.CheckConstraint(
            "topic ~ '^camera_ai[.]events[.][a-z][a-z0-9_]{2,96}[.]v1$'",
            name="ck_events_outbox_topic",
        ),
        sa.CheckConstraint(
            "contract_version = 'normalized_outbox_v1'",
            name="ck_events_outbox_contract",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(payload) = 'object' AND "
            f"payload ?& {_text_array(OUTBOX_REQUIRED_KEYS)} AND "
            "payload->>'schema_version' = 'normalized_outbox_v1' AND "
            f"payload - {_text_array(OUTBOX_KEYS)} = '{{}}'::jsonb AND "
            "jsonb_typeof(payload->'metadata') = 'object' AND "
            "payload->'metadata'->>'schema_version' = 'event_metadata_v1' AND "
            f"(payload->'metadata') - {_text_array(METADATA_KEYS)} = '{{}}'::jsonb",
            name="ck_events_outbox_payload_allowlist",
        ),
        sa.CheckConstraint(
            f"publish_status IN ({_quoted(PUBLISH_STATES)})",
            name="ck_events_outbox_status",
        ),
        sa.CheckConstraint(
            "(publish_status = 'published') = (published_at IS NOT NULL)",
            name="ck_events_outbox_published_state",
        ),
        sa.CheckConstraint(
            "attempt_count >= 0 AND attempt_count <= 5 AND "
            "(publish_status <> 'failed' OR attempt_count = 5)",
            name="ck_events_outbox_attempt_bound",
        ),
        sa.CheckConstraint(
            "(claim_token IS NULL) = (claim_expires_at IS NULL)",
            name="ck_events_outbox_claim_state",
        ),
        sa.ForeignKeyConstraint(
            ["normalized_event_id"],
            ["events.normalized_events.normalized_event_id"],
            name="fk_events_outbox_event",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "normalized_event_id",
            "topic",
            "contract_version",
            name="uq_events_outbox_event_topic_contract",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_events_outbox_status_due_recorded",
        "outbox_messages",
        ["publish_status", "next_attempt_at", "recorded_at"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_events_outbox_event",
        "outbox_messages",
        ["normalized_event_id"],
        schema=SCHEMA,
    )


def _protect_append_only_data() -> None:
    op.execute(
        sa.text(
            "CREATE FUNCTION events.reject_event_mutation() RETURNS trigger "
            "LANGUAGE plpgsql AS $$ BEGIN "
            "RAISE EXCEPTION 'event record is append-only' USING ERRCODE = '55000'; "
            "END $$"
        )
    )
    for table in (
        "ingestion_receipts",
        "normalized_events",
        "event_detections",
        "processing_attempts",
    ):
        op.execute(
            sa.text(
                f"CREATE TRIGGER {table}_reject_mutation "
                f"BEFORE UPDATE OR DELETE OR TRUNCATE ON events.{table} "
                "FOR EACH STATEMENT EXECUTE FUNCTION events.reject_event_mutation()"
            )
        )
    op.execute(
        sa.text(
            "CREATE TRIGGER outbox_messages_reject_delete "
            "BEFORE DELETE OR TRUNCATE ON events.outbox_messages "
            "FOR EACH STATEMENT EXECUTE FUNCTION events.reject_event_mutation()"
        )
    )
    op.execute(
        sa.text(
            "REVOKE UPDATE, DELETE, TRUNCATE ON events.ingestion_receipts, "
            "events.normalized_events, events.event_detections, "
            "events.processing_attempts FROM PUBLIC"
        )
    )
    op.execute(sa.text("REVOKE DELETE, TRUNCATE ON events.outbox_messages FROM PUBLIC"))


def upgrade() -> None:
    op.execute(sa.schema.CreateSchema(SCHEMA))
    _create_ingestion_receipts()
    _create_normalized_events()
    _create_event_detections()
    _create_processing_attempts()
    _create_outbox_messages()
    _protect_append_only_data()


def downgrade() -> None:
    op.drop_table("outbox_messages", schema=SCHEMA)
    op.drop_table("processing_attempts", schema=SCHEMA)
    op.drop_table("event_detections", schema=SCHEMA)
    op.drop_table("normalized_events", schema=SCHEMA)
    op.drop_table("ingestion_receipts", schema=SCHEMA)
    op.execute(sa.text("DROP FUNCTION events.reject_event_mutation()"))
    op.execute(sa.schema.DropSchema(SCHEMA))
