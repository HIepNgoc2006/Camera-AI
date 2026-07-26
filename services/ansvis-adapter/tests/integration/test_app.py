from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from ansvis_adapter.application.ports import (
    AuthenticatedSource,
    DurableReceipt,
    ReceiptOutcome,
    SourceAuthRequest,
)
from ansvis_adapter.config import MAX_EVENT_BODY_BYTES, Settings
from ansvis_adapter.domain.idempotency import IdempotencyDescriptor
from ansvis_adapter.domain.models import NormalizedAnsvisEvent
from ansvis_adapter.infrastructure.idempotency import ContractIdempotencyDeriver
from ansvis_adapter.infrastructure.unavailable import UnavailableDurableReceiptPort
from ansvis_adapter.main import create_app
from fastapi import FastAPI
from fastapi.testclient import TestClient


def event_payload() -> dict[str, object]:
    return {
        "schema_version": "ansvis_http_trigger_v1",
        "source_namespace": "ansvis.test.source",
        "source_event_id": "event_test_ansvis_0001",
        "event_type": "camera.health.changed",
        "tenant_ref": "tenant_test_0001",
        "school_ref": "school_test_0001",
        "camera_external_id": "camera_test_0001",
        "task_external_id": "task_test_0001",
        "event_time": "2030-01-01T00:00:00Z",
        "correlation_id": "corr_test_ansvis_0001",
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


class FakeFallbackKeys:
    def key_for(self, version: str) -> bytes | None:
        if version != "ansvis_fallback_idempotency_v1":
            return None
        return hashlib.sha256(b"SYNTHETIC_TEST_DATA_ONLY:route-fallback-key").digest()


def idempotency_deriver() -> ContractIdempotencyDeriver:
    return ContractIdempotencyDeriver(fallback_keys=FakeFallbackKeys())


class FakeReceiptPort:
    def __init__(self, outcome: ReceiptOutcome = ReceiptOutcome.ACCEPTED) -> None:
        self.outcome = outcome

    def record(
        self,
        event: NormalizedAnsvisEvent,
        source: AuthenticatedSource,
        idempotency: IdempotencyDescriptor,
    ) -> DurableReceipt:
        assert event.source_namespace == source.source_namespace
        return DurableReceipt(
            receipt_id="receipt_test_ansvis_0001",
            outcome=self.outcome,
            commit_confirmed=True,
            idempotency_key=idempotency.idempotency_key,
            canonical_fingerprint=idempotency.canonical_fingerprint,
        )


class FakeMetrics:
    def __init__(self) -> None:
        self.values: list[tuple[str, str]] = []
        self.observations: list[tuple[str, float]] = []
        self.gauges: list[tuple[str, float]] = []

    def increment(self, metric: str, *, outcome: str) -> None:
        self.values.append((metric, outcome))

    def observe(self, metric: str, *, seconds: float) -> None:
        self.observations.append((metric, seconds))

    def set_gauge(self, metric: str, *, value: float) -> None:
        self.gauges.append((metric, value))


def fixed_now() -> datetime:
    return datetime(2030, 1, 1, tzinfo=UTC)


def test_runtime_default_denies_unverified_source() -> None:
    with TestClient(create_app(Settings(environment="test", log_level="CRITICAL"))) as client:
        response = client.post(
            "/integration/ansvis/events",
            json=event_payload(),
            headers={"X-Request-ID": "req-test-default-deny"},
        )

    assert response.status_code == 401
    assert response.json() == {
        "error_code": "EVENT_SOURCE_UNAUTHORIZED",
        "message": "Request rejected.",
        "request_id": "req-test-default-deny",
    }


def test_committed_receipt_returns_minimal_accepted_ack() -> None:
    app = create_app(
        Settings(environment="test", log_level="CRITICAL"),
        authenticator=FakeAuthenticator(),
        idempotency_deriver=idempotency_deriver(),
        receipt_port=FakeReceiptPort(),
        now=fixed_now,
    )
    with TestClient(app, base_url="https://testserver") as client:
        response = client.post(
            "/integration/ansvis/events",
            json=event_payload(),
            headers={"X-Request-ID": "req-test-accepted"},
        )

    assert response.status_code == 202
    assert response.json() == {
        "schema_version": "ansvis_http_trigger_ack_v1",
        "outcome": "accepted",
        "receipt_id": "receipt_test_ansvis_0001",
        "request_id": "req-test-accepted",
        "correlation_id": "corr_test_ansvis_0001",
    }
    assert response.headers["X-Request-ID"] == "req-test-accepted"


def test_committed_duplicate_returns_200() -> None:
    app = create_app(
        Settings(environment="test", log_level="CRITICAL"),
        authenticator=FakeAuthenticator(),
        idempotency_deriver=idempotency_deriver(),
        receipt_port=FakeReceiptPort(ReceiptOutcome.DUPLICATE),
        now=fixed_now,
    )
    with TestClient(app, base_url="https://testserver") as client:
        response = client.post("/integration/ansvis/events", json=event_payload())

    assert response.status_code == 200
    assert response.json()["outcome"] == "duplicate"


def test_unavailable_durable_receipt_returns_503_without_ack() -> None:
    app = create_app(
        Settings(environment="test", log_level="CRITICAL"),
        authenticator=FakeAuthenticator(),
        idempotency_deriver=idempotency_deriver(),
        receipt_port=UnavailableDurableReceiptPort(),
        now=fixed_now,
    )
    with TestClient(app, base_url="https://testserver") as client:
        response = client.post(
            "/integration/ansvis/events",
            json=event_payload(),
            headers={"X-Request-ID": "req-test-no-receipt"},
        )

    assert response.status_code == 503
    assert response.json() == {
        "error_code": "EVENT_DURABLE_RECEIPT_UNAVAILABLE",
        "message": "Request rejected.",
        "request_id": "req-test-no-receipt",
    }
    assert "receipt_id" not in response.text


def test_content_type_and_body_limits_fail_before_business_processing() -> None:
    metrics = FakeMetrics()
    app = create_app(
        Settings(environment="test", log_level="CRITICAL"),
        authenticator=FakeAuthenticator(),
        receipt_port=FakeReceiptPort(),
        metrics=metrics,
        now=fixed_now,
    )
    with TestClient(app) as client:
        wrong_type = client.post(
            "/integration/ansvis/events",
            content=b"{}",
            headers={"Content-Type": "text/plain"},
        )
        oversized = client.post(
            "/integration/ansvis/events",
            content=b"{" + b"x" * MAX_EVENT_BODY_BYTES + b"}",
            headers={"Content-Type": "application/json"},
        )

    assert wrong_type.status_code == 415
    assert wrong_type.json()["error_code"] == "EVENT_CONTENT_TYPE_UNSUPPORTED"
    assert oversized.status_code == 413
    assert oversized.json()["error_code"] == "EVENT_BODY_TOO_LARGE"
    assert metrics.values == [
        ("event_ingestion_total", "rejected"),
        ("event_ingestion_total", "rejected"),
    ]


def test_invalid_json_and_unknown_fields_use_sanitized_error() -> None:
    app = create_app(
        Settings(environment="test", log_level="CRITICAL"),
        authenticator=FakeAuthenticator(),
        receipt_port=FakeReceiptPort(),
        now=fixed_now,
    )
    payload = event_payload()
    payload["raw_payload"] = "blocked_test_value"
    with TestClient(app) as client:
        invalid_json = client.post(
            "/integration/ansvis/events",
            content=b"not-json",
            headers={"Content-Type": "application/json"},
        )
        unknown_field = client.post("/integration/ansvis/events", json=payload)

    assert invalid_json.status_code == 422
    assert invalid_json.json()["error_code"] == "EVENT_SCHEMA_INVALID"
    assert unknown_field.status_code == 422
    assert unknown_field.json()["error_code"] == "EVENT_SCHEMA_INVALID"
    assert "blocked_test_value" not in unknown_field.text


def test_health_is_minimal_and_production_docs_are_disabled() -> None:
    with TestClient(create_app(Settings(environment="test", log_level="CRITICAL"))) as client:
        response = client.get("/healthz", headers={"X-Request-ID": "req-test-health"})
    assert response.json() == {"status": "ok", "request_id": "req-test-health"}

    production: FastAPI = create_app(Settings(environment="production", log_level="CRITICAL"))
    assert production.docs_url is None
    assert production.redoc_url is None
    assert production.openapi_url is None
