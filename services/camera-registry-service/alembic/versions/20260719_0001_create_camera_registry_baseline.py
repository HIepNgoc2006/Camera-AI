"""Create the fail-closed Camera Registry baseline.

Revision ID: 20260719_0001
Revises: None
Create Date: 2026-07-19 12:00:00+00:00
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260719_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "camera"
PURPOSE_CODES = (
    "emotion_insight",
    "kitchen_ppe",
    "littering_detection",
    "staff_timekeeping",
    "student_attendance",
    "student_uniform",
    "suspected_smoking",
)
ZONE_TYPES = ("gate", "yard", "hallway", "kitchen", "other")
ZONE_STATUSES = ("active", "inactive")
CAMERA_STATUSES = ("pending", "online", "offline", "disabled")
CHANGE_CODES = (
    "camera_deactivated",
    "camera_mapped",
    "camera_registered",
    "camera_updated",
    "zone_deactivated",
    "zone_registered",
    "zone_updated",
)
CHANGED_FIELDS = (
    "ansvis_source",
    "config",
    "metadata",
    "purpose",
    "schedule",
    "status",
    "task",
    "zone",
)


def _quoted(values: Iterable[str]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def _array(values: Iterable[str]) -> str:
    return f"ARRAY[{_quoted(values)}]::text[]"


def _create_zones() -> None:
    op.create_table(
        "zones",
        sa.Column(
            "zone_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("school_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("zone_type", sa.Text(), nullable=False),
        sa.Column("sensitivity", sa.Text(), nullable=False, server_default="high"),
        sa.Column("purpose_codes", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="active"),
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("row_version", sa.BigInteger(), nullable=False, server_default="1"),
        sa.CheckConstraint("code ~ '^[a-z][a-z0-9_.:-]{0,63}$'", name="ck_camera_zones_code"),
        sa.CheckConstraint(
            "char_length(name) BETWEEN 1 AND 128 AND "
            "name !~* '([a-z][a-z0-9+.-]*://|password|passwd|token|authorization)'",
            name="ck_camera_zones_name_minimized",
        ),
        sa.CheckConstraint(f"zone_type IN ({_quoted(ZONE_TYPES)})", name="ck_camera_zones_type"),
        sa.CheckConstraint(
            "sensitivity IN ('high', 'critical')", name="ck_camera_zones_sensitivity"
        ),
        sa.CheckConstraint(
            f"cardinality(purpose_codes) BETWEEN 1 AND {len(PURPOSE_CODES)} AND "
            f"purpose_codes <@ {_array(PURPOSE_CODES)}",
            name="ck_camera_zones_purposes",
        ),
        sa.CheckConstraint(f"status IN ({_quoted(ZONE_STATUSES)})", name="ck_camera_zones_status"),
        sa.CheckConstraint(
            "(status = 'inactive') = (deactivated_at IS NOT NULL)",
            name="ck_camera_zones_deactivated_state",
        ),
        sa.CheckConstraint("row_version > 0", name="ck_camera_zones_row_version"),
        sa.CheckConstraint("updated_at >= created_at", name="ck_camera_zones_timestamps"),
        sa.UniqueConstraint(
            "school_id",
            "zone_id",
            name="uq_camera_zones_school_zone",
        ),
        sa.UniqueConstraint("school_id", "code", name="uq_camera_zones_school_code"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_camera_zones_school_type_status",
        "zones",
        ["school_id", "zone_type", "status"],
        schema=SCHEMA,
    )


def _create_cameras() -> None:
    op.create_table(
        "cameras",
        sa.Column(
            "camera_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
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
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("row_version", sa.BigInteger(), nullable=False, server_default="1"),
        sa.CheckConstraint("code ~ '^[a-z][a-z0-9_.:-]{0,63}$'", name="ck_camera_cameras_code"),
        sa.CheckConstraint(
            "char_length(display_name) BETWEEN 1 AND 128 AND "
            "display_name !~* "
            "'([a-z][a-z0-9+.-]*://|password|passwd|token|authorization)'",
            name="ck_camera_cameras_name_minimized",
        ),
        sa.CheckConstraint(
            f"cardinality(purpose_codes) BETWEEN 1 AND {len(PURPOSE_CODES)} AND "
            f"purpose_codes <@ {_array(PURPOSE_CODES)}",
            name="ck_camera_cameras_purposes",
        ),
        sa.CheckConstraint(
            "((source_id IS NULL AND task_id IS NULL AND mapping_purpose_code IS NULL "
            "AND schedule_version IS NULL) OR "
            "(source_id IS NOT NULL AND task_id IS NOT NULL "
            "AND mapping_purpose_code IS NOT NULL AND schedule_version IS NOT NULL))",
            name="ck_camera_cameras_mapping_completeness",
        ),
        sa.CheckConstraint(
            "mapping_purpose_code IS NULL OR mapping_purpose_code = ANY(purpose_codes)",
            name="ck_camera_cameras_mapping_purpose",
        ),
        sa.CheckConstraint(
            "credential_ref IS NULL OR credential_ref ~ '^sec_v1_[A-Za-z0-9_-]{32,96}$'",
            name="ck_camera_cameras_credential_ref",
        ),
        sa.CheckConstraint(
            "schedule_version IS NULL OR schedule_version ~ '^[a-z][a-z0-9_.:-]{0,63}$'",
            name="ck_camera_cameras_schedule_version",
        ),
        sa.CheckConstraint(
            "config_version ~ '^[a-z][a-z0-9_.:-]{0,63}$'",
            name="ck_camera_cameras_config_version",
        ),
        sa.CheckConstraint(
            f"status IN ({_quoted(CAMERA_STATUSES)})", name="ck_camera_cameras_status"
        ),
        sa.CheckConstraint(
            "(status = 'disabled') = (deactivated_at IS NOT NULL)",
            name="ck_camera_cameras_deactivated_state",
        ),
        sa.CheckConstraint("row_version > 0", name="ck_camera_cameras_row_version"),
        sa.CheckConstraint("updated_at >= created_at", name="ck_camera_cameras_timestamps"),
        sa.ForeignKeyConstraint(
            ["school_id", "zone_id"],
            ["camera.zones.school_id", "camera.zones.zone_id"],
            name="fk_camera_cameras_school_zone",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("school_id", "code", name="uq_camera_cameras_school_code"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_camera_cameras_school_zone_status",
        "cameras",
        ["school_id", "zone_id", "status"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_camera_cameras_status_last_seen",
        "cameras",
        ["status", "last_seen_at"],
        schema=SCHEMA,
    )
    op.create_index(
        "uq_camera_cameras_primary_mapping",
        "cameras",
        ["school_id", "source_id", "task_id"],
        unique=True,
        schema=SCHEMA,
        postgresql_where=sa.text("source_id IS NOT NULL AND task_id IS NOT NULL"),
    )


def _create_audit_outbox() -> None:
    op.create_table(
        "camera_audit_outbox",
        sa.Column(
            "audit_intent_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("event_schema_version", sa.SmallInteger(), nullable=False, server_default="1"),
        sa.Column(
            "source_service", sa.Text(), nullable=False, server_default="camera-registry-service"
        ),
        sa.Column("source_event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("school_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.Text(), nullable=False, server_default="CAMERA_MAPPING_CHANGED"),
        sa.Column("purpose_code", sa.Text(), nullable=False, server_default="camera_operations"),
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
        sa.Column("result", sa.Text(), nullable=False, server_default="success"),
        sa.Column("state_before", sa.Text(), nullable=True),
        sa.Column("state_after", sa.Text(), nullable=False),
        sa.Column("config_version", sa.Text(), nullable=True),
        sa.Column("schedule_version", sa.Text(), nullable=True),
        sa.Column("policy_version", sa.Text(), nullable=False),
        sa.Column("reason_code", sa.Text(), nullable=True),
        sa.Column("resulting_version", sa.BigInteger(), nullable=False),
        sa.Column("delivery_status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("event_schema_version = 1", name="ck_camera_outbox_schema_version"),
        sa.CheckConstraint(
            "source_service = 'camera-registry-service'",
            name="ck_camera_outbox_source_service",
        ),
        sa.CheckConstraint("action = 'CAMERA_MAPPING_CHANGED'", name="ck_camera_outbox_action"),
        sa.CheckConstraint("purpose_code = 'camera_operations'", name="ck_camera_outbox_purpose"),
        sa.CheckConstraint(
            "resource_type IN ('camera', 'camera_zone')",
            name="ck_camera_outbox_resource_type",
        ),
        sa.CheckConstraint(
            f"change_code IN ({_quoted(CHANGE_CODES)})", name="ck_camera_outbox_change_code"
        ),
        sa.CheckConstraint(
            f"cardinality(changed_fields) BETWEEN 1 AND {len(CHANGED_FIELDS)} AND "
            f"changed_fields <@ {_array(CHANGED_FIELDS)}",
            name="ck_camera_outbox_changed_fields",
        ),
        sa.CheckConstraint(
            "request_id ~ '^req_[A-Za-z0-9_-]{8,120}$'",
            name="ck_camera_outbox_request_id",
        ),
        sa.CheckConstraint(
            "idempotency_key ~ '^idem_[A-Za-z0-9_-]{8,120}$'",
            name="ck_camera_outbox_idempotency_key",
        ),
        sa.CheckConstraint(
            "octet_length(request_fingerprint) = 32",
            name="ck_camera_outbox_request_fingerprint",
        ),
        sa.CheckConstraint("result = 'success'", name="ck_camera_outbox_result"),
        sa.CheckConstraint(
            "state_before IS NULL OR state_before ~ '^[a-z][a-z0-9_.:-]{0,63}$'",
            name="ck_camera_outbox_state_before",
        ),
        sa.CheckConstraint(
            "state_after ~ '^[a-z][a-z0-9_.:-]{0,63}$'",
            name="ck_camera_outbox_state_after",
        ),
        sa.CheckConstraint(
            "config_version IS NULL OR config_version ~ '^[a-z][a-z0-9_.:-]{0,63}$'",
            name="ck_camera_outbox_config_version",
        ),
        sa.CheckConstraint(
            "schedule_version IS NULL OR schedule_version ~ '^[a-z][a-z0-9_.:-]{0,63}$'",
            name="ck_camera_outbox_schedule_version",
        ),
        sa.CheckConstraint(
            "policy_version ~ '^[a-z][a-z0-9_.:-]{0,63}$'",
            name="ck_camera_outbox_policy_version",
        ),
        sa.CheckConstraint(
            "reason_code IS NULL OR reason_code ~ '^[A-Z][A-Z0-9_]{1,63}$'",
            name="ck_camera_outbox_reason_code",
        ),
        sa.CheckConstraint("resulting_version > 0", name="ck_camera_outbox_resulting_version"),
        sa.CheckConstraint(
            "delivery_status IN ('pending', 'published', 'failed')",
            name="ck_camera_outbox_delivery_status",
        ),
        sa.CheckConstraint("attempt_count >= 0", name="ck_camera_outbox_attempt_count"),
        sa.CheckConstraint(
            "(delivery_status = 'published') = (published_at IS NOT NULL)",
            name="ck_camera_outbox_published_state",
        ),
        sa.UniqueConstraint("source_event_id", name="uq_camera_outbox_source_event_id"),
        sa.UniqueConstraint("school_id", "idempotency_key", name="uq_camera_outbox_idempotency"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_camera_outbox_pending",
        "camera_audit_outbox",
        ["delivery_status", "created_at"],
        schema=SCHEMA,
        postgresql_where=sa.text("delivery_status IN ('pending', 'failed')"),
    )


def _protect_registry() -> None:
    op.execute(
        sa.text(
            """
            CREATE FUNCTION camera.reject_registry_delete()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            BEGIN
                RAISE EXCEPTION 'camera registry rows must be deactivated, not deleted';
            END;
            $$
            """
        )
    )
    for table in ("zones", "cameras"):
        op.execute(
            sa.text(
                f"CREATE TRIGGER {table}_reject_delete "
                f"BEFORE DELETE ON camera.{table} "
                "FOR EACH ROW EXECUTE FUNCTION camera.reject_registry_delete()"
            )
        )
        op.execute(
            sa.text(
                f"CREATE TRIGGER {table}_reject_truncate "
                f"BEFORE TRUNCATE ON camera.{table} "
                "FOR EACH STATEMENT EXECUTE FUNCTION camera.reject_registry_delete()"
            )
        )
    op.execute(
        sa.text(
            "REVOKE DELETE, TRUNCATE ON camera.zones, camera.cameras, "
            "camera.camera_audit_outbox FROM PUBLIC"
        )
    )


def upgrade() -> None:
    op.execute(sa.schema.CreateSchema(SCHEMA))
    _create_zones()
    _create_cameras()
    _create_audit_outbox()
    _protect_registry()


def downgrade() -> None:
    op.drop_table("camera_audit_outbox", schema=SCHEMA)
    op.drop_table("cameras", schema=SCHEMA)
    op.drop_table("zones", schema=SCHEMA)
    op.execute(sa.text("DROP FUNCTION camera.reject_registry_delete()"))
    op.execute(sa.schema.DropSchema(SCHEMA))
