from __future__ import annotations

import pytest
from ansvis_adapter.config import ConfigurationError, load_event_database_settings

SAFE_TEST_URI = "postgresql+psycopg://127.0.0.1:55432/Camera_AI_event_test"
PLACEHOLDER_URI = "postgresql+psycopg://example.invalid:55432/Camera_AI_event_test"


def test_event_database_config_accepts_only_named_psycopg_database() -> None:
    settings = load_event_database_settings(
        {"APP_ENV": "test", "EVENT_DATABASE_URI": SAFE_TEST_URI}
    )
    assert settings.environment == "test"
    assert settings.database_url.drivername == "postgresql+psycopg"
    assert settings.database_url.database == "Camera_AI_event_test"
    assert SAFE_TEST_URI not in repr(settings)

    for invalid in (
        {},
        {"EVENT_DATABASE_URI": "not-a-url"},
        {"EVENT_DATABASE_URI": "sqlite:///event.db"},
        {"EVENT_DATABASE_URI": "postgresql+psycopg://127.0.0.1:55432"},
    ):
        with pytest.raises(ConfigurationError):
            load_event_database_settings(invalid)


def test_placeholder_database_components_fail_outside_local_test() -> None:
    with pytest.raises(ConfigurationError, match="placeholder"):
        load_event_database_settings(
            {"APP_ENV": "production", "EVENT_DATABASE_URI": PLACEHOLDER_URI}
        )
