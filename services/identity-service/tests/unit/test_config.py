from __future__ import annotations

import pytest
from identity_service.config import ConfigurationError, Settings, load_settings


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
