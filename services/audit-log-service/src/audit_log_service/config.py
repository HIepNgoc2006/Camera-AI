"""Fail-closed database configuration without dotenv or secret logging."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field

from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError

ALLOWED_ENVIRONMENTS = frozenset({"development", "test", "staging", "production"})
PLACEHOLDER_MARKERS = ("replace_with", "change_me", "changeme", "example")


class AuditConfigurationError(ValueError):
    """Raised without echoing a secret-bearing configuration value."""


@dataclass(frozen=True, slots=True)
class AuditDatabaseSettings:
    """Validated labels and a password-masking SQLAlchemy URL."""

    environment: str
    database_url: URL = field(repr=False)


def _contains_placeholder(value: str | None) -> bool:
    normalized = (value or "").casefold()
    return any(marker in normalized for marker in PLACEHOLDER_MARKERS)


def load_database_settings(
    environ: Mapping[str, str] | None = None,
) -> AuditDatabaseSettings:
    """Load an injected PostgreSQL URL without reading or mutating a dotenv file."""

    source = os.environ if environ is None else environ
    environment = source.get("APP_ENV", "development").strip().lower()
    if environment not in ALLOWED_ENVIRONMENTS:
        raise AuditConfigurationError("APP_ENV must be an approved environment label")

    raw_url = source.get("AUDIT_DATABASE_URI", "").strip()
    if not raw_url:
        raise AuditConfigurationError("AUDIT_DATABASE_URI is required")
    try:
        database_url = make_url(raw_url)
    except ArgumentError as exc:
        raise AuditConfigurationError("AUDIT_DATABASE_URI must be a valid URL") from exc

    if database_url.drivername != "postgresql+psycopg" or not database_url.database:
        raise AuditConfigurationError(
            "AUDIT_DATABASE_URI must use postgresql+psycopg and name a database"
        )

    if environment in {"staging", "production"} and any(
        _contains_placeholder(component)
        for component in (
            database_url.username,
            database_url.password,
            database_url.host,
            database_url.database,
        )
    ):
        raise AuditConfigurationError(
            "placeholder database configuration is forbidden outside local/test environments"
        )

    return AuditDatabaseSettings(environment=environment, database_url=database_url)
