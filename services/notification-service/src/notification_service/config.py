"""Fail-closed Notification Service configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlsplit

from notification_service.domain.errors import NotificationError


@dataclass(frozen=True, slots=True)
class DatabaseSettings:
    database_url: str

    def __repr__(self) -> str:
        return "DatabaseSettings(database_url=<redacted>)"


def load_database_settings() -> DatabaseSettings:
    value = os.environ.get("NOTIFICATION_DATABASE_URI", "")
    try:
        parsed = urlsplit(value)
    except ValueError:
        raise NotificationError("NOTIFICATION_CONFIGURATION_INVALID") from None
    if parsed.scheme != "postgresql+psycopg" or not parsed.hostname or not parsed.path.strip("/"):
        raise NotificationError("NOTIFICATION_CONFIGURATION_INVALID")
    return DatabaseSettings(database_url=value)
