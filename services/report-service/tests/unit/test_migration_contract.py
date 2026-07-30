# mypy: disable-error-code="no-untyped-def"

from pathlib import Path


def test_migration_has_reporting_schema_ttl_and_no_sensitive_columns():
    text = Path(
        "services/report-service/alembic/versions/20260730_0001_create_reporting_baseline.py"
    ).read_text(encoding="utf-8")
    assert 'SCHEMA = "reporting"' in text
    assert "interval '7 days'" in text
    assert "scope_fingerprint" in text
    for forbidden in ("student_name", "image_base64", "signed_url", "object_key_ciphertext"):
        assert f'sa.Column("{forbidden}"' not in text
