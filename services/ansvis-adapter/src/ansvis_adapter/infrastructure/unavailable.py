"""Runtime defaults that cannot authenticate or acknowledge by accident."""

from __future__ import annotations

from ansvis_adapter.application.ports import (
    AuthenticatedSource,
    DurableReceipt,
    DurableReceiptPort,
    SourceAuthenticator,
    SourceAuthRequest,
)
from ansvis_adapter.domain.errors import AnsvisAdapterError
from ansvis_adapter.domain.models import NormalizedAnsvisEvent


class UnavailableSourceAuthenticator(SourceAuthenticator):
    """Deny every source until Issue #19 provides a verified implementation."""

    def authenticate(self, request: SourceAuthRequest) -> AuthenticatedSource:
        del request
        raise AnsvisAdapterError("EVENT_SOURCE_UNAUTHORIZED")


class UnavailableDurableReceiptPort(DurableReceiptPort):
    """Never ACK until Issue #61 wires committed PostgreSQL storage."""

    def record(self, event: NormalizedAnsvisEvent, source: AuthenticatedSource) -> DurableReceipt:
        del event, source
        raise AnsvisAdapterError("EVENT_DURABLE_RECEIPT_UNAVAILABLE")
