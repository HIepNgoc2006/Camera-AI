"""Framework-free values for durable event ingestion and outbox delivery."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

TOPIC_PATTERN = re.compile(r"^camera_ai\.events\.[a-z][a-z0-9_]{2,96}\.v1$")
REASON_CODE_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]{2,63}$")


@dataclass(frozen=True, slots=True, kw_only=True)
class ResolvedEventScope:
    """Authoritative internal references resolved outside producer-controlled input."""

    school_id: UUID
    source_id: UUID
    camera_id: UUID
    task_id: UUID
    verified: bool
    zone_id: UUID | None = None

    def __post_init__(self) -> None:
        if self.verified is not True:
            raise ValueError("event scope must be authoritatively verified")


@dataclass(frozen=True, slots=True, kw_only=True)
class PendingOutboxMessage:
    """One leased, versioned message safe for a downstream publisher."""

    outbox_message_id: UUID
    normalized_event_id: UUID
    claim_token: UUID
    topic: str
    contract_version: str
    payload: Mapping[str, object]
    attempt_count: int

    def __post_init__(self) -> None:
        if (
            TOPIC_PATTERN.fullmatch(self.topic) is None
            or self.contract_version != "normalized_outbox_v1"
            or not 0 <= self.attempt_count < 5
        ):
            raise ValueError("invalid pending outbox message")


class DispatchOutcome(StrEnum):
    EMPTY = "empty"
    PUBLISHED = "published"
    RETRY_SCHEDULED = "retry_scheduled"
    DEAD_LETTERED = "dead_lettered"


@dataclass(frozen=True, slots=True, kw_only=True)
class EventOperationalSnapshot:
    """Aggregate status containing no tenant, camera, person, event or evidence identifiers."""

    accepted_receipts: int
    pending_messages: int
    published_messages: int
    failed_messages: int
    retryable_attempts: int
    quarantined_conflicts: int
    delayed_messages: int
    oldest_pending_seconds: int

    def __post_init__(self) -> None:
        if any(
            value < 0
            for value in (
                self.accepted_receipts,
                self.pending_messages,
                self.published_messages,
                self.failed_messages,
                self.retryable_attempts,
                self.quarantined_conflicts,
                self.delayed_messages,
                self.oldest_pending_seconds,
            )
        ):
            raise ValueError("operational counters must be non-negative")
        if self.delayed_messages > self.pending_messages:
            raise ValueError("delayed messages cannot exceed pending messages")


class AlertSeverity(StrEnum):
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass(frozen=True, slots=True, kw_only=True)
class OperationalAlert:
    """A bounded alert signal with no free-form or high-cardinality labels."""

    code: str
    severity: AlertSeverity

    def __post_init__(self) -> None:
        if self.code not in {
            "EVENT_OUTBOX_DLQ_UNTRIAGED",
            "EVENT_OUTBOX_OLDEST_MESSAGE",
        }:
            raise ValueError("operational alert code is not allowlisted")


@dataclass(frozen=True, slots=True, kw_only=True)
class ReplayAuthorization:
    """Explicit operator authorization required before replaying a failed message."""

    actor_id: UUID
    reason_code: str
    approved: bool
    authorized_at: datetime

    def __post_init__(self) -> None:
        if (
            self.approved is not True
            or REASON_CODE_PATTERN.fullmatch(self.reason_code) is None
            or self.authorized_at.tzinfo is None
            or self.authorized_at.utcoffset() is None
        ):
            raise ValueError("invalid replay authorization")
