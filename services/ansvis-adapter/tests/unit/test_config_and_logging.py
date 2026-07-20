from __future__ import annotations

import json
import logging

import pytest
from ansvis_adapter.config import ConfigurationError, Settings, load_settings
from ansvis_adapter.logging import JsonLogFormatter


def test_settings_accept_only_approved_non_secret_labels() -> None:
    assert load_settings({"APP_ENV": "TEST", "LOG_LEVEL": "warning"}) == Settings(
        environment="test", log_level="WARNING"
    )
    with pytest.raises(ConfigurationError):
        load_settings({"APP_ENV": "local-with-secret", "LOG_LEVEL": "INFO"})
    with pytest.raises(ConfigurationError):
        load_settings({"APP_ENV": "test", "LOG_LEVEL": "TRACE"})


def test_formatter_ignores_message_and_unapproved_record_fields() -> None:
    record = logging.LogRecord(
        name="ansvis-adapter",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="blocked_test_payload_marker",
        args=(),
        exc_info=None,
    )
    record.environment = "test"
    record.event = "request_completed"
    record.request_id = "req_test_ansvis_logging"
    record.status_code = 202
    record.authorization = "blocked_test_authorization_marker"
    record.raw_payload = "blocked_test_raw_payload_marker"

    output = JsonLogFormatter().format(record)
    decoded = json.loads(output)

    assert decoded["service_name"] == "ansvis-adapter"
    assert decoded["status_code"] == 202
    assert "blocked_test" not in output
    assert set(decoded) == {
        "timestamp",
        "level",
        "service_name",
        "environment",
        "event",
        "request_id",
        "status_code",
    }
