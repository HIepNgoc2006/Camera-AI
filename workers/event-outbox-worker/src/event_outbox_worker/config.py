"""Fail-closed worker configuration.

The broker URL is secret-bearing: it is parsed once, never printed, never defaulted, and a
placeholder credential is rejected outside local/test environments — mirroring the adapter's
database-settings contract.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from urllib.parse import urlsplit

ALLOWED_ENVIRONMENTS = frozenset({"development", "test", "staging", "production"})
PLACEHOLDER_MARKERS = ("replace_with", "change_me", "changeme", "example")
EXCHANGE_NAME = "camera-ai.events.v1"
MAX_BATCH_SIZE = 50
MAX_DATABASE_CONNECTIONS_PER_PROCESS = 4


class WorkerConfigurationError(ValueError):
    """Raised when the worker environment is unsafe or incomplete."""


@dataclass(frozen=True, slots=True)
class WorkerSettings:
    """Validated runtime settings; the broker URL has no printable representation."""

    environment: str
    broker_url: str = field(repr=False)
    batch_size: int = MAX_BATCH_SIZE
    idle_sleep_seconds: float = 1.0
    broker_retry_seconds: float = 5.0
    metrics_port: int = 0
    snapshot_interval_seconds: float = 60.0
    event_db_pool_size: int = 2
    event_db_max_overflow: int = 1
    audit_db_pool_size: int = 1
    audit_db_max_overflow: int = 0
    db_pool_timeout_seconds: float = 2.0


def load_worker_settings(environ: Mapping[str, str] | None = None) -> WorkerSettings:
    """Load and validate worker settings without logging any secret component."""

    source = os.environ if environ is None else environ
    environment = source.get("APP_ENV", "development").strip().lower()
    if environment not in ALLOWED_ENVIRONMENTS:
        raise WorkerConfigurationError("APP_ENV must be an approved environment label")

    broker_url = source.get("EVENT_BROKER_URI", "").strip()
    if not broker_url:
        raise WorkerConfigurationError("EVENT_BROKER_URI is required")
    parts = urlsplit(broker_url)
    if parts.scheme not in {"amqp", "amqps"} or not parts.hostname:
        raise WorkerConfigurationError("EVENT_BROKER_URI must be an amqp(s) URL naming a host")
    if environment in {"staging", "production"}:
        if parts.scheme != "amqps":
            raise WorkerConfigurationError("EVENT_BROKER_URI must use amqps outside local/test")
        components = (parts.username, parts.password, parts.hostname)
        if any(
            any(marker in (component or "").casefold() for marker in PLACEHOLDER_MARKERS)
            for component in components
        ):
            raise WorkerConfigurationError(
                "placeholder broker configuration is forbidden outside local/test environments"
            )

    batch_size = _bounded_int(source, "WORKER_BATCH_SIZE", default=MAX_BATCH_SIZE, low=1, high=50)
    idle_sleep = _bounded_float(
        source, "WORKER_IDLE_SLEEP_SECONDS", default=1.0, low=0.1, high=60.0
    )
    broker_retry = _bounded_float(
        source, "WORKER_BROKER_RETRY_SECONDS", default=5.0, low=1.0, high=300.0
    )
    default_metrics_port = 0 if environment == "test" else 9_465
    metrics_port = _bounded_int(
        source, "WORKER_METRICS_PORT", default=default_metrics_port, low=0, high=65_535
    )
    if metrics_port != 0 and metrics_port < 1_024:
        raise WorkerConfigurationError(
            "WORKER_METRICS_PORT must be 0 (disabled) or within 1024..65535"
        )
    snapshot_interval = _bounded_float(
        source, "WORKER_SNAPSHOT_INTERVAL_SECONDS", default=60.0, low=5.0, high=3_600.0
    )
    event_db_pool_size = _bounded_int(source, "EVENT_DB_POOL_SIZE", default=2, low=1, high=4)
    event_db_max_overflow = _bounded_int(source, "EVENT_DB_MAX_OVERFLOW", default=1, low=0, high=3)
    audit_db_pool_size = _bounded_int(source, "AUDIT_DB_POOL_SIZE", default=1, low=1, high=4)
    audit_db_max_overflow = _bounded_int(source, "AUDIT_DB_MAX_OVERFLOW", default=0, low=0, high=3)
    connection_budget = (
        event_db_pool_size + event_db_max_overflow + audit_db_pool_size + audit_db_max_overflow
    )
    if connection_budget > MAX_DATABASE_CONNECTIONS_PER_PROCESS:
        raise WorkerConfigurationError(
            "combined worker database pools must not exceed 4 connections per process"
        )
    db_pool_timeout = _bounded_float(
        source, "DB_POOL_TIMEOUT_SECONDS", default=2.0, low=0.1, high=30.0
    )
    return WorkerSettings(
        environment=environment,
        broker_url=broker_url,
        batch_size=batch_size,
        idle_sleep_seconds=idle_sleep,
        broker_retry_seconds=broker_retry,
        metrics_port=metrics_port,
        snapshot_interval_seconds=snapshot_interval,
        event_db_pool_size=event_db_pool_size,
        event_db_max_overflow=event_db_max_overflow,
        audit_db_pool_size=audit_db_pool_size,
        audit_db_max_overflow=audit_db_max_overflow,
        db_pool_timeout_seconds=db_pool_timeout,
    )


def _bounded_int(source: Mapping[str, str], name: str, *, default: int, low: int, high: int) -> int:
    raw = source.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as error:
        raise WorkerConfigurationError(f"{name} must be an integer") from error
    if not low <= value <= high:
        raise WorkerConfigurationError(f"{name} must stay within {low}..{high}")
    return value


def _bounded_float(
    source: Mapping[str, str], name: str, *, default: float, low: float, high: float
) -> float:
    raw = source.get(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError as error:
        raise WorkerConfigurationError(f"{name} must be a number") from error
    if not low <= value <= high:
        raise WorkerConfigurationError(f"{name} must stay within {low}..{high}")
    return value


@dataclass(frozen=True, slots=True)
class AuditDeliverySettings:
    """Audit delivery inputs; the integrity key has no printable representation."""

    retention_days: int
    integrity_key: bytes = field(repr=False)


def load_audit_delivery_settings(
    environ: Mapping[str, str] | None = None,
) -> AuditDeliverySettings:
    """Load the approved audit retention and the injected integrity key, fail closed."""

    source = os.environ if environ is None else environ
    environment = source.get("APP_ENV", "development").strip().lower()
    if environment not in ALLOWED_ENVIRONMENTS:
        raise WorkerConfigurationError("APP_ENV must be an approved environment label")
    retention_days = _bounded_int(source, "AUDIT_RETENTION_DAYS", default=1_825, low=30, high=3_650)
    raw_key = source.get("AUDIT_INTEGRITY_KEY", "")
    if len(raw_key.encode("utf-8")) < 32:
        raise WorkerConfigurationError("AUDIT_INTEGRITY_KEY must provide at least 32 bytes")
    if environment in {"staging", "production"} and any(
        marker in raw_key.casefold() for marker in PLACEHOLDER_MARKERS
    ):
        raise WorkerConfigurationError(
            "placeholder integrity key is forbidden outside local/test environments"
        )
    return AuditDeliverySettings(
        retention_days=retention_days,
        integrity_key=raw_key.encode("utf-8"),
    )
