"""Ports for source authentication and commit-before-ACK persistence."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from ansvis_adapter.domain.auth import RegisteredSource
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


class ReceiptOutcome(StrEnum):
    ACCEPTED = "accepted"
    DUPLICATE = "duplicate"


@dataclass(frozen=True, slots=True)
class DurableReceipt:
    """Receipt returned only after the storage transaction has a known result."""

    receipt_id: str
    outcome: ReceiptOutcome
    commit_confirmed: bool


class DurableReceiptPort(Protocol):
    def record(self, event: NormalizedAnsvisEvent, source: AuthenticatedSource) -> DurableReceipt:
        """Persist the normalized event and return its committed receipt outcome."""
