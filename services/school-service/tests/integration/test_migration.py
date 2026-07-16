from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from uuid import UUID

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, inspect
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError

SERVICE_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_COLUMNS = {
    "schools": {
        "school_id",
        "code",
        "name",
        "timezone",
        "status",
        "deactivated_at",
        "created_at",
        "updated_at",
        "row_version",
    },
    "students": {
        "student_id",
        "school_id",
        "student_code",
        "full_name_ciphertext",
        "date_of_birth_ciphertext",
        "status",
        "biometric_subject_ref_ciphertext",
        "deactivated_at",
        "created_at",
        "updated_at",
        "row_version",
    },
    "guardians": {
        "guardian_id",
        "school_id",
        "full_name_ciphertext",
        "contact_ciphertext",
        "contact_lookup_hmac",
        "status",
        "deactivated_at",
        "created_at",
        "updated_at",
        "row_version",
    },
    "guardian_students": {
        "guardian_student_id",
        "guardian_id",
        "student_id",
        "relationship_type",
        "can_manage_consent",
        "valid_from",
        "valid_to",
        "created_at",
        "updated_at",
        "row_version",
    },
    "staff_members": {
        "staff_id",
        "school_id",
        "staff_code",
        "full_name_ciphertext",
        "staff_type",
        "status",
        "biometric_subject_ref_ciphertext",
        "deactivated_at",
        "created_at",
        "updated_at",
        "row_version",
    },
    "classes": {
        "class_id",
        "school_id",
        "class_code",
        "display_name",
        "academic_year",
        "status",
        "archived_at",
        "created_at",
        "updated_at",
        "row_version",
    },
    "class_enrollments": {
        "class_enrollment_id",
        "class_id",
        "student_id",
        "enrolled_from",
        "enrolled_to",
        "status",
        "created_at",
        "updated_at",
        "row_version",
    },
    "staff_class_assignments": {
        "staff_class_assignment_id",
        "staff_id",
        "class_id",
        "assignment_type",
        "valid_from",
        "valid_to",
        "created_at",
        "updated_at",
        "row_version",
    },
}
EXPECTED_EXCLUSIONS = {
    "ex_guardian_students_validity",
    "ex_class_enrollments_active_validity",
    "ex_staff_class_assignments_validity",
}
EXPECTED_PRIMARY_KEYS = {
    "schools": "school_id",
    "students": "student_id",
    "guardians": "guardian_id",
    "guardian_students": "guardian_student_id",
    "staff_members": "staff_id",
    "classes": "class_id",
    "class_enrollments": "class_enrollment_id",
    "staff_class_assignments": "staff_class_assignment_id",
}
EXPECTED_NULLABLE = {
    "schools": {"deactivated_at"},
    "students": {
        "date_of_birth_ciphertext",
        "biometric_subject_ref_ciphertext",
        "deactivated_at",
    },
    "guardians": {"contact_ciphertext", "contact_lookup_hmac", "deactivated_at"},
    "guardian_students": {"valid_to"},
    "staff_members": {"biometric_subject_ref_ciphertext", "deactivated_at"},
    "classes": {"archived_at"},
    "class_enrollments": {"enrolled_to"},
    "staff_class_assignments": {"valid_to"},
}
EXPECTED_DEFAULTS = {
    "schools": {"school_id", "created_at", "updated_at", "row_version", "status"},
    "students": {"student_id", "created_at", "updated_at", "row_version", "status"},
    "guardians": {"guardian_id", "created_at", "updated_at", "row_version", "status"},
    "guardian_students": {
        "guardian_student_id",
        "created_at",
        "updated_at",
        "row_version",
        "can_manage_consent",
    },
    "staff_members": {"staff_id", "created_at", "updated_at", "row_version", "status"},
    "classes": {"class_id", "created_at", "updated_at", "row_version", "status"},
    "class_enrollments": {
        "class_enrollment_id",
        "created_at",
        "updated_at",
        "row_version",
        "status",
    },
    "staff_class_assignments": {
        "staff_class_assignment_id",
        "created_at",
        "updated_at",
        "row_version",
    },
}
EXPECTED_INDEXES = {
    "ix_schools_status",
    "ix_students_school_status",
    "uq_guardians_school_contact_hmac",
    "ix_guardians_school_status",
    "ix_staff_members_school_type_status",
    "ix_classes_school_year_status",
    "ix_guardian_students_guardian_valid_to",
    "ix_guardian_students_student_valid_to",
    "ix_class_enrollments_class_status",
    "ix_class_enrollments_student_enrolled_to",
    "ix_staff_class_assignments_staff_valid_to",
    "ix_staff_class_assignments_class_valid_to",
}
SCHOOL_ONE = UUID("00000000-0000-4000-8000-000000000101")
SCHOOL_TWO = UUID("00000000-0000-4000-8000-000000000102")
STUDENT_ONE = UUID("00000000-0000-4000-8000-000000000201")
GUARDIAN_ONE = UUID("00000000-0000-4000-8000-000000000301")
GUARDIAN_TWO = UUID("00000000-0000-4000-8000-000000000302")
STAFF_ONE = UUID("00000000-0000-4000-8000-000000000401")
CLASS_ONE = UUID("00000000-0000-4000-8000-000000000501")
SYNTHETIC_ENVELOPE = b"ENCV1-synthetic-envelope"


def _test_database_uri() -> str:
    raw_uri = os.environ.get("SCHOOL_DATABASE_URI", "").strip()
    if not raw_uri:
        pytest.skip("SCHOOL_DATABASE_URI is required for isolated migration verification")

    url = make_url(raw_uri)
    database_name = (url.database or "").casefold()
    if (
        url.drivername != "postgresql+psycopg"
        or url.host not in {"127.0.0.1", "localhost"}
        or url.port in {None, 5432}
        or not database_name.endswith("_test")
    ):
        pytest.fail("migration integration test requires an isolated loopback non-5432 *_test DB")
    return raw_uri


def _alembic_config() -> Config:
    return Config(str(SERVICE_ROOT / "alembic.ini"))


def _constraint_names(engine: Engine) -> set[str]:
    statement = sa.text(
        """
        SELECT pc.conname
        FROM pg_constraint AS pc
        JOIN pg_namespace AS pn ON pn.oid = pc.connamespace
        WHERE pn.nspname = 'school'
        """
    )
    with engine.connect() as connection:
        return {str(value) for value in connection.execute(statement).scalars()}


def _index_names(engine: Engine) -> set[str]:
    statement = sa.text("SELECT indexname FROM pg_indexes WHERE schemaname = 'school'")
    with engine.connect() as connection:
        return {str(value) for value in connection.execute(statement).scalars()}


def _assert_column_type(column_name: str, column_type: object) -> None:
    if column_name.endswith("_id"):
        assert isinstance(column_type, postgresql.UUID)
    elif column_name.endswith("_ciphertext") or column_name.endswith("_hmac"):
        assert isinstance(column_type, postgresql.BYTEA)
    elif column_name in {"valid_from", "valid_to", "enrolled_from", "enrolled_to"}:
        assert isinstance(column_type, sa.Date)
    elif column_name.endswith("_at"):
        assert isinstance(column_type, sa.DateTime)
        assert column_type.timezone is True
    elif column_name == "row_version":
        assert isinstance(column_type, sa.BigInteger)
    elif column_name == "can_manage_consent":
        assert isinstance(column_type, sa.Boolean)
    else:
        assert isinstance(column_type, sa.Text)


def _assert_inventory(engine: Engine) -> None:
    inspector = inspect(engine)
    assert set(inspector.get_table_names(schema="school")) == set(EXPECTED_COLUMNS)

    for table, expected_columns in EXPECTED_COLUMNS.items():
        columns = inspector.get_columns(table, schema="school")
        assert {str(column["name"]) for column in columns} == expected_columns
        assert {str(column["name"]) for column in columns if column["nullable"] is True} == (
            EXPECTED_NULLABLE[table]
        )
        assert {str(column["name"]) for column in columns if column["default"] is not None} == (
            EXPECTED_DEFAULTS[table]
        )
        assert inspector.get_pk_constraint(table, schema="school")["constrained_columns"] == [
            EXPECTED_PRIMARY_KEYS[table]
        ]
        for column in columns:
            _assert_column_type(str(column["name"]), column["type"])
        for foreign_key in inspector.get_foreign_keys(table, schema="school"):
            assert foreign_key["referred_schema"] == "school"

    assert _constraint_names(engine) >= EXPECTED_EXCLUSIONS
    assert _index_names(engine) >= EXPECTED_INDEXES


def _reflect(engine: Engine) -> dict[str, sa.Table]:
    metadata = sa.MetaData()
    return {
        table: sa.Table(table, metadata, schema="school", autoload_with=engine)
        for table in EXPECTED_COLUMNS
    }


def _insert_synthetic_graph(engine: Engine, tables: dict[str, sa.Table]) -> None:
    with engine.begin() as connection:
        connection.execute(
            tables["schools"].insert(),
            [
                {
                    "school_id": SCHOOL_ONE,
                    "code": "SYNTHETIC-SCHOOL-01",
                    "name": "Synthetic School One",
                    "timezone": "Asia/Bangkok",
                },
                {
                    "school_id": SCHOOL_TWO,
                    "code": "SYNTHETIC-SCHOOL-02",
                    "name": "Synthetic School Two",
                    "timezone": "Asia/Bangkok",
                },
            ],
        )
        connection.execute(
            tables["students"]
            .insert()
            .values(
                student_id=STUDENT_ONE,
                school_id=SCHOOL_ONE,
                student_code="SYNTHETIC-STUDENT-01",
                full_name_ciphertext=SYNTHETIC_ENVELOPE,
            )
        )
        connection.execute(
            tables["guardians"].insert(),
            [
                {
                    "guardian_id": GUARDIAN_ONE,
                    "school_id": SCHOOL_ONE,
                    "full_name_ciphertext": SYNTHETIC_ENVELOPE,
                },
                {
                    "guardian_id": GUARDIAN_TWO,
                    "school_id": SCHOOL_TWO,
                    "full_name_ciphertext": SYNTHETIC_ENVELOPE,
                },
            ],
        )
        connection.execute(
            tables["staff_members"]
            .insert()
            .values(
                staff_id=STAFF_ONE,
                school_id=SCHOOL_ONE,
                staff_code="SYNTHETIC-STAFF-01",
                full_name_ciphertext=SYNTHETIC_ENVELOPE,
                staff_type="teacher",
            )
        )
        connection.execute(
            tables["classes"]
            .insert()
            .values(
                class_id=CLASS_ONE,
                school_id=SCHOOL_ONE,
                class_code="SYNTHETIC-CLASS-01",
                display_name="Synthetic Class One",
                academic_year="2026-2027",
            )
        )
        connection.execute(
            tables["guardian_students"]
            .insert()
            .values(
                guardian_id=GUARDIAN_ONE,
                student_id=STUDENT_ONE,
                relationship_type="parent",
                valid_from=date(2026, 1, 1),
            )
        )
        connection.execute(
            tables["class_enrollments"]
            .insert()
            .values(
                class_id=CLASS_ONE,
                student_id=STUDENT_ONE,
                enrolled_from=date(2026, 1, 1),
            )
        )
        connection.execute(
            tables["staff_class_assignments"]
            .insert()
            .values(
                staff_id=STAFF_ONE,
                class_id=CLASS_ONE,
                assignment_type="homeroom",
                valid_from=date(2026, 1, 1),
            )
        )


def _assert_constraints(engine: Engine, tables: dict[str, sa.Table]) -> None:
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            tables["students"]
            .insert()
            .values(
                school_id=SCHOOL_ONE,
                student_code="SYNTHETIC-STUDENT-01",
                full_name_ciphertext=SYNTHETIC_ENVELOPE,
            )
        )

    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            tables["guardian_students"]
            .insert()
            .values(
                guardian_id=GUARDIAN_TWO,
                student_id=STUDENT_ONE,
                relationship_type="parent",
                valid_from=date(2026, 1, 1),
            )
        )

    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            tables["guardian_students"]
            .insert()
            .values(
                guardian_id=GUARDIAN_ONE,
                student_id=STUDENT_ONE,
                relationship_type="parent",
                valid_from=date(2026, 2, 1),
            )
        )

    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            tables["guardians"]
            .update()
            .where(tables["guardians"].c.guardian_id == GUARDIAN_ONE)
            .values(school_id=SCHOOL_TWO)
        )

    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            tables["class_enrollments"]
            .insert()
            .values(
                class_id=CLASS_ONE,
                student_id=STUDENT_ONE,
                enrolled_from=date(2026, 6, 1),
                enrolled_to=date(2026, 5, 1),
            )
        )

    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            tables["staff_class_assignments"]
            .insert()
            .values(
                staff_id=STAFF_ONE,
                class_id=CLASS_ONE,
                assignment_type="homeroom",
                valid_from=date(2026, 2, 1),
            )
        )

    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            tables["class_enrollments"]
            .insert()
            .values(
                class_id=CLASS_ONE,
                student_id=STUDENT_ONE,
                enrolled_from=date(2026, 2, 1),
                status="active",
            )
        )


def test_upgrade_inventory_constraints_and_downgrade() -> None:
    database_uri = _test_database_uri()
    engine = sa.create_engine(database_uri, poolclass=sa.pool.NullPool)
    config = _alembic_config()
    upgraded = False
    try:
        command.downgrade(config, "base")
        assert inspect(engine).has_schema("school") is False

        command.upgrade(config, "head")
        upgraded = True
        _assert_inventory(engine)
        tables = _reflect(engine)
        _insert_synthetic_graph(engine, tables)
        _assert_constraints(engine, tables)

        command.downgrade(config, "base")
        upgraded = False
        assert inspect(engine).has_schema("school") is False
    finally:
        if upgraded:
            command.downgrade(config, "base")
        engine.dispose()
