"""Stable redacted Consent Service errors."""

from __future__ import annotations

ERROR_MESSAGES = {
    "CONSENT_INPUT_INVALID": "The consent input failed validation.",
    "CONSENT_AUTHORITY_DENIED": "The consent authority check was denied.",
    "CONSENT_PURPOSE_INACTIVE": "The consent purpose is not active.",
    "CONSENT_ALREADY_EXISTS": "A consent record already exists for this purpose.",
    "CONSENT_NOT_FOUND": "The consent record was not found.",
    "CONSENT_VERSION_CONFLICT": "The consent record changed before this request completed.",
    "CONSENT_DUPLICATE_CONFLICT": "The idempotency identity conflicts with an earlier request.",
    "CONSENT_TRANSITION_DENIED": "The requested consent status transition is not allowed.",
    "CONSENT_UNAVAILABLE": "The consent store is unavailable.",
}


class ConsentError(RuntimeError):
    """An error whose text never contains rejected input or provider details."""

    def __init__(self, code: str) -> None:
        if code not in ERROR_MESSAGES:
            code = "CONSENT_INPUT_INVALID"
        self.code = code
        self.safe_message = ERROR_MESSAGES[code]
        super().__init__(self.safe_message)

    def __str__(self) -> str:
        return f"{self.code}: {self.safe_message}"
