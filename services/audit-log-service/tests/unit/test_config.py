from __future__ import annotations

import pytest
from audit_log_service.config import AuditConfigurationError, load_database_settings

SAFE_TEST_URI = "postgresql+psycopg://127.0.0.1:55432/Camera_AI_audit_test"
PLACEHOLDER_TEST_URI = "postgresql+psycopg://example.invalid:55432/audit"


def test_load_database_settings_accepts_local_uri_without_exposing_it() -> None:
    settings = load_database_settings({"APP_ENV": " TEST ", "AUDIT_DATABASE_URI": SAFE_TEST_URI})

    assert settings.environment == "test"
    assert settings.database_url.drivername == "postgresql+psycopg"
    assert SAFE_TEST_URI not in repr(settings)


@pytest.mark.parametrize(
    ("environment", "database_uri"),
    [
        ("preview", SAFE_TEST_URI),
        ("test", "sqlite:///unsafe.db"),
        ("production", PLACEHOLDER_TEST_URI),
    ],
)
def test_load_database_settings_fails_closed_without_echoing_uri(
    environment: str, database_uri: str
) -> None:
    with pytest.raises(AuditConfigurationError) as caught:
        load_database_settings({"APP_ENV": environment, "AUDIT_DATABASE_URI": database_uri})

    assert database_uri not in str(caught.value)


def test_load_database_settings_requires_explicit_uri() -> None:
    with pytest.raises(AuditConfigurationError, match="required"):
        load_database_settings({"APP_ENV": "test"})
