from __future__ import annotations

import hashlib
import io
import logging
from datetime import UTC, datetime

from ansvis_adapter.application.ports import (
    AuthenticatedSource,
    DurableReceipt,
    RateLimitDecision,
    ReceiptOutcome,
    SourceAuthRequest,
)
from ansvis_adapter.config import Settings
from ansvis_adapter.domain.errors import AnsvisAdapterError
from ansvis_adapter.domain.idempotency import IdempotencyDescriptor
from ansvis_adapter.domain.models import NormalizedAnsvisEvent
from ansvis_adapter.infrastructure.idempotency import ContractIdempotencyDeriver
from ansvis_adapter.logging import JsonLogFormatter
from ansvis_adapter.main import create_app
from fastapi import FastAPI
from fastapi.testclient import TestClient


def event_payload() -> dict[str, object]:
    return {
        "schema_version": "ansvis_http_trigger_v1",
        "source_namespace": "ansvis.test.source",
        "source_event_id": "event_test_idempotency_0001",
        "event_type": "camera.health.changed",
        "tenant_ref": "tenant_test_0001",
        "school_ref": "school_test_0001",
        "camera_external_id": "camera_test_0001",
        "task_external_id": "task_test_0001",
        "event_time": "2030-01-01T00:00:00Z",
        "correlation_id": "corr_test_idempotency_0001",
        "attributes": {"status": "online"},
    }


class FakeAuthenticator:
    def authenticate(self, request: SourceAuthRequest) -> AuthenticatedSource:
        return AuthenticatedSource(
            source_namespace=request.declared_source_namespace,
            subject_ref="source_subject_test_0001",
            tenant_ref="tenant_test_0001",
            school_ref="school_test_0001",
        )


class PermittingRateLimiter:
    def check(self, source_namespace: str) -> RateLimitDecision:
        assert source_namespace == "ansvis.test.source"
        return RateLimitDecision(allowed=True)


class FakeFallbackKeys:
    def key_for(self, version: str) -> bytes | None:
        if version != "ansvis_fallback_idempotency_v1":
            return None
        return hashlib.sha256(b"SYNTHETIC_TEST_DATA_ONLY:route-idempotency-key").digest()


class SyntheticReceiptLedger:
    """Test-only model of the unique key/fingerprint transaction owned by Issue #61."""

    def __init__(self) -> None:
        self.records: dict[str, tuple[str, str]] = {}
        self.canonical_effects = 0
        self.descriptors: list[IdempotencyDescriptor] = []

    def record(
        self,
        event: NormalizedAnsvisEvent,
        source: AuthenticatedSource,
        idempotency: IdempotencyDescriptor,
    ) -> DurableReceipt:
        assert event.tenant_ref == source.tenant_ref
        self.descriptors.append(idempotency)
        existing = self.records.get(idempotency.idempotency_key)
        if existing is None:
            receipt_id = "receipt_test_idempotency_0001"
            self.records[idempotency.idempotency_key] = (
                idempotency.canonical_fingerprint,
                receipt_id,
            )
            self.canonical_effects += 1
            outcome = ReceiptOutcome.ACCEPTED
        else:
            fingerprint, receipt_id = existing
            if fingerprint != idempotency.canonical_fingerprint:
                raise AnsvisAdapterError("EVENT_IDEMPOTENCY_CONFLICT")
            outcome = ReceiptOutcome.DUPLICATE
        return DurableReceipt(
            receipt_id=receipt_id,
            outcome=outcome,
            commit_confirmed=True,
            idempotency_key=idempotency.idempotency_key,
            canonical_fingerprint=idempotency.canonical_fingerprint,
        )


def app_with(ledger: SyntheticReceiptLedger, *, logger: logging.Logger | None = None) -> FastAPI:
    return create_app(
        Settings(environment="test", log_level="CRITICAL" if logger is None else "INFO"),
        authenticator=FakeAuthenticator(),
        idempotency_deriver=ContractIdempotencyDeriver(fallback_keys=FakeFallbackKeys()),
        receipt_port=ledger,
        rate_limiter=PermittingRateLimiter(),
        request_logger=logger,
        now=lambda: datetime(2030, 1, 1, tzinfo=UTC),
    )


def test_ten_identical_retries_create_one_canonical_effect_and_one_receipt() -> None:
    ledger = SyntheticReceiptLedger()
    application = app_with(ledger)
    responses = []

    with TestClient(application, base_url="https://testserver") as client:
        for index in range(10):
            payload = event_payload()
            payload["correlation_id"] = f"corr_test_retry_{index:04d}"
            responses.append(client.post("/integration/ansvis/events", json=payload))

    assert responses[0].status_code == 202
    assert all(response.status_code == 200 for response in responses[1:])
    assert [response.json()["outcome"] for response in responses] == [
        "accepted",
        *(["duplicate"] * 9),
    ]
    assert len({response.json()["receipt_id"] for response in responses}) == 1
    assert ledger.canonical_effects == 1
    assert len(ledger.records) == 1


def test_same_identity_with_changed_content_is_masked_conflict() -> None:
    log_buffer = io.StringIO()
    handler = logging.StreamHandler(log_buffer)
    handler.setFormatter(JsonLogFormatter())
    request_logger = logging.Logger("ansvis-idempotency-route-test", level=logging.INFO)
    request_logger.addHandler(handler)
    ledger = SyntheticReceiptLedger()
    application = app_with(ledger, logger=request_logger)

    with TestClient(application, base_url="https://testserver") as client:
        accepted = client.post("/integration/ansvis/events", json=event_payload())
        changed = event_payload()
        changed["correlation_id"] = "corr_test_conflict_0001"
        changed["attributes"] = {"status": "offline"}
        conflict = client.post("/integration/ansvis/events", json=changed)

    assert accepted.status_code == 202
    assert conflict.status_code == 409
    assert conflict.json()["error_code"] == "EVENT_IDEMPOTENCY_CONFLICT"
    assert "receipt_id" not in conflict.text
    assert ledger.canonical_effects == 1
    assert len(ledger.records) == 1
    combined = log_buffer.getvalue()
    assert "EVENT_IDEMPOTENCY_CONFLICT" in combined
    for descriptor in ledger.descriptors:
        assert descriptor.idempotency_key not in conflict.text
        assert descriptor.idempotency_key not in combined
        assert descriptor.canonical_fingerprint not in conflict.text
        assert descriptor.canonical_fingerprint not in combined
    for marker in (
        "event_test_idempotency_0001",
        "tenant_test_0001",
        "source_subject_test_0001",
    ):
        assert marker not in conflict.text
        assert marker not in combined


def test_fallback_retry_is_deterministic_and_missing_deriver_fails_closed() -> None:
    ledger = SyntheticReceiptLedger()
    application = app_with(ledger)
    fallback = event_payload()
    fallback["source_event_id"] = None
    fallback["attributes"] = {
        "status": "online",
        "track_id": "track_test_0001",
        "detection_key": "detection_test_0001",
    }

    with TestClient(application, base_url="https://testserver") as client:
        first = client.post("/integration/ansvis/events", json=fallback)
        fallback["correlation_id"] = "corr_test_fallback_retry_0001"
        duplicate = client.post("/integration/ansvis/events", json=fallback)

    assert first.status_code == 202
    assert duplicate.status_code == 200
    assert duplicate.json()["outcome"] == "duplicate"
    assert ledger.canonical_effects == 1
    assert ledger.descriptors[0].idempotency_key.startswith("idem_fallback_v1_")

    unavailable_ledger = SyntheticReceiptLedger()
    unavailable_app = create_app(
        Settings(environment="test", log_level="CRITICAL"),
        authenticator=FakeAuthenticator(),
        receipt_port=unavailable_ledger,
        rate_limiter=PermittingRateLimiter(),
        now=lambda: datetime(2030, 1, 1, tzinfo=UTC),
    )
    with TestClient(unavailable_app, base_url="https://testserver") as client:
        unavailable = client.post("/integration/ansvis/events", json=event_payload())

    assert unavailable.status_code == 503
    assert unavailable.json()["error_code"] == "EVENT_DURABLE_RECEIPT_UNAVAILABLE"
    assert unavailable_ledger.canonical_effects == 0
