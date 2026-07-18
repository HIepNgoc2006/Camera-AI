"""Ports used by the append-only audit application service."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from audit_log_service.domain.integrity import IntegritySigner
from audit_log_service.domain.models import AppendOutcome, AuditEvent


class AuditRepository(Protocol):
    def append(
        self,
        event: AuditEvent,
        *,
        recorded_at: datetime,
        audit_event_id: UUID,
        signer: IntegritySigner,
    ) -> AppendOutcome:
        """Append once or return the semantically identical existing evidence."""

    def verify_partition(self, partition: str, signer: IntegritySigner) -> None:
        """Raise a redacted integrity error when the chain does not verify."""
