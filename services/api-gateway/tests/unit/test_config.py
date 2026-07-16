from __future__ import annotations

import pytest
from api_gateway.config import ConfigurationError, Settings, load_settings


def test_load_settings_normalizes_approved_runtime_labels() -> None:
    assert load_settings({"APP_ENV": " Staging ", "LOG_LEVEL": " warning "}) == Settings(
        environment="staging",
        log_level="WARNING",
    )


@pytest.mark.parametrize(
    ("environ", "message"),
    [
        ({"APP_ENV": "preview"}, "APP_ENV"),
        ({"LOG_LEVEL": "TRACE"}, "LOG_LEVEL"),
    ],
)
def test_load_settings_rejects_unapproved_values(environ: dict[str, str], message: str) -> None:
    with pytest.raises(ConfigurationError, match=message):
        load_settings(environ)
