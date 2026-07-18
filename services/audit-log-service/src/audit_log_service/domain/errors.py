"""Stable, redacted Audit Log Service errors."""

from __future__ import annotations

ERROR_MESSAGES = {
    "AUDIT_EVENT_INVALID": "The audit event failed validation.",
    "AUDIT_ACTION_UNKNOWN": "The audit action is not supported.",
    "AUDIT_CHANGE_FORBIDDEN": "The audit change summary is not allowed.",
    "AUDIT_DUPLICATE_CONFLICT": "The publisher event identity conflicts with existing evidence.",
    "AUDIT_UNAVAILABLE": "The audit evidence store is unavailable.",
    "AUDIT_INTEGRITY_FAILED": "Audit integrity verification failed.",
}


class AuditError(RuntimeError):
    """An error whose text never contains rejected input or provider details."""

    def __init__(self, code: str) -> None:
        if code not in ERROR_MESSAGES:
            code = "AUDIT_EVENT_INVALID"
        self.code = code
        self.safe_message = ERROR_MESSAGES[code]
        super().__init__(self.safe_message)

    def __str__(self) -> str:
        return f"{self.code}: {self.safe_message}"
