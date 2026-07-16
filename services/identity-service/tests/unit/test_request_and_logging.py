from __future__ import annotations

import json
import logging

import pytest
from identity_service.api.request_id import REQUEST_ID_PATTERN, select_request_id
from identity_service.logging import JsonLogFormatter


@pytest.mark.parametrize(
    "values",
    [[], ["one", "two"], [""], ["line\r\nbreak"], ["x" * 65], ["unicode-đ"]],
)
def test_request_id_replaces_missing_duplicate_or_unsafe_values(values: list[str]) -> None:
    selected = select_request_id(values)
    assert selected not in values
    assert REQUEST_ID_PATTERN.fullmatch(selected) is not None


def test_json_formatter_does_not_serialize_arbitrary_message() -> None:
    record = logging.LogRecord(
        name="identity-service",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="fake-sensitive-request-marker",
        args=(),
        exc_info=None,
    )
    record.environment = "test"
    record.event = "request_failed"
    record.request_id = "req-test-123"
    record.status_code = 500

    payload = json.loads(JsonLogFormatter().format(record))

    assert set(payload) == {
        "timestamp",
        "level",
        "service_name",
        "environment",
        "event",
        "request_id",
        "status_code",
    }
    assert "fake-sensitive-request-marker" not in payload.values()
