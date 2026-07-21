"""Attendance Service-owned SQLAlchemy table metadata."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

metadata = sa.MetaData(schema="attendance")

attendance_records = sa.Table(
    "attendance_records",
    metadata,
    sa.Column("attendance_record_id", postgresql.UUID(as_uuid=True), primary_key=True),
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
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("row_version", sa.BigInteger(), nullable=False),
)

attendance_event_links = sa.Table(
    "attendance_event_links",
    metadata,
    sa.Column("attendance_event_link_id", postgresql.UUID(as_uuid=True), primary_key=True),
    sa.Column(
        "attendance_record_id",
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey(
            "attendance.attendance_records.attendance_record_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    ),
    sa.Column("normalized_event_id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("link_type", sa.Text(), nullable=False),
    sa.Column("decision_confidence", sa.Numeric(5, 4), nullable=True),
    sa.Column("consent_snapshot_status", sa.Text(), nullable=False),
    sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
)

attendance_corrections = sa.Table(
    "attendance_corrections",
    metadata,
    sa.Column("attendance_correction_id", postgresql.UUID(as_uuid=True), primary_key=True),
    sa.Column(
        "attendance_record_id",
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey(
            "attendance.attendance_records.attendance_record_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    ),
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
    sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
)
