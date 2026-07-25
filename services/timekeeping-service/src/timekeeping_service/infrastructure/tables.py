"""Timekeeping Service-owned SQLAlchemy table metadata."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

metadata = sa.MetaData(schema="timekeeping")

shifts = sa.Table(
    "shifts",
    metadata,
    sa.Column("shift_id", postgresql.UUID(as_uuid=True), primary_key=True),
    sa.Column("school_id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("code", sa.Text(), nullable=False),
    sa.Column("name", sa.Text(), nullable=False),
    sa.Column("timezone", sa.Text(), nullable=False),
    sa.Column("start_local_time", sa.Time(timezone=False), nullable=False),
    sa.Column("end_local_time", sa.Time(timezone=False), nullable=False),
    sa.Column("overnight", sa.Boolean(), nullable=False),
    sa.Column("check_in_grace_minutes", sa.Integer(), nullable=False),
    sa.Column("check_out_grace_minutes", sa.Integer(), nullable=False),
    sa.Column("status", sa.Text(), nullable=False),
    sa.Column("version", sa.Integer(), nullable=False),
    sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
    sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.UniqueConstraint("shift_id", "school_id"),
)

staff_shift_assignments = sa.Table(
    "staff_shift_assignments",
    metadata,
    sa.Column("staff_shift_assignment_id", postgresql.UUID(as_uuid=True), primary_key=True),
    sa.Column("school_id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("staff_id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("shift_id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("valid_from", sa.Date(), nullable=False),
    sa.Column("valid_to", sa.Date(), nullable=True),
    sa.Column("status", sa.Text(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("row_version", sa.BigInteger(), nullable=False),
    sa.ForeignKeyConstraint(
        ["shift_id", "school_id"],
        ["timekeeping.shifts.shift_id", "timekeeping.shifts.school_id"],
        ondelete="RESTRICT",
    ),
)

timekeeping_records = sa.Table(
    "timekeeping_records",
    metadata,
    sa.Column("timekeeping_record_id", postgresql.UUID(as_uuid=True), primary_key=True),
    sa.Column("school_id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("staff_id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("shift_id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("work_date", sa.Date(), nullable=False),
    sa.Column("check_in_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("check_out_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("status", sa.Text(), nullable=False),
    sa.Column("source_type", sa.Text(), nullable=False),
    sa.Column("review_status", sa.Text(), nullable=False),
    sa.Column("retention_until", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("row_version", sa.BigInteger(), nullable=False),
    sa.ForeignKeyConstraint(
        ["shift_id", "school_id"],
        ["timekeeping.shifts.shift_id", "timekeeping.shifts.school_id"],
        ondelete="RESTRICT",
    ),
)

timekeeping_event_links = sa.Table(
    "timekeeping_event_links",
    metadata,
    sa.Column("timekeeping_event_link_id", postgresql.UUID(as_uuid=True), primary_key=True),
    sa.Column(
        "timekeeping_record_id",
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey(
            "timekeeping.timekeeping_records.timekeeping_record_id",
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

timekeeping_corrections = sa.Table(
    "timekeeping_corrections",
    metadata,
    sa.Column("timekeeping_correction_id", postgresql.UUID(as_uuid=True), primary_key=True),
    sa.Column(
        "timekeeping_record_id",
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey(
            "timekeeping.timekeeping_records.timekeeping_record_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    ),
    sa.Column("from_status", sa.Text(), nullable=False),
    sa.Column("to_status", sa.Text(), nullable=False),
    sa.Column("from_check_in_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("to_check_in_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("from_check_out_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("to_check_out_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("reason_code", sa.Text(), nullable=False),
    sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("approval_status", sa.Text(), nullable=False),
    sa.Column("approver_id", postgresql.UUID(as_uuid=True), nullable=True),
    sa.Column("request_id", sa.Text(), nullable=False),
    sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
)
