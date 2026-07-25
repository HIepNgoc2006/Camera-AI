"""Persistence port for the Timekeeping Service application boundary."""

from __future__ import annotations

from datetime import date, datetime
from typing import Protocol
from uuid import UUID

from timekeeping_service.domain.models import (
    Shift,
    TimekeepingCorrectionOutcome,
    TimekeepingCorrectionRequest,
    TimekeepingIngestionOutcome,
    TimekeepingIngestionRequest,
    TimekeepingRecord,
    TrustedTimekeepingContext,
)


class TimekeepingRepository(Protocol):
    def get_effective_shift(
        self,
        shift_id: UUID,
        school_id: UUID,
        occurred_at: datetime,
    ) -> Shift | None:
        """Return only a service-owned shift version effective at the event instant."""

    def has_active_assignment(
        self,
        school_id: UUID,
        staff_id: UUID,
        shift_id: UUID,
        work_date: date,
    ) -> bool:
        """Check the service-owned assignment without querying another schema."""

    def ingest_event(self, request: TimekeepingIngestionRequest) -> TimekeepingIngestionOutcome:
        """Atomically apply one normalized event or return an identical retry."""

    def get_record(self, record_id: UUID, school_id: UUID) -> TimekeepingRecord | None:
        """Return only a school-owned record."""

    def correct_record(
        self,
        request: TimekeepingCorrectionRequest,
        context: TrustedTimekeepingContext,
    ) -> TimekeepingCorrectionOutcome:
        """Atomically lock, recheck scope/version, correct, and append history."""
