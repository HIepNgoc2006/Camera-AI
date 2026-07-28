"""Fail-closed, non-secret process configuration."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import urlsplit

ALLOWED_ENVIRONMENTS = frozenset({"development", "test", "staging", "production"})
ALLOWED_LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})


class ConfigurationError(ValueError):
    """Raised when a runtime label has an unsafe or unsupported value."""


@dataclass(frozen=True, slots=True)
class Settings:
    """Non-secret settings needed by the service skeleton."""

    environment: str = "development"
    log_level: str = "INFO"

    def __post_init__(self) -> None:
        if self.environment not in ALLOWED_ENVIRONMENTS:
            raise ConfigurationError("APP_ENV must be an approved environment label")
        if self.log_level not in ALLOWED_LOG_LEVELS:
            raise ConfigurationError("LOG_LEVEL must be an approved logging level")


@dataclass(frozen=True, slots=True)
class DatabaseSettings:
    database_url: str

    def __repr__(self) -> str:
        return "DatabaseSettings(database_url=<redacted>)"


def load_settings(environ: Mapping[str, str] | None = None) -> Settings:
    """Load approved runtime labels without reading a dotenv file."""

    source = os.environ if environ is None else environ
    return Settings(
        environment=source.get("APP_ENV", "development").strip().lower(),
        log_level=source.get("LOG_LEVEL", "INFO").strip().upper(),
    )


def load_database_settings(environ: Mapping[str, str] | None = None) -> DatabaseSettings:
    source = os.environ if environ is None else environ
    value = source.get("IDENTITY_DATABASE_URI", "")
    try:
        parsed = urlsplit(value)
    except ValueError:
        raise ConfigurationError("IDENTITY_DATABASE_URI is invalid") from None
    if parsed.scheme != "postgresql+psycopg" or not parsed.hostname or not parsed.path.strip("/"):
        raise ConfigurationError("IDENTITY_DATABASE_URI is invalid")
    return DatabaseSettings(database_url=value)
