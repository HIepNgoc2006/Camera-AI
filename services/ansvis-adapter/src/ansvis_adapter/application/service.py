"""Coordinate authentication, validation, normalization and durable receipt."""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta

from ansvis_adapter.application.ports import (
    AuthenticatedSource,
    DurableReceipt,
    DurableReceiptPort,
    IdempotencyDeriver,
    MetricsSink,
    ReceiptOutcome,
    SourceAuthenticator,
    SourceAuthRequest,
)
from ansvis_adapter.application.telemetry import NullMetricsSink
from ansvis_adapter.domain.errors import AnsvisAdapterError
from ansvis_adapter.domain.models import NormalizedAnsvisEvent
from ansvis_adapter.schemas.events import (
    declared_event_time,
    declared_source_namespace,
    parse_and_normalize_event,
)

RECEIPT_ID_PATTERN = re.compile(r"^receipt_[A-Za-z0-9_-]{8,120}$")
FUTURE_TOLERANCE = timedelta(seconds=30)
REPLAY_WINDOW = timedelta(seconds=300)


def system_utc_now() -> datetime:
    return datetime.now(UTC)


class IngestAnsvisEvent:
    """Fail closed unless identity, event policy and durable commit all succeed."""

    def __init__(
        self,
        authenticator: SourceAuthenticator,
        idempotency_deriver: IdempotencyDeriver,
        receipt_port: DurableReceiptPort,
        *,
        metrics: MetricsSink | None = None,
        now: Callable[[], datetime] = system_utc_now,
    ) -> None:
        self._authenticator = authenticator
        self._idempotency_deriver = idempotency_deriver
        self._receipt_port = receipt_port
        self._metrics = metrics or NullMetricsSink()
        self._now = now

    def execute(
        self,
        payload: Mapping[str, object],
        *,
        authorization_values: tuple[str, ...],
        transport_secure: bool,
    ) -> DurableReceipt:
        try:
            received_at = self.capture_trusted_receipt_time()
            source_namespace = declared_source_namespace(payload)
            source = self.authenticate_source(
                source_namespace,
                authorization_values=authorization_values,
                transport_secure=transport_secure,
            )
            receipt = self._execute_authenticated(payload, source, received_at=received_at)
        except AnsvisAdapterError as exc:
            outcome = "conflict" if exc.code == "EVENT_IDEMPOTENCY_CONFLICT" else "rejected"
            self._metric(outcome)
            raise
        self._metric(receipt.outcome.value)
        return receipt

    def capture_trusted_receipt_time(self) -> datetime:
        """Capture and validate the receiver clock once for the entire request."""

        now = self._now()
        if now.tzinfo is None or now.utcoffset() is None:
            raise AnsvisAdapterError("TIME_SOURCE_UNHEALTHY")
        return now.astimezone(UTC)

    def authenticate_source(
        self,
        source_namespace: str,
        *,
        authorization_values: tuple[str, ...],
        transport_secure: bool,
    ) -> AuthenticatedSource:
        source = self._authenticator.authenticate(
            SourceAuthRequest(
                declared_source_namespace=source_namespace,
                authorization_values=authorization_values,
                transport_secure=transport_secure,
            )
        )
        if source.source_namespace != source_namespace:
            raise AnsvisAdapterError("EVENT_SOURCE_UNAUTHORIZED")
        return source

    def execute_authenticated(
        self,
        payload: Mapping[str, object],
        source: AuthenticatedSource,
        *,
        received_at: datetime,
    ) -> DurableReceipt:
        try:
            receipt = self._execute_authenticated(payload, source, received_at=received_at)
        except AnsvisAdapterError as exc:
            outcome = "conflict" if exc.code == "EVENT_IDEMPOTENCY_CONFLICT" else "rejected"
            self._metric(outcome)
            raise
        self._metric(receipt.outcome.value)
        return receipt

    def _execute_authenticated(
        self,
        payload: Mapping[str, object],
        source: AuthenticatedSource,
        *,
        received_at: datetime,
    ) -> DurableReceipt:
        self._validate_replay_window(declared_event_time(payload), received_at=received_at)
        event = parse_and_normalize_event(payload)
        self._validate_source_mapping(event, source)
        try:
            idempotency = self._idempotency_deriver.derive(event, source)
        except AnsvisAdapterError:
            raise
        except Exception:
            raise AnsvisAdapterError("EVENT_DURABLE_RECEIPT_UNAVAILABLE") from None
        try:
            receipt = self._receipt_port.record(event, source, idempotency)
        except AnsvisAdapterError:
            raise
        except Exception:
            raise AnsvisAdapterError("EVENT_DURABLE_RECEIPT_UNAVAILABLE") from None
        if (
            not receipt.commit_confirmed
            or not isinstance(receipt.outcome, ReceiptOutcome)
            or RECEIPT_ID_PATTERN.fullmatch(receipt.receipt_id) is None
            or receipt.idempotency_key != idempotency.idempotency_key
            or receipt.canonical_fingerprint != idempotency.canonical_fingerprint
        ):
            raise AnsvisAdapterError("EVENT_DURABLE_RECEIPT_UNAVAILABLE")
        return receipt

    @staticmethod
    def _validate_source_mapping(event: NormalizedAnsvisEvent, source: AuthenticatedSource) -> None:
        if event.source_namespace != source.source_namespace:
            raise AnsvisAdapterError("EVENT_SOURCE_UNAUTHORIZED")
        if event.tenant_ref != source.tenant_ref or event.school_ref != source.school_ref:
            raise AnsvisAdapterError("EVENT_SOURCE_MAPPING_DENIED")

    def _metric(self, outcome: str) -> None:
        try:
            self._metrics.increment("event_ingestion_total", outcome=outcome)
        except Exception:
            return

    def _validate_replay_window(self, occurred_at: datetime, *, received_at: datetime) -> None:
        if received_at.tzinfo is None or received_at.utcoffset() is None:
            raise AnsvisAdapterError("TIME_SOURCE_UNHEALTHY")
        current = received_at.astimezone(UTC)
        if occurred_at > current + FUTURE_TOLERANCE:
            raise AnsvisAdapterError("TIME_EVENT_FUTURE")
        if occurred_at < current - REPLAY_WINDOW:
            raise AnsvisAdapterError("TIME_REPLAY_WINDOW_EXCEEDED")
