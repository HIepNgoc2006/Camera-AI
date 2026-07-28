from __future__ import annotations

from time import perf_counter

from notification_service.application.capacity import DEFAULT_CAPACITY_MODEL


def test_synthetic_triangular_arrival_profile_stays_inside_local_budget() -> None:
    """Exercise the recorded fake-recipient profile without network/provider access."""

    model = DEFAULT_CAPACITY_MODEL
    peak = model.triangular_peak_rate_per_second
    buckets = tuple(
        round(peak * (1 - abs(second - 300) / 300))
        for second in range(model.arrival_window_seconds)
    )
    assert sum(buckets) == model.recipient_deliveries
    assert max(buckets) == 6

    started = perf_counter()
    authorizations = 0
    for offset in range(0, model.recipient_deliveries, model.authorization_batch_size):
        authorizations += min(
            model.authorization_batch_size,
            model.recipient_deliveries - offset,
        )
    elapsed = perf_counter() - started

    assert authorizations == 1_800
    assert elapsed < 0.050
    assert model.authorization_lane_utilization <= 0.10
    assert model.load_test_dispatch_rate_per_second == 60
