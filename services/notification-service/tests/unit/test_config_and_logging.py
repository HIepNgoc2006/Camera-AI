from __future__ import annotations

import logging

import pytest
from notification_service.config import load_database_settings
from notification_service.domain.errors import NotificationError
from notification_service.logging import safe_log


def test_database_config_fails_closed_without_echoing_uri(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("NOTIFICATION_DATABASE_URI", raising=False)
    with pytest.raises(NotificationError, match="NOTIFICATION_CONFIGURATION_INVALID"):
        load_database_settings()

    malformed = "postgresql+psycopg://[invalid-host/synthetic-private-value"
    monkeypatch.setenv("NOTIFICATION_DATABASE_URI", malformed)
    with pytest.raises(NotificationError) as caught:
        load_database_settings()
    assert malformed not in str(caught.value)
    assert "synthetic-private-value" not in repr(caught.value)


def test_logs_drop_recipient_endpoint_content_and_provider_fields(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = logging.getLogger("notification-test")
    with caplog.at_level(logging.INFO, logger="notification-test"):
        safe_log(
            logger,
            logging.INFO,
            {
                "request_id": "req_synthetic_0001",
                "outcome": "denied",
                "recipient_ref": "synthetic-recipient",
                "device_token": "synthetic-private-value",
                "message_text": "synthetic-private-value",
                "provider_payload": "synthetic-private-value",
            },
        )
    rendered = caplog.text.casefold()
    assert "synthetic-private-value" not in rendered
    assert "recipient_ref" not in rendered
    assert "provider_payload" not in rendered
