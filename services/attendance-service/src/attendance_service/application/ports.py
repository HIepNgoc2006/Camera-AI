"""Persistence port for the Attendance Service application boundary."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from attendance_service.domain.models import (
    AttendanceCorrectionOutcome,
    AttendanceCorrectionRequest,
    AttendanceIngestionOutcome,
    AttendanceIngestionRequest,
    AttendanceRecord,
    TrustedAttendanceContext,
)


class AttendanceRepository(Protocol):
    def ingest_event(self, request: AttendanceIngestionRequest) -> AttendanceIngestionOutcome:
        """Atomically apply one normalized event or return an identical retry."""

    def get_record(self, record_id: UUID, school_id: UUID) -> AttendanceRecord | None:
        """Return only a tenant-owned record."""

    def correct_record(
        self,
        request: AttendanceCorrectionRequest,
        context: TrustedAttendanceContext,
    ) -> AttendanceCorrectionOutcome:
        """Atomically lock, recheck scope/version, correct, and append history."""
