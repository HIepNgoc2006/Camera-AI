"""Fail-closed Report Service configuration."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ReportSettings:
    minimum_cohort_size: int | None = None
    max_concurrent_exports_per_actor: int = 2
    max_queue_depth: int = 5_000
    artifact_ttl_seconds: int = 604_800
    signed_get_ttl_seconds: int = 60

    def validate(self) -> None:
        if self.minimum_cohort_size is not None and not 2 <= self.minimum_cohort_size <= 100:
            raise ValueError("REPORT_CONFIG_INVALID")
        if not 1 <= self.max_concurrent_exports_per_actor <= 20:
            raise ValueError("REPORT_CONFIG_INVALID")
        if not 1 <= self.max_queue_depth <= 20_000:
            raise ValueError("REPORT_CONFIG_INVALID")
        if self.artifact_ttl_seconds != 604_800 or not 1 <= self.signed_get_ttl_seconds <= 300:
            raise ValueError("REPORT_CONFIG_INVALID")
