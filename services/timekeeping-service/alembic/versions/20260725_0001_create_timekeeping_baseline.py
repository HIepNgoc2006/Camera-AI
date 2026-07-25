"""Create the fail-closed Timekeeping Service baseline.

Revision ID: 20260725_0001
Revises: None
Create Date: 2026-07-25 03:30:00+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260725_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "timekeeping"
SHIFT_STATUSES = ("draft", "active", "retired")
ASSIGNMENT_STATUSES = ("active", "suspended", "ended")
TIMEKEEPING_STATUSES = (
    "pending",
    "present",
    "late",
    "early_leave",
    "absent",
    "review",
)
REVIEW_STATUSES = ("pending", "approved", "rejected", "not_required")
SOURCE_TYPES = ("ai", "manual", "import")
LINK_TYPES = ("check_in", "check_out", "supporting", "rejected")
CONSENT_SNAPSHOTS = ("allowed", "blocked", "not_required")
APPROVAL_STATUSES = ("pending", "approved", "rejected", "not_required")
CORRECTION_REASONS = (
    "MISSED_CHECK_IN",
    "MISSED_CHECK_OUT",
    "REVIEW_RESOLUTION",
    "SHIFT_OVERRIDE",
    "TIME_ADJUSTMENT",
)


def _quoted(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def _create_shifts() -> None:
    op.create_table(
        "shifts",
        sa.Column(
            "shift_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
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
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "code ~ '^[A-Z][A-Z0-9_-]{1,31}$'",
            name="ck_timekeeping_shifts_code",
        ),
        sa.CheckConstraint(
            "char_length(name) BETWEEN 1 AND 100",
            name="ck_timekeeping_shifts_name",
        ),
        sa.CheckConstraint(
            "char_length(timezone) BETWEEN 1 AND 64",
            name="ck_timekeeping_shifts_timezone",
        ),
        sa.CheckConstraint(
            "start_local_time <> end_local_time "
            "AND overnight = (end_local_time < start_local_time)",
            name="ck_timekeeping_shifts_overnight",
        ),
        sa.CheckConstraint(
            "check_in_grace_minutes BETWEEN 0 AND 240 "
            "AND check_out_grace_minutes BETWEEN 0 AND 240",
            name="ck_timekeeping_shifts_grace",
        ),
        sa.CheckConstraint(
            f"status IN ({_quoted(SHIFT_STATUSES)})",
            name="ck_timekeeping_shifts_status",
        ),
        sa.CheckConstraint("version > 0", name="ck_timekeeping_shifts_version"),
        sa.CheckConstraint(
            "valid_to IS NULL OR valid_to > valid_from",
            name="ck_timekeeping_shifts_validity",
        ),
        sa.CheckConstraint(
            "(status = 'active' AND valid_to IS NULL) "
            "OR (status = 'retired' AND valid_to IS NOT NULL) "
            "OR status = 'draft'",
            name="ck_timekeeping_shifts_lifecycle",
        ),
        sa.UniqueConstraint(
            "school_id",
            "code",
            "version",
            name="uq_timekeeping_shifts_school_code_version",
        ),
        sa.UniqueConstraint(
            "shift_id",
            "school_id",
            name="uq_timekeeping_shifts_id_school",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "uq_timekeeping_shifts_one_active_code",
        "shifts",
        ["school_id", "code"],
        unique=True,
        schema=SCHEMA,
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_index(
        "ix_timekeeping_shifts_school_status",
        "shifts",
        ["school_id", "status", "code"],
        schema=SCHEMA,
    )


def _create_assignments() -> None:
    op.create_table(
        "staff_shift_assignments",
        sa.Column(
            "staff_shift_assignment_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("school_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("staff_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("shift_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
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
            f"status IN ({_quoted(ASSIGNMENT_STATUSES)})",
            name="ck_timekeeping_assignments_status",
        ),
        sa.CheckConstraint(
            "valid_to IS NULL OR valid_to >= valid_from",
            name="ck_timekeeping_assignments_validity",
        ),
        sa.CheckConstraint(
            "updated_at >= created_at",
            name="ck_timekeeping_assignments_timestamps",
        ),
        sa.CheckConstraint(
            "row_version > 0",
            name="ck_timekeeping_assignments_row_version",
        ),
        sa.ForeignKeyConstraint(
            ["shift_id", "school_id"],
            ["timekeeping.shifts.shift_id", "timekeeping.shifts.school_id"],
            name="fk_timekeeping_assignments_shift_school",
            ondelete="RESTRICT",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_timekeeping_assignments_staff_validity",
        "staff_shift_assignments",
        ["school_id", "staff_id", "status", "valid_from", "valid_to"],
        schema=SCHEMA,
    )


def _create_records() -> None:
    op.create_table(
        "timekeeping_records",
        sa.Column(
            "timekeeping_record_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
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
            f"status IN ({_quoted(TIMEKEEPING_STATUSES)})",
            name="ck_timekeeping_records_status",
        ),
        sa.CheckConstraint(
            f"review_status IN ({_quoted(REVIEW_STATUSES)})",
            name="ck_timekeeping_records_review_status",
        ),
        sa.CheckConstraint(
            f"source_type IN ({_quoted(SOURCE_TYPES)})",
            name="ck_timekeeping_records_source_type",
        ),
        sa.CheckConstraint(
            "(status = 'review') = (review_status = 'pending')",
            name="ck_timekeeping_records_review_state",
        ),
        sa.CheckConstraint(
            "check_in_at IS NULL OR check_out_at IS NULL OR check_out_at >= check_in_at",
            name="ck_timekeeping_records_times",
        ),
        sa.CheckConstraint(
            "retention_until > created_at",
            name="ck_timekeeping_records_retention",
        ),
        sa.CheckConstraint(
            "updated_at >= created_at",
            name="ck_timekeeping_records_timestamps",
        ),
        sa.CheckConstraint("row_version > 0", name="ck_timekeeping_records_row_version"),
        sa.ForeignKeyConstraint(
            ["shift_id", "school_id"],
            ["timekeeping.shifts.shift_id", "timekeeping.shifts.school_id"],
            name="fk_timekeeping_records_shift_school",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "school_id",
            "staff_id",
            "work_date",
            "shift_id",
            name="uq_timekeeping_records_school_staff_date_shift",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_timekeeping_records_school_date_status",
        "timekeeping_records",
        ["school_id", "work_date", "status"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_timekeeping_records_staff_date_desc",
        "timekeeping_records",
        ["school_id", "staff_id", sa.text("work_date DESC")],
        schema=SCHEMA,
    )


def _create_event_links() -> None:
    op.create_table(
        "timekeeping_event_links",
        sa.Column(
            "timekeeping_event_link_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("timekeeping_record_id", postgresql.UUID(as_uuid=True), nullable=False),
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
            name="ck_timekeeping_event_links_type",
        ),
        sa.CheckConstraint(
            "decision_confidence IS NULL OR decision_confidence BETWEEN 0 AND 1",
            name="ck_timekeeping_event_links_confidence",
        ),
        sa.CheckConstraint(
            f"consent_snapshot_status IN ({_quoted(CONSENT_SNAPSHOTS)})",
            name="ck_timekeeping_event_links_consent",
        ),
        sa.CheckConstraint(
            "consent_snapshot_status <> 'blocked' OR link_type = 'rejected'",
            name="ck_timekeeping_event_links_blocked",
        ),
        sa.CheckConstraint(
            "recorded_at >= occurred_at",
            name="ck_timekeeping_event_links_timestamps",
        ),
        sa.ForeignKeyConstraint(
            ["timekeeping_record_id"],
            ["timekeeping.timekeeping_records.timekeeping_record_id"],
            name="fk_timekeeping_event_links_record",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "normalized_event_id",
            "link_type",
            name="uq_timekeeping_event_links_normalized_type",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_timekeeping_event_links_record_occurred",
        "timekeeping_event_links",
        ["timekeeping_record_id", "occurred_at"],
        schema=SCHEMA,
    )


def _create_corrections() -> None:
    op.create_table(
        "timekeeping_corrections",
        sa.Column(
            "timekeeping_correction_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("timekeeping_record_id", postgresql.UUID(as_uuid=True), nullable=False),
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
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            f"from_status IN ({_quoted(TIMEKEEPING_STATUSES)}) "
            f"AND to_status IN ({_quoted(TIMEKEEPING_STATUSES)})",
            name="ck_timekeeping_corrections_statuses",
        ),
        sa.CheckConstraint(
            f"approval_status IN ({_quoted(APPROVAL_STATUSES)})",
            name="ck_timekeeping_corrections_approval",
        ),
        sa.CheckConstraint(
            "(approval_status IN ('approved', 'rejected')) = (approver_id IS NOT NULL)",
            name="ck_timekeeping_corrections_approver",
        ),
        sa.CheckConstraint(
            f"reason_code IN ({_quoted(CORRECTION_REASONS)})",
            name="ck_timekeeping_corrections_reason",
        ),
        sa.CheckConstraint(
            "request_id ~ '^req_[A-Za-z0-9_-]{8,120}$'",
            name="ck_timekeeping_corrections_request_id",
        ),
        sa.CheckConstraint(
            "to_check_in_at IS NULL OR to_check_out_at IS NULL "
            "OR to_check_out_at >= to_check_in_at",
            name="ck_timekeeping_corrections_times",
        ),
        sa.CheckConstraint(
            "recorded_at >= occurred_at",
            name="ck_timekeeping_corrections_timestamps",
        ),
        sa.ForeignKeyConstraint(
            ["timekeeping_record_id"],
            ["timekeeping.timekeeping_records.timekeeping_record_id"],
            name="fk_timekeeping_corrections_record",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "request_id",
            name="uq_timekeeping_corrections_request_id",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_timekeeping_corrections_record_occurred_desc",
        "timekeeping_corrections",
        ["timekeeping_record_id", sa.text("occurred_at DESC")],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_timekeeping_corrections_approval_occurred",
        "timekeeping_corrections",
        ["approval_status", "occurred_at"],
        schema=SCHEMA,
    )


def _create_integrity_functions() -> None:
    op.execute(
        sa.text(
            """
            CREATE FUNCTION timekeeping.enforce_assignment_non_overlap()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            BEGIN
                PERFORM pg_advisory_xact_lock(
                    hashtextextended(NEW.school_id::text || ':' || NEW.staff_id::text, 0)
                );
                IF NEW.status = 'active' AND EXISTS (
                    SELECT 1
                    FROM timekeeping.staff_shift_assignments existing
                    WHERE existing.school_id = NEW.school_id
                      AND existing.staff_id = NEW.staff_id
                      AND existing.status = 'active'
                      AND existing.staff_shift_assignment_id
                          <> NEW.staff_shift_assignment_id
                      AND daterange(
                            existing.valid_from,
                            COALESCE(existing.valid_to, 'infinity'::date),
                            '[]'
                          )
                          &&
                          daterange(
                            NEW.valid_from,
                            COALESCE(NEW.valid_to, 'infinity'::date),
                            '[]'
                          )
                ) THEN
                    RAISE EXCEPTION 'active staff shift assignments cannot overlap';
                END IF;
                RETURN NEW;
            END;
            $$
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE FUNCTION timekeeping.enforce_one_active_shift_version()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            DECLARE
                target_school_id uuid;
                target_code text;
            BEGIN
                target_school_id := NEW.school_id;
                target_code := NEW.code;
                IF EXISTS (
                    SELECT 1
                    FROM timekeeping.shifts lifecycle
                    WHERE lifecycle.school_id = target_school_id
                      AND lifecycle.code = target_code
                      AND lifecycle.status IN ('active', 'retired')
                ) AND (
                    SELECT count(*)
                    FROM timekeeping.shifts active_version
                    WHERE active_version.school_id = target_school_id
                      AND active_version.code = target_code
                      AND active_version.status = 'active'
                ) <> 1 THEN
                    RAISE EXCEPTION 'activated shift code requires exactly one active version';
                END IF;
                RETURN NULL;
            END;
            $$
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE FUNCTION timekeeping.protect_shift_versions()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            BEGIN
                IF TG_OP = 'DELETE' THEN
                    RAISE EXCEPTION 'shift versions cannot be deleted';
                END IF;
                IF OLD.status = 'retired' THEN
                    RAISE EXCEPTION 'retired shift versions are immutable';
                END IF;
                IF OLD.status = 'active' THEN
                    IF NEW.status NOT IN ('active', 'retired')
                       OR NEW.school_id IS DISTINCT FROM OLD.school_id
                       OR NEW.code IS DISTINCT FROM OLD.code
                       OR NEW.name IS DISTINCT FROM OLD.name
                       OR NEW.timezone IS DISTINCT FROM OLD.timezone
                       OR NEW.start_local_time IS DISTINCT FROM OLD.start_local_time
                       OR NEW.end_local_time IS DISTINCT FROM OLD.end_local_time
                       OR NEW.overnight IS DISTINCT FROM OLD.overnight
                       OR NEW.check_in_grace_minutes
                            IS DISTINCT FROM OLD.check_in_grace_minutes
                       OR NEW.check_out_grace_minutes
                            IS DISTINCT FROM OLD.check_out_grace_minutes
                       OR NEW.version IS DISTINCT FROM OLD.version
                       OR NEW.valid_from IS DISTINCT FROM OLD.valid_from
                       OR NEW.created_at IS DISTINCT FROM OLD.created_at
                    THEN
                        RAISE EXCEPTION 'active shift versions are immutable';
                    END IF;
                    IF NEW.status = 'active'
                       AND NEW.valid_to IS DISTINCT FROM OLD.valid_to
                    THEN
                        RAISE EXCEPTION 'active shift versions are immutable';
                    END IF;
                END IF;
                RETURN NEW;
            END;
            $$
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE FUNCTION timekeeping.reject_record_delete()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            BEGIN
                RAISE EXCEPTION 'timekeeping records cannot be deleted';
            END;
            $$
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE FUNCTION timekeeping.reject_append_only_change()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            BEGIN
                RAISE EXCEPTION 'timekeeping history is append-only';
            END;
            $$
            """
        )
    )


def _create_integrity_triggers() -> None:
    op.execute(
        sa.text(
            "CREATE TRIGGER staff_shift_assignments_prevent_overlap "
            "BEFORE INSERT OR UPDATE ON timekeeping.staff_shift_assignments "
            "FOR EACH ROW EXECUTE FUNCTION timekeeping.enforce_assignment_non_overlap()"
        )
    )
    op.execute(
        sa.text(
            "CREATE CONSTRAINT TRIGGER shifts_require_one_active_version "
            "AFTER INSERT OR UPDATE ON timekeeping.shifts "
            "DEFERRABLE INITIALLY DEFERRED FOR EACH ROW "
            "EXECUTE FUNCTION timekeeping.enforce_one_active_shift_version()"
        )
    )
    for operation in ("UPDATE", "DELETE"):
        op.execute(
            sa.text(
                f"CREATE TRIGGER shifts_protect_{operation.lower()} "
                f"BEFORE {operation} ON timekeeping.shifts "
                "FOR EACH ROW EXECUTE FUNCTION timekeeping.protect_shift_versions()"
            )
        )
    for table in ("staff_shift_assignments", "timekeeping_records"):
        for operation in ("DELETE", "TRUNCATE"):
            level = "STATEMENT" if operation == "TRUNCATE" else "ROW"
            op.execute(
                sa.text(
                    f"CREATE TRIGGER {table}_reject_{operation.lower()} "
                    f"BEFORE {operation} ON timekeeping.{table} "
                    f"FOR EACH {level} EXECUTE FUNCTION timekeeping.reject_record_delete()"
                )
            )
    for table in ("timekeeping_event_links", "timekeeping_corrections"):
        for operation in ("UPDATE", "DELETE", "TRUNCATE"):
            level = "STATEMENT" if operation == "TRUNCATE" else "ROW"
            op.execute(
                sa.text(
                    f"CREATE TRIGGER {table}_reject_{operation.lower()} "
                    f"BEFORE {operation} ON timekeeping.{table} "
                    f"FOR EACH {level} EXECUTE FUNCTION "
                    "timekeeping.reject_append_only_change()"
                )
            )
    op.execute(
        sa.text(
            "REVOKE DELETE, TRUNCATE ON timekeeping.shifts, "
            "timekeeping.staff_shift_assignments, "
            "timekeeping.timekeeping_records FROM PUBLIC"
        )
    )
    op.execute(
        sa.text(
            "REVOKE UPDATE, DELETE, TRUNCATE ON "
            "timekeeping.timekeeping_event_links, "
            "timekeeping.timekeeping_corrections FROM PUBLIC"
        )
    )


def upgrade() -> None:
    op.execute(sa.schema.CreateSchema(SCHEMA))
    _create_shifts()
    _create_assignments()
    _create_records()
    _create_event_links()
    _create_corrections()
    _create_integrity_functions()
    _create_integrity_triggers()


def downgrade() -> None:
    op.drop_table("timekeeping_corrections", schema=SCHEMA)
    op.drop_table("timekeeping_event_links", schema=SCHEMA)
    op.drop_table("timekeeping_records", schema=SCHEMA)
    op.drop_table("staff_shift_assignments", schema=SCHEMA)
    op.drop_table("shifts", schema=SCHEMA)
    op.execute(sa.text("DROP FUNCTION timekeeping.reject_append_only_change()"))
    op.execute(sa.text("DROP FUNCTION timekeeping.reject_record_delete()"))
    op.execute(sa.text("DROP FUNCTION timekeeping.protect_shift_versions()"))
    op.execute(sa.text("DROP FUNCTION timekeeping.enforce_one_active_shift_version()"))
    op.execute(sa.text("DROP FUNCTION timekeeping.enforce_assignment_non_overlap()"))
    op.execute(sa.schema.DropSchema(SCHEMA))
