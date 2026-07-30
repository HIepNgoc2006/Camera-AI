"""Worker configuration fail-closed behaviour. All values are synthetic."""

from __future__ import annotations

import pytest
from event_outbox_worker.config import (
    WorkerConfigurationError,
    WorkerSettings,
    load_worker_settings,
)

LOCAL_URI = "amqp://127.0.0.1:5672/%2F"


def test_valid_local_settings_load_with_defaults() -> None:
    settings = load_worker_settings({"APP_ENV": "test", "EVENT_BROKER_URI": LOCAL_URI})

    assert settings.environment == "test"
    assert settings.batch_size == 50
    assert settings.idle_sleep_seconds == 1.0
    assert settings.broker_retry_seconds == 5.0
    assert settings.event_db_pool_size == 2
    assert settings.event_db_max_overflow == 1
    assert settings.audit_db_pool_size == 1
    assert settings.audit_db_max_overflow == 0
    assert settings.db_pool_timeout_seconds == 2.0


def test_broker_uri_is_required_and_scheme_checked() -> None:
    with pytest.raises(WorkerConfigurationError, match="EVENT_BROKER_URI is required"):
        load_worker_settings({"APP_ENV": "test"})
    with pytest.raises(WorkerConfigurationError, match="amqp"):
        load_worker_settings({"APP_ENV": "test", "EVENT_BROKER_URI": "http://broker.invalid"})


def test_production_requires_amqps_and_rejects_placeholders() -> None:
    with pytest.raises(WorkerConfigurationError, match="amqps"):
        load_worker_settings({"APP_ENV": "production", "EVENT_BROKER_URI": LOCAL_URI})
    with pytest.raises(WorkerConfigurationError, match="placeholder"):
        load_worker_settings(
            {
                "APP_ENV": "production",
                "EVENT_BROKER_URI": "amqps://broker.replace_with_host.internal/vhost",
            }
        )


@pytest.mark.parametrize(
    ("name", "value", "match"),
    [
        ("WORKER_BATCH_SIZE", "0", "1..50"),
        ("WORKER_BATCH_SIZE", "51", "1..50"),
        ("WORKER_BATCH_SIZE", "many", "integer"),
        ("WORKER_IDLE_SLEEP_SECONDS", "0", "0.1..60"),
        ("WORKER_BROKER_RETRY_SECONDS", "0.5", "1.0..300"),
        ("EVENT_DB_POOL_SIZE", "0", "1..4"),
        ("AUDIT_DB_MAX_OVERFLOW", "4", "0..3"),
        ("DB_POOL_TIMEOUT_SECONDS", "31", "0.1..30"),
    ],
)
def test_bounded_numeric_settings_fail_closed(name: str, value: str, match: str) -> None:
    with pytest.raises(WorkerConfigurationError, match=match):
        load_worker_settings({"APP_ENV": "test", "EVENT_BROKER_URI": LOCAL_URI, name: value})


def test_combined_database_pool_budget_fails_closed() -> None:
    with pytest.raises(WorkerConfigurationError, match="must not exceed 4"):
        load_worker_settings(
            {
                "APP_ENV": "test",
                "EVENT_BROKER_URI": LOCAL_URI,
                "EVENT_DB_POOL_SIZE": "3",
                "EVENT_DB_MAX_OVERFLOW": "1",
                "AUDIT_DB_POOL_SIZE": "1",
            }
        )


def test_settings_repr_never_contains_the_broker_url() -> None:
    settings = load_worker_settings({"APP_ENV": "test", "EVENT_BROKER_URI": LOCAL_URI})

    assert LOCAL_URI not in repr(settings)
    assert "127.0.0.1" not in repr(settings)
    assert isinstance(settings, WorkerSettings)
