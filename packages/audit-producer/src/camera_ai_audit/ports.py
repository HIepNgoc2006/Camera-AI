"""Recorder port each producing service implements with its own transactional outbox."""

from __future__ import annotations

from typing import Protocol

from camera_ai_audit.intents import AuditIntent


class AuditRecorderUnavailableError(RuntimeError):
    """Raised when no approved audit outbox is wired; carries only a stable code."""

    def __init__(self) -> None:
        super().__init__("AUDIT_RECORDER_UNAVAILABLE")


class AuditIntentRecorder(Protocol):
    def record(self, intent: AuditIntent) -> None:
        """Durably enqueue one intent in the caller's own outbox, idempotent per intent."""


class UnavailableAuditIntentRecorder:
    """Fail-closed default: a service without a wired audit outbox cannot pretend to audit."""

    def record(self, intent: AuditIntent) -> None:
        del intent
        raise AuditRecorderUnavailableError
