"""Fail-closed, non-secret process configuration."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field

from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError

ALLOWED_ENVIRONMENTS = frozenset({"development", "test", "staging", "production"})
ALLOWED_LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})
PLACEHOLDER_MARKERS = ("replace_with", "change_me", "changeme", "example")
MAX_EVENT_BODY_BYTES = 65_536


class ConfigurationError(ValueError):
    """Raised when a runtime label has an unsafe or unsupported value."""


@dataclass(frozen=True, slots=True)
class Settings:
    """Non-secret settings needed by the adapter skeleton."""

    environment: str = "development"
    log_level: str = "INFO"


@dataclass(frozen=True, slots=True)
class EventDatabaseSettings:
    """Secret-bearing event-store connection parsed without a printable representation."""

    environment: str
    database_url: URL = field(repr=False)


def load_settings(environ: Mapping[str, str] | None = None) -> Settings:
    """Load safe labels without loading dotenv files or credentials."""

    source = os.environ if environ is None else environ
    environment = source.get("APP_ENV", "development").strip().lower()
    log_level = source.get("LOG_LEVEL", "INFO").strip().upper()
    if environment not in ALLOWED_ENVIRONMENTS:
        raise ConfigurationError("APP_ENV must be an approved environment label")
    if log_level not in ALLOWED_LOG_LEVELS:
        raise ConfigurationError("LOG_LEVEL must be an approved logging level")
    return Settings(environment=environment, log_level=log_level)


def load_event_database_settings(
    environ: Mapping[str, str] | None = None,
) -> EventDatabaseSettings:
    """Load the injected event-store URL without logging or copying it into source files."""

    source = os.environ if environ is None else environ
    environment = source.get("APP_ENV", "development").strip().lower()
    if environment not in ALLOWED_ENVIRONMENTS:
        raise ConfigurationError("APP_ENV must be an approved environment label")

    raw_url = source.get("EVENT_DATABASE_URI", "").strip()
    if not raw_url:
        raise ConfigurationError("EVENT_DATABASE_URI is required")
    try:
        database_url = make_url(raw_url)
    except ArgumentError as exc:
        raise ConfigurationError("EVENT_DATABASE_URI must be a valid URL") from exc
    if database_url.drivername != "postgresql+psycopg" or not database_url.database:
        raise ConfigurationError(
            "EVENT_DATABASE_URI must use postgresql+psycopg and name a database"
        )
    if environment in {"staging", "production"}:
        components = (
            database_url.username,
            database_url.password,
            database_url.host,
            database_url.database,
        )
        if any(
            any(marker in (component or "").casefold() for marker in PLACEHOLDER_MARKERS)
            for component in components
        ):
            raise ConfigurationError(
                "placeholder database configuration is forbidden outside local/test environments"
            )
    return EventDatabaseSettings(environment=environment, database_url=database_url)
