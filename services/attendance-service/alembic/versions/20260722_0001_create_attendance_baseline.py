"""Create the fail-closed Attendance Service baseline.

Revision ID: 20260722_0001
Revises: None
Create Date: 2026-07-22 03:00:00+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260722_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "attendance"
STATUSES = ("present", "absent", "late", "excused", "pending_review")
REVIEW_STATUSES = ("pending", "approved", "rejected", "not_required")
SOURCE_TYPES = ("ai", "manual", "import")
LINK_TYPES = ("check_in", "check_out", "supporting", "rejected")
CONSENT_SNAPSHOTS = ("allowed", "blocked", "not_required")
APPROVAL_STATUSES = ("pending", "approved", "rejected", "not_required")
CORRECTION_REASONS = (
    "EXCUSED_ABSENCE",
    "MANUAL_CORRECTION",
    "REVIEW_RESOLUTION",
    "TIME_ADJUSTMENT",
)


def _quoted(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def _create_records() -> None:
    op.create_table(
        "attendance_records",
        sa.Column(
            "attendance_record_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("school_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("class_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("attendance_date", sa.Date(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("first_check_in_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_check_out_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column("review_status", sa.Text(), nullable=False),
        sa.Column("retention_until", sa.DateTime(timezone=True), nullable=False),
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
        sa.CheckConstraint(
            f"status IN ({_quoted(STATUSES)})",
            name="ck_attendance_records_status",
        ),
        sa.CheckConstraint(
            f"review_status IN ({_quoted(REVIEW_STATUSES)})",
            name="ck_attendance_records_review_status",
        ),
        sa.CheckConstraint(
            f"source_type IN ({_quoted(SOURCE_TYPES)})",
            name="ck_attendance_records_source_type",
        ),
        sa.CheckConstraint(
            "(status = 'pending_review') = (review_status = 'pending')",
            name="ck_attendance_records_review_state",
        ),
        sa.CheckConstraint(
            "first_check_in_at IS NULL OR last_check_out_at IS NULL "
            "OR last_check_out_at >= first_check_in_at",
            name="ck_attendance_records_check_times",
        ),
        sa.CheckConstraint("retention_until > created_at", name="ck_attendance_records_retention"),
        sa.CheckConstraint("updated_at >= created_at", name="ck_attendance_records_timestamps"),
        sa.CheckConstraint("row_version > 0", name="ck_attendance_records_row_version"),
        sa.UniqueConstraint(
            "school_id",
            "student_id",
            "attendance_date",
            name="uq_attendance_records_school_student_date",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_attendance_records_class_date_status",
        "attendance_records",
        ["school_id", "class_id", "attendance_date", "status"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_attendance_records_student_date_desc",
        "attendance_records",
        ["school_id", "student_id", sa.text("attendance_date DESC")],
        schema=SCHEMA,
    )


def _create_event_links() -> None:
    op.create_table(
        "attendance_event_links",
        sa.Column(
            "attendance_event_link_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("attendance_record_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("normalized_event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("link_type", sa.Text(), nullable=False),
        sa.Column("decision_confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("consent_snapshot_status", sa.Text(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            f"link_type IN ({_quoted(LINK_TYPES)})",
            name="ck_attendance_event_links_type",
        ),
        sa.CheckConstraint(
            "decision_confidence IS NULL OR decision_confidence BETWEEN 0 AND 1",
            name="ck_attendance_event_links_confidence",
        ),
        sa.CheckConstraint(
            f"consent_snapshot_status IN ({_quoted(CONSENT_SNAPSHOTS)})",
            name="ck_attendance_event_links_consent",
        ),
        sa.CheckConstraint(
            "consent_snapshot_status <> 'blocked' OR link_type = 'rejected'",
            name="ck_attendance_event_links_blocked",
        ),
        sa.CheckConstraint(
            "recorded_at >= occurred_at",
            name="ck_attendance_event_links_timestamps",
        ),
        sa.ForeignKeyConstraint(
            ["attendance_record_id"],
            ["attendance.attendance_records.attendance_record_id"],
            name="fk_attendance_event_links_record",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "normalized_event_id",
            "link_type",
            name="uq_attendance_event_links_normalized_type",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_attendance_event_links_record_occurred",
        "attendance_event_links",
        ["attendance_record_id", "occurred_at"],
        schema=SCHEMA,
    )


def _create_corrections() -> None:
    op.create_table(
        "attendance_corrections",
        sa.Column(
            "attendance_correction_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("attendance_record_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("from_status", sa.Text(), nullable=False),
        sa.Column("to_status", sa.Text(), nullable=False),
        sa.Column("from_check_in_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("to_check_in_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reason_code", sa.Text(), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("approval_status", sa.Text(), nullable=False),
        sa.Column("approver_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("request_id", sa.Text(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            f"from_status IN ({_quoted(STATUSES)}) AND to_status IN ({_quoted(STATUSES)})",
            name="ck_attendance_corrections_statuses",
        ),
        sa.CheckConstraint(
            f"approval_status IN ({_quoted(APPROVAL_STATUSES)})",
            name="ck_attendance_corrections_approval",
        ),
        sa.CheckConstraint(
            "(approval_status IN ('approved', 'rejected')) = (approver_id IS NOT NULL)",
            name="ck_attendance_corrections_approver",
        ),
        sa.CheckConstraint(
            f"reason_code IN ({_quoted(CORRECTION_REASONS)})",
            name="ck_attendance_corrections_reason",
        ),
        sa.CheckConstraint(
            "request_id ~ '^req_[A-Za-z0-9_-]{8,120}$'",
            name="ck_attendance_corrections_request_id",
        ),
        sa.CheckConstraint(
            "recorded_at >= occurred_at",
            name="ck_attendance_corrections_timestamps",
        ),
        sa.ForeignKeyConstraint(
            ["attendance_record_id"],
            ["attendance.attendance_records.attendance_record_id"],
            name="fk_attendance_corrections_record",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("request_id", name="uq_attendance_corrections_request_id"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_attendance_corrections_record_occurred_desc",
        "attendance_corrections",
        ["attendance_record_id", sa.text("occurred_at DESC")],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_attendance_corrections_approval_occurred",
        "attendance_corrections",
        ["approval_status", "occurred_at"],
        schema=SCHEMA,
    )


def _protect_history() -> None:
    op.execute(
        sa.text(
            """
            CREATE FUNCTION attendance.reject_record_delete()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            BEGIN
                RAISE EXCEPTION 'attendance records cannot be deleted';
            END;
            $$
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE FUNCTION attendance.reject_append_only_change()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            BEGIN
                RAISE EXCEPTION 'attendance history is append-only';
            END;
            $$
            """
        )
    )
    for operation in ("DELETE", "TRUNCATE"):
        level = "ROW" if operation == "DELETE" else "STATEMENT"
        op.execute(
            sa.text(
                f"CREATE TRIGGER attendance_records_reject_{operation.lower()} "
                f"BEFORE {operation} ON attendance.attendance_records "
                f"FOR EACH {level} EXECUTE FUNCTION attendance.reject_record_delete()"
            )
        )
    for table in ("attendance_event_links", "attendance_corrections"):
        for operation in ("UPDATE", "DELETE", "TRUNCATE"):
            level = "STATEMENT" if operation == "TRUNCATE" else "ROW"
            op.execute(
                sa.text(
                    f"CREATE TRIGGER {table}_reject_{operation.lower()} "
                    f"BEFORE {operation} ON attendance.{table} "
                    f"FOR EACH {level} EXECUTE FUNCTION attendance.reject_append_only_change()"
                )
            )
    op.execute(sa.text("REVOKE DELETE, TRUNCATE ON attendance.attendance_records FROM PUBLIC"))
    op.execute(
        sa.text(
            "REVOKE UPDATE, DELETE, TRUNCATE ON attendance.attendance_event_links, "
            "attendance.attendance_corrections FROM PUBLIC"
        )
    )


def upgrade() -> None:
    op.execute(sa.schema.CreateSchema(SCHEMA))
    _create_records()
    _create_event_links()
    _create_corrections()
    _protect_history()


def downgrade() -> None:
    op.drop_table("attendance_corrections", schema=SCHEMA)
    op.drop_table("attendance_event_links", schema=SCHEMA)
    op.drop_table("attendance_records", schema=SCHEMA)
    op.execute(sa.text("DROP FUNCTION attendance.reject_append_only_change()"))
    op.execute(sa.text("DROP FUNCTION attendance.reject_record_delete()"))
    op.execute(sa.schema.DropSchema(SCHEMA))
