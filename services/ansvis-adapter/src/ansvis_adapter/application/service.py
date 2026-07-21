"""Coordinate authentication, validation, normalization and durable receipt."""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta

from ansvis_adapter.application.ports import (
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
from ansvis_adapter.schemas.events import declared_source_namespace, parse_and_normalize_event

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
            receipt = self._execute(
                payload,
                authorization_values=authorization_values,
                transport_secure=transport_secure,
            )
        except AnsvisAdapterError as exc:
            outcome = "conflict" if exc.code == "EVENT_IDEMPOTENCY_CONFLICT" else "rejected"
            self._metric(outcome)
            raise
        self._metric(receipt.outcome.value)
        return receipt

    def _execute(
        self,
        payload: Mapping[str, object],
        *,
        authorization_values: tuple[str, ...],
        transport_secure: bool,
    ) -> DurableReceipt:
        source_namespace = declared_source_namespace(payload)
        source = self._authenticator.authenticate(
            SourceAuthRequest(
                declared_source_namespace=source_namespace,
                authorization_values=authorization_values,
                transport_secure=transport_secure,
            )
        )
        if source.source_namespace != source_namespace:
            raise AnsvisAdapterError("EVENT_SOURCE_UNAUTHORIZED")

        event = parse_and_normalize_event(payload)
        if event.tenant_ref != source.tenant_ref or event.school_ref != source.school_ref:
            raise AnsvisAdapterError("EVENT_SOURCE_MAPPING_DENIED")
        self._validate_replay_window(event.occurred_at)
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

    def _metric(self, outcome: str) -> None:
        try:
            self._metrics.increment("event_ingestion_total", outcome=outcome)
        except Exception:
            return

    def _validate_replay_window(self, occurred_at: datetime) -> None:
        now = self._now()
        if now.tzinfo is None or now.utcoffset() is None:
            raise AnsvisAdapterError("TIME_SOURCE_UNHEALTHY")
        current = now.astimezone(UTC)
        if occurred_at > current + FUTURE_TOLERANCE:
            raise AnsvisAdapterError("TIME_EVENT_FUTURE")
        if occurred_at < current - REPLAY_WINDOW:
            raise AnsvisAdapterError("TIME_REPLAY_WINDOW_EXCEEDED")
