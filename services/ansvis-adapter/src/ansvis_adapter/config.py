"""Fail-closed, non-secret process configuration."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

ALLOWED_ENVIRONMENTS = frozenset({"development", "test", "staging", "production"})
ALLOWED_LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})
MAX_EVENT_BODY_BYTES = 65_536


class ConfigurationError(ValueError):
    """Raised when a runtime label has an unsafe or unsupported value."""


@dataclass(frozen=True, slots=True)
class Settings:
    """Non-secret settings needed by the adapter skeleton."""

    environment: str = "development"
    log_level: str = "INFO"


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
