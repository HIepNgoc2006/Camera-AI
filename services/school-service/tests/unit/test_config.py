from __future__ import annotations

import pytest
from school_service.config import MigrationConfigurationError, load_migration_settings

SAFE_TEST_URI = "postgresql+psycopg://127.0.0.1:55432/Camera_AI_test"
PLACEHOLDER_TEST_URI = "postgresql+psycopg://example.invalid:55432/Camera_AI_test"


def test_load_migration_settings_accepts_local_uri_without_exposing_it() -> None:
    settings = load_migration_settings({"APP_ENV": " TEST ", "SCHOOL_DATABASE_URI": SAFE_TEST_URI})

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
def test_load_migration_settings_fails_closed_without_echoing_uri(
    environment: str, database_uri: str
) -> None:
    with pytest.raises(MigrationConfigurationError) as caught:
        load_migration_settings({"APP_ENV": environment, "SCHOOL_DATABASE_URI": database_uri})

    assert database_uri not in str(caught.value)


def test_load_migration_settings_requires_explicit_uri() -> None:
    with pytest.raises(MigrationConfigurationError, match="required"):
        load_migration_settings({"APP_ENV": "test"})
