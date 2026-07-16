from __future__ import annotations

from pathlib import Path

MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "20260717_0001_create_school_schema.py"
)
EXPECTED_TABLES = {
    "schools",
    "students",
    "guardians",
    "guardian_students",
    "staff_members",
    "classes",
    "class_enrollments",
    "staff_class_assignments",
}


def test_migration_source_owns_only_approved_school_tables() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    for table in EXPECTED_TABLES:
        assert f'"{table}"' in source
    assert "identity." not in source
    assert "privacy." not in source
    assert "face_image" not in source
    assert "face_embedding" not in source
    assert 'sa.Column("biometric_subject_ref",' not in source


def test_migration_uses_encrypted_profile_columns_and_scope_guards() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    for column in (
        "full_name_ciphertext",
        "date_of_birth_ciphertext",
        "contact_ciphertext",
        "biometric_subject_ref_ciphertext",
    ):
        assert column in source
    for guard in (
        "ensure_guardian_student_school_scope",
        "ensure_class_enrollment_school_scope",
        "ensure_staff_class_school_scope",
        "ensure_subject_school_scope_update",
    ):
        assert guard in source
