"""Ports for source authentication and commit-before-ACK persistence."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from ansvis_adapter.domain.auth import RegisteredSource
from ansvis_adapter.domain.idempotency import IdempotencyDescriptor
from ansvis_adapter.domain.ingestion import (
    EventOperationalSnapshot,
    PendingOutboxMessage,
    ResolvedEventScope,
)
from ansvis_adapter.domain.models import NormalizedAnsvisEvent


@dataclass(frozen=True, slots=True)
class SourceAuthRequest:
    """Authentication inputs; implementations must never log the authorization value."""

    declared_source_namespace: str
    authorization_values: tuple[str, ...]
    transport_secure: bool


@dataclass(frozen=True, slots=True)
class AuthenticatedSource:
    """Minimal verified identity passed beyond the authentication adapter."""

    source_namespace: str
    subject_ref: str
    tenant_ref: str
    school_ref: str


class SigningKeyProvider(Protocol):
    def key_for(self, key_id: str) -> bytes | None:
        """Return secret-managed verification key bytes, or None for an unknown key ID."""


class TokenRevocationChecker(Protocol):
    def is_revoked(self, token_id: str) -> bool:
        """Return revocation status; implementations must fail rather than guess."""


class RegisteredSourceRepository(Protocol):
    def find_by_subject(self, subject_ref: str) -> RegisteredSource | None:
        """Return the unique authoritative mapping for a verified token subject."""


class SourceAuthenticator(Protocol):
    def authenticate(self, request: SourceAuthRequest) -> AuthenticatedSource:
        """Verify the source or raise a stable fail-closed adapter error."""


class FallbackIdempotencyKeyProvider(Protocol):
    def key_for(self, version: str) -> bytes | None:
        """Return secret-managed fallback HMAC key bytes for one exact policy version."""


class IdempotencyDeriver(Protocol):
    def derive(
        self, event: NormalizedAnsvisEvent, source: AuthenticatedSource
    ) -> IdempotencyDescriptor:
        """Return the opaque key/fingerprint pair or fail closed."""


class ReceiptOutcome(StrEnum):
    ACCEPTED = "accepted"
    DUPLICATE = "duplicate"


@dataclass(frozen=True, slots=True)
class DurableReceipt:
    """Receipt returned only after the storage transaction has a known result."""

    receipt_id: str
    outcome: ReceiptOutcome
    commit_confirmed: bool
    idempotency_key: str
    canonical_fingerprint: str


class DurableReceiptPort(Protocol):
    def record(
        self,
        event: NormalizedAnsvisEvent,
        source: AuthenticatedSource,
        idempotency: IdempotencyDescriptor,
    ) -> DurableReceipt:
        """Atomically return accepted/duplicate or reject a conflicting fingerprint."""


class EventScopeResolver(Protocol):
    def resolve(
        self, event: NormalizedAnsvisEvent, source: AuthenticatedSource
    ) -> ResolvedEventScope:
        """Resolve approved source/camera/task IDs without querying another service schema."""


class OutboxRepository(Protocol):
    def claim_next(self, *, now: datetime) -> PendingOutboxMessage | None:
        """Lease one due message without allowing another worker to claim it."""

    def mark_published(
        self, message_id: UUID, claim_token: UUID, *, published_at: datetime
    ) -> None:
        """Confirm publish for the exact active lease."""

    def record_failure(
        self,
        message: PendingOutboxMessage,
        *,
        failed_at: datetime,
        next_retry_at: datetime | None,
        error_code: str,
    ) -> bool:
        """Record a bounded retry; return True when the message is dead-lettered."""

    def replay_failed(
        self,
        message_id: UUID,
        *,
        actor_id: UUID,
        reason_code: str,
        authorized_at: datetime,
    ) -> None:
        """Move one failed message back to pending after explicit authorization."""


class OperationalStatusRepository(Protocol):
    def snapshot(self, *, now: datetime) -> EventOperationalSnapshot:
        """Return identifier-free aggregate ingestion and outbox status."""


class EventPublisher(Protocol):
    def publish(self, *, topic: str, payload: Mapping[str, object]) -> None:
        """Publish one normalized payload or raise without exposing its content."""


class MetricsSink(Protocol):
    def increment(self, metric: str, *, outcome: str) -> None:
        """Increment an allowlisted low-cardinality metric."""
