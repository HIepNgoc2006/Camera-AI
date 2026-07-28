"""Explicit synthetic load model for the inactive Notification Service baseline."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CapacityModel:
    peak_concurrent_classes: int = 60
    recipients_per_class: int = 30
    arrival_window_seconds: int = 600
    authorization_batch_size: int = 30
    authorization_p95_seconds: float = 0.050
    load_test_dispatch_rate_per_second: int = 60
    max_inflight_retries: int = 5_000

    @property
    def recipient_deliveries(self) -> int:
        return self.peak_concurrent_classes * self.recipients_per_class

    @property
    def triangular_peak_rate_per_second(self) -> float:
        return 2 * self.recipient_deliveries / self.arrival_window_seconds

    @property
    def authorization_lane_utilization(self) -> float:
        batch_calls = self.load_test_dispatch_rate_per_second / self.authorization_batch_size
        return batch_calls * self.authorization_p95_seconds

    def validate(self) -> None:
        if (
            self.triangular_peak_rate_per_second != 6.0
            or self.authorization_lane_utilization > 0.10
            or self.max_inflight_retries > 5_000
        ):
            raise ValueError("notification capacity model exceeds the approved local profile")


DEFAULT_CAPACITY_MODEL = CapacityModel()
DEFAULT_CAPACITY_MODEL.validate()
