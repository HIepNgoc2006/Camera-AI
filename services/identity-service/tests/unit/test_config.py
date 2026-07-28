from __future__ import annotations

import pytest
from identity_service.config import (
    ConfigurationError,
    DatabaseSettings,
    Settings,
    load_database_settings,
    load_settings,
)


def test_load_settings_normalizes_approved_labels() -> None:
    assert load_settings({"APP_ENV": " Staging ", "LOG_LEVEL": " warning "}) == Settings(
        environment="staging",
        log_level="WARNING",
    )


@pytest.mark.parametrize(
    "settings",
    [
        {"environment": "preview", "log_level": "INFO"},
        {"environment": "test", "log_level": "TRACE"},
    ],
)
def test_settings_reject_unapproved_values(settings: dict[str, str]) -> None:
    with pytest.raises(ConfigurationError):
        Settings(**settings)


def test_database_settings_require_postgresql_psycopg_and_redact_repr() -> None:
    database_url = "postgresql+psycopg://localhost/camera_ai_test"
    settings = load_database_settings({"IDENTITY_DATABASE_URI": database_url})
    assert settings == DatabaseSettings(database_url)
    assert repr(settings) == "DatabaseSettings(database_url=<redacted>)"
    for invalid in ("", "sqlite:///tmp/test.db", "postgresql+psycopg:///missing-host"):
        with pytest.raises(ConfigurationError):
            load_database_settings({"IDENTITY_DATABASE_URI": invalid})
