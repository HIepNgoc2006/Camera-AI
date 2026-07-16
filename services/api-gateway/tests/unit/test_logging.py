from __future__ import annotations

import json
import logging

from api_gateway.logging import JsonLogFormatter


def test_json_formatter_serializes_only_allowlisted_metadata() -> None:
    record = logging.LogRecord(
        name="api-gateway",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="fake-sensitive-body-marker",
        args=(),
        exc_info=None,
    )
    record.environment = "test"
    record.event = "request_failed"
    record.request_id = "req-test-123"
    record.status_code = 500
    record.error_code = "INTERNAL_SERVER_ERROR"
    record.exception_type = "RuntimeError"

    payload = json.loads(JsonLogFormatter().format(record))

    assert set(payload) == {
        "timestamp",
        "level",
        "service_name",
        "environment",
        "event",
        "request_id",
        "status_code",
        "error_code",
        "exception_type",
    }
    assert "fake-sensitive-body-marker" not in payload.values()
