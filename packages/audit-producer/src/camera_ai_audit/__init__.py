"""Shared audit-intent producer surface for Camera AI services.

Producing services build a shape-validated `AuditIntent` and hand it to an
`AuditIntentRecorder` (their own transactional outbox). Full action-policy validation stays in
the owning audit-log-service at delivery time; this package only guarantees the intent is
well-formed, minimized, and free of forbidden content.
"""

from __future__ import annotations

from camera_ai_audit.intents import (
    AUDIT_EVENT_SCHEMA_VERSION,
    AuditIntent,
    AuditIntentInvalidError,
    IntentResult,
)
from camera_ai_audit.ports import (
    AuditIntentRecorder,
    AuditRecorderUnavailableError,
    UnavailableAuditIntentRecorder,
)

__all__ = [
    "AUDIT_EVENT_SCHEMA_VERSION",
    "AuditIntent",
    "AuditIntentInvalidError",
    "AuditIntentRecorder",
    "AuditRecorderUnavailableError",
    "IntentResult",
    "UnavailableAuditIntentRecorder",
]
