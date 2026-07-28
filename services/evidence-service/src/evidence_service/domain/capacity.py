"""Attachment-ratio capacity model and fail-closed alert threshold."""

from __future__ import annotations

from dataclasses import dataclass

from evidence_service.domain.errors import EvidenceError

MODELED_EVENTS_PER_DAY = 1_428_000
MODELED_AVERAGE_OBJECT_BYTES = 200_000
WORST_CASE_GB_PER_DAY = MODELED_EVENTS_PER_DAY * MODELED_AVERAGE_OBJECT_BYTES / 1_000_000_000


@dataclass(frozen=True, slots=True)
class AttachmentRatioPolicy:
    expected_ratio: float
    alert_threshold: float
    minimum_window_events: int = 100

    def __post_init__(self) -> None:
        if (
            not 0 <= self.expected_ratio <= 1
            or not self.expected_ratio < self.alert_threshold <= 1
            or not 1 <= self.minimum_window_events <= 1_000_000
        ):
            raise EvidenceError("EVIDENCE_CAPACITY_CONFIGURATION_INVALID")

    def ratio(self, *, attached_events: int, total_events: int) -> float:
        if not 0 <= attached_events <= total_events:
            raise EvidenceError("EVIDENCE_CAPACITY_SAMPLE_INVALID")
        return 0.0 if total_events == 0 else attached_events / total_events

    def should_alert(self, *, attached_events: int, total_events: int) -> bool:
        ratio = self.ratio(attached_events=attached_events, total_events=total_events)
        return total_events >= self.minimum_window_events and ratio > self.alert_threshold

    def expected_gb_per_day(self) -> float:
        return WORST_CASE_GB_PER_DAY * self.expected_ratio
