"""Runtime defaults that cannot authenticate or acknowledge by accident."""

from __future__ import annotations

from ansvis_adapter.application.ports import (
    AuthenticatedSource,
    ConsentGate,
    DurableReceipt,
    DurableReceiptPort,
    IdempotencyDeriver,
    RateLimitDecision,
    SourceAuthenticator,
    SourceAuthRequest,
    SourceRateLimiter,
)
from ansvis_adapter.domain.consent import (
    CONSENT_UNAVAILABLE,
    ConsentGateDecision,
    ConsentGateRequest,
)
from ansvis_adapter.domain.errors import AnsvisAdapterError
from ansvis_adapter.domain.idempotency import IdempotencyDescriptor
from ansvis_adapter.domain.models import NormalizedAnsvisEvent


class UnavailableSourceAuthenticator(SourceAuthenticator):
    """Deny every source until approved key/revocation/source adapters are explicitly wired."""

    def authenticate(self, request: SourceAuthRequest) -> AuthenticatedSource:
        del request
        raise AnsvisAdapterError("EVENT_SOURCE_UNAUTHORIZED")


class UnavailableSourceRateLimiter(SourceRateLimiter):
    """Reject ingestion until a shared Redis-backed limiter is explicitly wired."""

    def check(self, source_namespace: str) -> RateLimitDecision:
        del source_namespace
        raise AnsvisAdapterError("EVENT_RATE_LIMIT_UNAVAILABLE")


class UnavailableIdempotencyDeriver(IdempotencyDeriver):
    """Deny ingestion until the approved V1 derivation policy is explicitly wired."""

    def derive(
        self, event: NormalizedAnsvisEvent, source: AuthenticatedSource
    ) -> IdempotencyDescriptor:
        del event, source
        raise AnsvisAdapterError("EVENT_DURABLE_RECEIPT_UNAVAILABLE")


class UnavailableDurableReceiptPort(DurableReceiptPort):
    """Never ACK until Issue #61 wires committed PostgreSQL storage."""

    def record(
        self,
        event: NormalizedAnsvisEvent,
        source: AuthenticatedSource,
        idempotency: IdempotencyDescriptor,
    ) -> DurableReceipt:
        del event, source, idempotency
        raise AnsvisAdapterError("EVENT_DURABLE_RECEIPT_UNAVAILABLE")


class UnavailableConsentGate(ConsentGate):
    """Defer every biometric event until an approved consent gate is explicitly wired.

    This is the mandatory default: with no gate configured, face and emotion
    events keep a durable deferred receipt and are never persisted with an
    unevaluated or fabricated consent status.
    """

    def evaluate(self, request: ConsentGateRequest) -> ConsentGateDecision:
        del request
        raise AnsvisAdapterError(CONSENT_UNAVAILABLE)
