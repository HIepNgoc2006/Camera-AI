"""Stable redacted Attendance Service errors."""

from __future__ import annotations

ERROR_MESSAGES = {
    "ATTENDANCE_INPUT_INVALID": "The attendance input failed validation.",
    "ATTENDANCE_AUTHORITY_DENIED": "The attendance authority check was denied.",
    "ATTENDANCE_CONSENT_BLOCKED": "Attendance processing is blocked by consent policy.",
    "ATTENDANCE_NOT_FOUND": "The attendance record was not found.",
    "ATTENDANCE_VERSION_CONFLICT": "The attendance record changed before this request completed.",
    "ATTENDANCE_DUPLICATE_CONFLICT": "The event identity conflicts with an earlier event.",
    "ATTENDANCE_UNAVAILABLE": "The attendance store is unavailable.",
}


class AttendanceError(RuntimeError):
    """An error whose text never contains rejected input or provider details."""

    def __init__(self, code: str) -> None:
        if code not in ERROR_MESSAGES:
            code = "ATTENDANCE_INPUT_INVALID"
        self.code = code
        self.safe_message = ERROR_MESSAGES[code]
        super().__init__(self.safe_message)

    def __str__(self) -> str:
        return f"{self.code}: {self.safe_message}"
