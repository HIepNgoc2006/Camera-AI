"""Stable redacted Timekeeping Service errors."""

from __future__ import annotations

ERROR_MESSAGES = {
    "TIMEKEEPING_INPUT_INVALID": "The timekeeping input failed validation.",
    "TIMEKEEPING_AUTHORITY_DENIED": "The timekeeping authority check was denied.",
    "TIMEKEEPING_CONSENT_BLOCKED": "Timekeeping processing is blocked by consent policy.",
    "TIMEKEEPING_SHIFT_NOT_FOUND": "The applicable shift was not found.",
    "TIMEKEEPING_ASSIGNMENT_DENIED": "No applicable staff shift assignment was found.",
    "TIMEKEEPING_NOT_FOUND": "The timekeeping record was not found.",
    "TIMEKEEPING_VERSION_CONFLICT": "The timekeeping record changed before this request completed.",
    "TIMEKEEPING_DUPLICATE_CONFLICT": "The event identity conflicts with an earlier event.",
    "TIMEKEEPING_UNAVAILABLE": "The timekeeping store is unavailable.",
}


class TimekeepingError(RuntimeError):
    """An error whose text never contains rejected input or provider details."""

    def __init__(self, code: str) -> None:
        if code not in ERROR_MESSAGES:
            code = "TIMEKEEPING_INPUT_INVALID"
        self.code = code
        self.safe_message = ERROR_MESSAGES[code]
        super().__init__(self.safe_message)

    def __str__(self) -> str:
        return f"{self.code}: {self.safe_message}"
