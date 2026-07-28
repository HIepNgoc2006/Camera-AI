from __future__ import annotations

from datetime import UTC, datetime, timedelta

from notification_service.application.capacity import DEFAULT_CAPACITY_MODEL
from notification_service.domain.policies import (
    BASE_BACKOFF_SECONDS,
    MAX_ATTEMPTS,
    MAX_INFLIGHT_RETRIES,
    retry_schedule,
)


def test_capacity_model_records_the_synthetic_morning_spike() -> None:
    model = DEFAULT_CAPACITY_MODEL
    assert model.recipient_deliveries == 1_800
    assert model.triangular_peak_rate_per_second == 6.0
    assert model.load_test_dispatch_rate_per_second == 60
    assert model.authorization_lane_utilization == 0.10
    assert model.max_inflight_retries == MAX_INFLIGHT_RETRIES == 5_000


def test_retry_budget_is_numeric_bounded_and_expiry_aware() -> None:
    now = datetime(2026, 7, 28, tzinfo=UTC)
    assert MAX_ATTEMPTS == 5
    assert BASE_BACKOFF_SECONDS == 2
    assert retry_schedule(
        attempt_count=0,
        now=now,
        expires_at=now + timedelta(minutes=1),
        retry_backlog=0,
        jitter=lambda maximum: maximum,
    ) == now + timedelta(seconds=3)
    assert (
        retry_schedule(
            attempt_count=4,
            now=now,
            expires_at=now + timedelta(minutes=1),
            retry_backlog=0,
            jitter=lambda maximum: maximum,
        )
        is None
    )
