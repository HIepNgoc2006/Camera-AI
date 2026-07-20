"""Camera Registry-owned SQLAlchemy table metadata."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

metadata = sa.MetaData(schema="camera")

zones = sa.Table(
    "zones",
    metadata,
    sa.Column("zone_id", postgresql.UUID(as_uuid=True), primary_key=True),
    sa.Column("school_id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("code", sa.Text(), nullable=False),
    sa.Column("name", sa.Text(), nullable=False),
    sa.Column("zone_type", sa.Text(), nullable=False),
    sa.Column("sensitivity", sa.Text(), nullable=False),
    sa.Column("purpose_codes", postgresql.ARRAY(sa.Text()), nullable=False),
    sa.Column("status", sa.Text(), nullable=False),
    sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("row_version", sa.BigInteger(), nullable=False),
    sa.UniqueConstraint("school_id", "zone_id", name="uq_camera_zones_school_zone"),
)

cameras = sa.Table(
    "cameras",
    metadata,
    sa.Column("camera_id", postgresql.UUID(as_uuid=True), primary_key=True),
    sa.Column("school_id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("zone_id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("code", sa.Text(), nullable=False),
    sa.Column("display_name", sa.Text(), nullable=False),
    sa.Column("purpose_codes", postgresql.ARRAY(sa.Text()), nullable=False),
    sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=True),
    sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=True),
    sa.Column("mapping_purpose_code", sa.Text(), nullable=True),
    sa.Column("credential_ref", sa.Text(), nullable=True),
    sa.Column("schedule_version", sa.Text(), nullable=True),
    sa.Column("config_version", sa.Text(), nullable=False),
    sa.Column("status", sa.Text(), nullable=False),
    sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("row_version", sa.BigInteger(), nullable=False),
    sa.ForeignKeyConstraint(
        ["school_id", "zone_id"],
        ["camera.zones.school_id", "camera.zones.zone_id"],
        name="fk_camera_cameras_school_zone",
        ondelete="RESTRICT",
    ),
)

camera_audit_outbox = sa.Table(
    "camera_audit_outbox",
    metadata,
    sa.Column("audit_intent_id", postgresql.UUID(as_uuid=True), primary_key=True),
    sa.Column("event_schema_version", sa.SmallInteger(), nullable=False),
    sa.Column("source_service", sa.Text(), nullable=False),
    sa.Column("source_event_id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("school_id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("action", sa.Text(), nullable=False),
    sa.Column("purpose_code", sa.Text(), nullable=False),
    sa.Column("resource_type", sa.Text(), nullable=False),
    sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("change_code", sa.Text(), nullable=False),
    sa.Column("changed_fields", postgresql.ARRAY(sa.Text()), nullable=False),
    sa.Column("zone_id", postgresql.UUID(as_uuid=True), nullable=True),
    sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=True),
    sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=True),
    sa.Column("request_id", sa.Text(), nullable=False),
    sa.Column("idempotency_key", sa.Text(), nullable=False),
    sa.Column("request_fingerprint", postgresql.BYTEA(), nullable=False),
    sa.Column("result", sa.Text(), nullable=False),
    sa.Column("state_before", sa.Text(), nullable=True),
    sa.Column("state_after", sa.Text(), nullable=False),
    sa.Column("config_version", sa.Text(), nullable=True),
    sa.Column("schedule_version", sa.Text(), nullable=True),
    sa.Column("policy_version", sa.Text(), nullable=False),
    sa.Column("reason_code", sa.Text(), nullable=True),
    sa.Column("resulting_version", sa.BigInteger(), nullable=False),
    sa.Column("delivery_status", sa.Text(), nullable=False),
    sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("attempt_count", sa.Integer(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)
