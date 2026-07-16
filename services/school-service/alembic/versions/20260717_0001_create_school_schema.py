"""Create the initial School Service schema.

Revision ID: 20260717_0001
Revises:
Create Date: 2026-07-17 00:00:00+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260717_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = ("school_service",)
depends_on: str | Sequence[str] | None = None

SCHEMA = "school"


def _mutable_columns(identifier: str) -> tuple[sa.Column[object], ...]:
    return (
        sa.Column(
            identifier,
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
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
        sa.Column(
            "row_version",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.CheckConstraint(
            "row_version > 0", name=f"ck_{identifier.removesuffix('_id')}_row_version"
        ),
    )


def _create_tables() -> None:
    op.create_table(
        "schools",
        *_mutable_columns("school_id"),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("timezone", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'active'")),
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("btrim(code) <> ''", name="ck_schools_code_not_blank"),
        sa.CheckConstraint("btrim(name) <> ''", name="ck_schools_name_not_blank"),
        sa.CheckConstraint("btrim(timezone) <> ''", name="ck_schools_timezone_not_blank"),
        sa.CheckConstraint("status IN ('active', 'suspended', 'closed')", name="ck_schools_status"),
        sa.CheckConstraint(
            "deactivated_at IS NULL OR status <> 'active'",
            name="ck_schools_deactivated_status",
        ),
        sa.UniqueConstraint("code", name="uq_schools_code"),
        schema=SCHEMA,
    )
    op.create_index("ix_schools_status", "schools", ["status"], schema=SCHEMA)

    op.create_table(
        "students",
        *_mutable_columns("student_id"),
        sa.Column(
            "school_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "school.schools.school_id",
                name="fk_students_school",
                ondelete="RESTRICT",
                onupdate="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column("student_code", sa.Text(), nullable=False),
        sa.Column("full_name_ciphertext", postgresql.BYTEA(), nullable=False),
        sa.Column("date_of_birth_ciphertext", postgresql.BYTEA(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'active'")),
        sa.Column("biometric_subject_ref_ciphertext", postgresql.BYTEA(), nullable=True),
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("btrim(student_code) <> ''", name="ck_students_code_not_blank"),
        sa.CheckConstraint(
            "octet_length(full_name_ciphertext) > 0", name="ck_students_name_envelope_not_empty"
        ),
        sa.CheckConstraint(
            "date_of_birth_ciphertext IS NULL OR octet_length(date_of_birth_ciphertext) > 0",
            name="ck_students_birth_envelope_not_empty",
        ),
        sa.CheckConstraint(
            "biometric_subject_ref_ciphertext IS NULL "
            "OR octet_length(biometric_subject_ref_ciphertext) > 0",
            name="ck_students_biometric_ref_envelope_not_empty",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'inactive', 'graduated')", name="ck_students_status"
        ),
        sa.CheckConstraint(
            "deactivated_at IS NULL OR status <> 'active'",
            name="ck_students_deactivated_status",
        ),
        sa.UniqueConstraint("school_id", "student_code", name="uq_students_school_code"),
        schema=SCHEMA,
    )
    op.create_index("ix_students_school_status", "students", ["school_id", "status"], schema=SCHEMA)

    op.create_table(
        "guardians",
        *_mutable_columns("guardian_id"),
        sa.Column(
            "school_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "school.schools.school_id",
                name="fk_guardians_school",
                ondelete="RESTRICT",
                onupdate="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column("full_name_ciphertext", postgresql.BYTEA(), nullable=False),
        sa.Column("contact_ciphertext", postgresql.BYTEA(), nullable=True),
        sa.Column("contact_lookup_hmac", postgresql.BYTEA(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'active'")),
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "octet_length(full_name_ciphertext) > 0", name="ck_guardians_name_envelope_not_empty"
        ),
        sa.CheckConstraint(
            "contact_ciphertext IS NULL OR octet_length(contact_ciphertext) > 0",
            name="ck_guardians_contact_envelope_not_empty",
        ),
        sa.CheckConstraint(
            "contact_lookup_hmac IS NULL OR octet_length(contact_lookup_hmac) = 32",
            name="ck_guardians_contact_hmac_length",
        ),
        sa.CheckConstraint("status IN ('active', 'inactive')", name="ck_guardians_status"),
        sa.CheckConstraint(
            "deactivated_at IS NULL OR status <> 'active'",
            name="ck_guardians_deactivated_status",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "uq_guardians_school_contact_hmac",
        "guardians",
        ["school_id", "contact_lookup_hmac"],
        unique=True,
        schema=SCHEMA,
        postgresql_where=sa.text("contact_lookup_hmac IS NOT NULL"),
    )
    op.create_index(
        "ix_guardians_school_status", "guardians", ["school_id", "status"], schema=SCHEMA
    )

    op.create_table(
        "staff_members",
        *_mutable_columns("staff_id"),
        sa.Column(
            "school_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "school.schools.school_id",
                name="fk_staff_members_school",
                ondelete="RESTRICT",
                onupdate="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column("staff_code", sa.Text(), nullable=False),
        sa.Column("full_name_ciphertext", postgresql.BYTEA(), nullable=False),
        sa.Column("staff_type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'active'")),
        sa.Column("biometric_subject_ref_ciphertext", postgresql.BYTEA(), nullable=True),
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("btrim(staff_code) <> ''", name="ck_staff_members_code_not_blank"),
        sa.CheckConstraint(
            "octet_length(full_name_ciphertext) > 0",
            name="ck_staff_members_name_envelope_not_empty",
        ),
        sa.CheckConstraint(
            "biometric_subject_ref_ciphertext IS NULL "
            "OR octet_length(biometric_subject_ref_ciphertext) > 0",
            name="ck_staff_members_biometric_ref_envelope_not_empty",
        ),
        sa.CheckConstraint(
            "staff_type IN ('teacher', 'kitchen', 'operations', 'other')",
            name="ck_staff_members_type",
        ),
        sa.CheckConstraint("status IN ('active', 'inactive')", name="ck_staff_members_status"),
        sa.CheckConstraint(
            "deactivated_at IS NULL OR status <> 'active'",
            name="ck_staff_members_deactivated_status",
        ),
        sa.UniqueConstraint("school_id", "staff_code", name="uq_staff_members_school_code"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_staff_members_school_type_status",
        "staff_members",
        ["school_id", "staff_type", "status"],
        schema=SCHEMA,
    )

    op.create_table(
        "classes",
        *_mutable_columns("class_id"),
        sa.Column(
            "school_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "school.schools.school_id",
                name="fk_classes_school",
                ondelete="RESTRICT",
                onupdate="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column("class_code", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("academic_year", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'active'")),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("btrim(class_code) <> ''", name="ck_classes_code_not_blank"),
        sa.CheckConstraint("btrim(display_name) <> ''", name="ck_classes_name_not_blank"),
        sa.CheckConstraint("btrim(academic_year) <> ''", name="ck_classes_year_not_blank"),
        sa.CheckConstraint("status IN ('active', 'archived')", name="ck_classes_status"),
        sa.CheckConstraint(
            "archived_at IS NULL OR status = 'archived'", name="ck_classes_archived_status"
        ),
        sa.UniqueConstraint(
            "school_id", "academic_year", "class_code", name="uq_classes_school_year_code"
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_classes_school_year_status",
        "classes",
        ["school_id", "academic_year", "status"],
        schema=SCHEMA,
    )

    op.create_table(
        "guardian_students",
        *_mutable_columns("guardian_student_id"),
        sa.Column(
            "guardian_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "school.guardians.guardian_id",
                name="fk_guardian_students_guardian",
                ondelete="RESTRICT",
                onupdate="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column(
            "student_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "school.students.student_id",
                name="fk_guardian_students_student",
                ondelete="RESTRICT",
                onupdate="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column("relationship_type", sa.Text(), nullable=False),
        sa.Column(
            "can_manage_consent", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.CheckConstraint(
            "relationship_type IN ('parent', 'legal_guardian', 'authorized')",
            name="ck_guardian_students_relationship_type",
        ),
        sa.CheckConstraint(
            "valid_to IS NULL OR valid_to >= valid_from", name="ck_guardian_students_validity"
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_guardian_students_guardian_valid_to",
        "guardian_students",
        ["guardian_id", "valid_to"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_guardian_students_student_valid_to",
        "guardian_students",
        ["student_id", "valid_to"],
        schema=SCHEMA,
    )

    op.create_table(
        "class_enrollments",
        *_mutable_columns("class_enrollment_id"),
        sa.Column(
            "class_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "school.classes.class_id",
                name="fk_class_enrollments_class",
                ondelete="RESTRICT",
                onupdate="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column(
            "student_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "school.students.student_id",
                name="fk_class_enrollments_student",
                ondelete="RESTRICT",
                onupdate="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column("enrolled_from", sa.Date(), nullable=False),
        sa.Column("enrolled_to", sa.Date(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'active'")),
        sa.CheckConstraint(
            "enrolled_to IS NULL OR enrolled_to >= enrolled_from",
            name="ck_class_enrollments_validity",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'withdrawn', 'completed')",
            name="ck_class_enrollments_status",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_class_enrollments_class_status",
        "class_enrollments",
        ["class_id", "status"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_class_enrollments_student_enrolled_to",
        "class_enrollments",
        ["student_id", "enrolled_to"],
        schema=SCHEMA,
    )

    op.create_table(
        "staff_class_assignments",
        *_mutable_columns("staff_class_assignment_id"),
        sa.Column(
            "staff_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "school.staff_members.staff_id",
                name="fk_staff_class_assignments_staff",
                ondelete="RESTRICT",
                onupdate="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column(
            "class_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "school.classes.class_id",
                name="fk_staff_class_assignments_class",
                ondelete="RESTRICT",
                onupdate="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column("assignment_type", sa.Text(), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.CheckConstraint(
            "assignment_type IN ('homeroom', 'subject', 'support')",
            name="ck_staff_class_assignments_type",
        ),
        sa.CheckConstraint(
            "valid_to IS NULL OR valid_to >= valid_from",
            name="ck_staff_class_assignments_validity",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_staff_class_assignments_staff_valid_to",
        "staff_class_assignments",
        ["staff_id", "valid_to"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_staff_class_assignments_class_valid_to",
        "staff_class_assignments",
        ["class_id", "valid_to"],
        schema=SCHEMA,
    )


def _create_overlap_constraints() -> None:
    op.execute(
        """
        ALTER TABLE school.guardian_students
        ADD CONSTRAINT ex_guardian_students_validity
        EXCLUDE USING gist (
            guardian_id WITH =,
            student_id WITH =,
            relationship_type WITH =,
            daterange(valid_from, valid_to, '[]') WITH &&
        )
        """
    )
    op.execute(
        """
        ALTER TABLE school.class_enrollments
        ADD CONSTRAINT ex_class_enrollments_active_validity
        EXCLUDE USING gist (
            class_id WITH =,
            student_id WITH =,
            daterange(enrolled_from, enrolled_to, '[]') WITH &&
        ) WHERE (status = 'active')
        """
    )
    op.execute(
        """
        ALTER TABLE school.staff_class_assignments
        ADD CONSTRAINT ex_staff_class_assignments_validity
        EXCLUDE USING gist (
            staff_id WITH =,
            class_id WITH =,
            assignment_type WITH =,
            daterange(valid_from, valid_to, '[]') WITH &&
        )
        """
    )


def _create_school_scope_functions() -> None:
    op.execute(
        """
        CREATE FUNCTION school.ensure_guardian_student_school_scope()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM school.guardians AS guardian
                JOIN school.students AS student
                  ON student.school_id = guardian.school_id
                WHERE guardian.guardian_id = NEW.guardian_id
                  AND student.student_id = NEW.student_id
            ) THEN
                RAISE EXCEPTION USING
                    ERRCODE = '23514',
                    MESSAGE = 'school scope mismatch',
                    CONSTRAINT = 'ck_guardian_students_school_scope';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION school.ensure_class_enrollment_school_scope()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM school.classes AS class
                JOIN school.students AS student
                  ON student.school_id = class.school_id
                WHERE class.class_id = NEW.class_id
                  AND student.student_id = NEW.student_id
            ) THEN
                RAISE EXCEPTION USING
                    ERRCODE = '23514',
                    MESSAGE = 'school scope mismatch',
                    CONSTRAINT = 'ck_class_enrollments_school_scope';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION school.ensure_staff_class_school_scope()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM school.staff_members AS staff
                JOIN school.classes AS class
                  ON class.school_id = staff.school_id
                WHERE staff.staff_id = NEW.staff_id
                  AND class.class_id = NEW.class_id
            ) THEN
                RAISE EXCEPTION USING
                    ERRCODE = '23514',
                    MESSAGE = 'school scope mismatch',
                    CONSTRAINT = 'ck_staff_class_assignments_school_scope';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION school.ensure_subject_school_scope_update()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF NEW.school_id IS NOT DISTINCT FROM OLD.school_id THEN
                RETURN NEW;
            END IF;

            IF TG_TABLE_NAME = 'guardians' AND EXISTS (
                SELECT 1
                FROM school.guardian_students AS relation
                JOIN school.students AS student ON student.student_id = relation.student_id
                WHERE relation.guardian_id = NEW.guardian_id
                  AND student.school_id <> NEW.school_id
            ) THEN
                RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'school scope mismatch';
            ELSIF TG_TABLE_NAME = 'students' AND (
                EXISTS (
                    SELECT 1
                    FROM school.guardian_students AS relation
                    JOIN school.guardians AS guardian ON guardian.guardian_id = relation.guardian_id
                    WHERE relation.student_id = NEW.student_id
                      AND guardian.school_id <> NEW.school_id
                ) OR EXISTS (
                    SELECT 1
                    FROM school.class_enrollments AS enrollment
                    JOIN school.classes AS class ON class.class_id = enrollment.class_id
                    WHERE enrollment.student_id = NEW.student_id
                      AND class.school_id <> NEW.school_id
                )
            ) THEN
                RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'school scope mismatch';
            ELSIF TG_TABLE_NAME = 'staff_members' AND EXISTS (
                SELECT 1
                FROM school.staff_class_assignments AS assignment
                JOIN school.classes AS class ON class.class_id = assignment.class_id
                WHERE assignment.staff_id = NEW.staff_id
                  AND class.school_id <> NEW.school_id
            ) THEN
                RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'school scope mismatch';
            ELSIF TG_TABLE_NAME = 'classes' AND (
                EXISTS (
                    SELECT 1
                    FROM school.class_enrollments AS enrollment
                    JOIN school.students AS student ON student.student_id = enrollment.student_id
                    WHERE enrollment.class_id = NEW.class_id
                      AND student.school_id <> NEW.school_id
                ) OR EXISTS (
                    SELECT 1
                    FROM school.staff_class_assignments AS assignment
                    JOIN school.staff_members AS staff ON staff.staff_id = assignment.staff_id
                    WHERE assignment.class_id = NEW.class_id
                      AND staff.school_id <> NEW.school_id
                )
            ) THEN
                RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'school scope mismatch';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )


def _create_school_scope_triggers() -> None:
    op.execute(
        """
        CREATE TRIGGER guardian_students_school_scope
        BEFORE INSERT OR UPDATE OF guardian_id, student_id
        ON school.guardian_students
        FOR EACH ROW EXECUTE FUNCTION school.ensure_guardian_student_school_scope()
        """
    )
    op.execute(
        """
        CREATE TRIGGER class_enrollments_school_scope
        BEFORE INSERT OR UPDATE OF class_id, student_id
        ON school.class_enrollments
        FOR EACH ROW EXECUTE FUNCTION school.ensure_class_enrollment_school_scope()
        """
    )
    op.execute(
        """
        CREATE TRIGGER staff_class_assignments_school_scope
        BEFORE INSERT OR UPDATE OF staff_id, class_id
        ON school.staff_class_assignments
        FOR EACH ROW EXECUTE FUNCTION school.ensure_staff_class_school_scope()
        """
    )
    for table in ("guardians", "students", "staff_members", "classes"):
        op.execute(
            f"""
            CREATE TRIGGER {table}_school_scope_update
            BEFORE UPDATE OF school_id ON school.{table}
            FOR EACH ROW EXECUTE FUNCTION school.ensure_subject_school_scope_update()
            """
        )


def upgrade() -> None:
    op.execute(sa.schema.CreateSchema(SCHEMA))
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    _create_tables()
    _create_overlap_constraints()
    _create_school_scope_functions()
    _create_school_scope_triggers()


def downgrade() -> None:
    for table in (
        "staff_class_assignments",
        "class_enrollments",
        "guardian_students",
        "classes",
        "staff_members",
        "guardians",
        "students",
        "schools",
    ):
        op.drop_table(table, schema=SCHEMA)

    for function in (
        "ensure_subject_school_scope_update",
        "ensure_staff_class_school_scope",
        "ensure_class_enrollment_school_scope",
        "ensure_guardian_student_school_scope",
    ):
        op.execute(f"DROP FUNCTION school.{function}()")
    op.execute(sa.schema.DropSchema(SCHEMA))
