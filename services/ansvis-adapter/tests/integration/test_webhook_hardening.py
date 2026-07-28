from __future__ import annotations

import hashlib
import io
import json
import logging
from collections.abc import Mapping
from datetime import UTC, datetime
from statistics import quantiles
from time import perf_counter

import ansvis_adapter.api.events as events_api
import ansvis_adapter.application.service as service_module
import pytest
from ansvis_adapter.application.ports import (
    AuthenticatedSource,
    DurableReceipt,
    IdempotencyDeriver,
    RateLimitDecision,
    ReceiptOutcome,
    SourceAuthRequest,
    SourceRateLimiter,
)
from ansvis_adapter.application.service import IngestAnsvisEvent
from ansvis_adapter.config import MAX_EVENT_BODY_BYTES, Settings
from ansvis_adapter.domain.errors import AnsvisAdapterError
from ansvis_adapter.domain.idempotency import IdempotencyDescriptor
from ansvis_adapter.domain.models import NormalizedAnsvisEvent
from ansvis_adapter.infrastructure.idempotency import ContractIdempotencyDeriver
from ansvis_adapter.infrastructure.rate_limit import (
    BURST_REQUESTS,
    SUSTAINED_REQUESTS_PER_SECOND,
)
from ansvis_adapter.logging import JsonLogFormatter
from ansvis_adapter.main import create_app
from ansvis_adapter.schemas.events import (
    declared_event_time as parse_declared_event_time,
)
from ansvis_adapter.schemas.events import (
    parse_and_normalize_event as normalize_event,
)
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

NOW = datetime(2030, 1, 1, tzinfo=UTC)


def event_payload() -> dict[str, object]:
    return {
        "schema_version": "ansvis_http_trigger_v1",
        "source_namespace": "ansvis.test.source",
        "source_event_id": "event_test_hardening_0001",
        "event_type": "camera.health.changed",
        "tenant_ref": "tenant_test_0001",
        "school_ref": "school_test_0001",
        "camera_external_id": "camera_test_0001",
        "task_external_id": "task_test_0001",
        "event_time": "2030-01-01T00:00:00Z",
        "correlation_id": "corr_test_hardening_0001",
        "attributes": {"status": "online"},
    }


class FakeAuthenticator:
    def __init__(self, stages: list[str] | None = None) -> None:
        self.calls = 0
        self._stages = stages

    def authenticate(self, request: SourceAuthRequest) -> AuthenticatedSource:
        self.calls += 1
        if self._stages is not None:
            self._stages.append("authenticate_source_and_bearer_token")
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
        return hashlib.sha256(b"SYNTHETIC_TEST_DATA_ONLY:hardening-fallback-key").digest()


class RecordingIdempotencyDeriver:
    def __init__(self, stages: list[str] | None = None) -> None:
        self._delegate = ContractIdempotencyDeriver(fallback_keys=FakeFallbackKeys())
        self._stages = stages

    def derive(
        self, event: NormalizedAnsvisEvent, source: AuthenticatedSource
    ) -> IdempotencyDescriptor:
        if self._stages is not None:
            self._stages.append("derive_idempotency_and_canonical_fingerprint")
        return self._delegate.derive(event, source)


class RecordingReceiptPort:
    def __init__(self, stages: list[str] | None = None) -> None:
        self.calls = 0
        self.backlog = 0
        self._stages = stages

    def record(
        self,
        event: NormalizedAnsvisEvent,
        source: AuthenticatedSource,
        idempotency: IdempotencyDescriptor,
    ) -> DurableReceipt:
        del event, source
        self.calls += 1
        if self._stages is not None:
            self._stages.append("commit_durable_receipt_before_ack")
        return DurableReceipt(
            receipt_id="receipt_test_hardening_0001",
            outcome=ReceiptOutcome.ACCEPTED,
            commit_confirmed=True,
            idempotency_key=idempotency.idempotency_key,
            canonical_fingerprint=idempotency.canonical_fingerprint,
        )


class StaticRateLimiter:
    def __init__(
        self,
        decision: RateLimitDecision | None = None,
        *,
        fail: bool = False,
    ) -> None:
        self.decision = decision or RateLimitDecision(allowed=True)
        self.fail = fail
        self.calls = 0

    def check(self, source_namespace: str) -> RateLimitDecision:
        assert source_namespace == "ansvis.test.source"
        self.calls += 1
        if self.fail:
            raise AnsvisAdapterError("EVENT_RATE_LIMIT_UNAVAILABLE")
        return self.decision


class SimulatedProfileLimiter:
    """Token bucket driven at 200 rps without wall-clock sleeping."""

    def __init__(self) -> None:
        self.tokens = float(BURST_REQUESTS)
        self.now = 0.0
        self.updated_at = 0.0

    def check(self, source_namespace: str) -> RateLimitDecision:
        assert source_namespace == "ansvis.test.source"
        elapsed = self.now - self.updated_at
        self.tokens = min(
            float(BURST_REQUESTS),
            self.tokens + elapsed * SUSTAINED_REQUESTS_PER_SECOND,
        )
        self.updated_at = self.now
        if self.tokens >= 1:
            self.tokens -= 1
            decision = RateLimitDecision(allowed=True)
        else:
            decision = RateLimitDecision(allowed=False, retry_after_seconds=1)
        self.now += 0.005
        return decision


class RecordingMetrics:
    def __init__(self) -> None:
        self.counters: list[tuple[str, str]] = []

    def increment(self, metric: str, *, outcome: str) -> None:
        self.counters.append((metric, outcome))

    def observe(self, metric: str, *, seconds: float) -> None:
        del metric, seconds

    def set_gauge(self, metric: str, *, value: float) -> None:
        del metric, value


def app_with(
    *,
    limiter: SourceRateLimiter,
    authenticator: FakeAuthenticator | None = None,
    receipt: RecordingReceiptPort | None = None,
    metrics: RecordingMetrics | None = None,
    logger: logging.Logger | None = None,
    idempotency: IdempotencyDeriver | None = None,
) -> FastAPI:
    return create_app(
        Settings(environment="test", log_level="CRITICAL"),
        authenticator=authenticator or FakeAuthenticator(),
        idempotency_deriver=idempotency or RecordingIdempotencyDeriver(),
        receipt_port=receipt or RecordingReceiptPort(),
        rate_limiter=limiter,
        metrics=metrics,
        request_logger=logger,
        now=lambda: NOW,
    )


def test_rate_limit_rejection_has_retry_after_and_never_reaches_auth_or_receipt() -> None:
    limiter = StaticRateLimiter(RateLimitDecision(allowed=False, retry_after_seconds=2))
    authenticator = FakeAuthenticator()
    receipt = RecordingReceiptPort()
    metrics = RecordingMetrics()
    application = app_with(
        limiter=limiter,
        authenticator=authenticator,
        receipt=receipt,
        metrics=metrics,
    )

    with TestClient(application, base_url="https://testserver") as client:
        response = client.post("/integration/ansvis/events", json=event_payload())

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "2"
    assert response.json()["error_code"] == "EVENT_RATE_LIMITED"
    assert authenticator.calls == 0
    assert receipt.calls == 0
    assert ("event_ingestion_rejections_total", "rate_limited") in metrics.counters


def test_unavailable_limiter_fails_closed_before_authentication() -> None:
    limiter = StaticRateLimiter(fail=True)
    authenticator = FakeAuthenticator()
    application = app_with(limiter=limiter, authenticator=authenticator)

    with TestClient(application, base_url="https://testserver") as client:
        response = client.post("/integration/ansvis/events", json=event_payload())

    assert response.status_code == 503
    assert response.json()["error_code"] == "EVENT_RATE_LIMIT_UNAVAILABLE"
    assert authenticator.calls == 0


def test_nested_array_bomb_is_stable_pre_auth_4xx_without_stack_trace() -> None:
    log_buffer = io.StringIO()
    handler = logging.StreamHandler(log_buffer)
    handler.setFormatter(JsonLogFormatter())
    logger = logging.Logger("ansvis-hardening-nested-array", level=logging.INFO)
    logger.addHandler(handler)
    authenticator = FakeAuthenticator()
    raw = json.dumps(
        {
            "source_namespace": "ansvis.test.source",
            "attributes": [[[[[[[[[[[[[[[[[0]]]]]]]]]]]]]]]]],
            "padding": "x" * 60_000,
        },
        separators=(",", ":"),
    ).encode()
    assert len(raw) <= MAX_EVENT_BODY_BYTES
    application = app_with(
        limiter=StaticRateLimiter(),
        authenticator=authenticator,
        logger=logger,
    )

    with TestClient(application, base_url="https://testserver") as client:
        response = client.post(
            "/integration/ansvis/events",
            content=raw,
            headers={"Content-Type": "application/json"},
        )

    combined = log_buffer.getvalue()
    assert response.status_code == 422
    assert response.json()["error_code"] == "EVENT_SCHEMA_INVALID"
    assert authenticator.calls == 0
    assert "Traceback" not in combined
    assert "RecursionError" not in combined
    assert '"status_code":500' not in combined


def test_contract_processing_order_is_exact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stages: list[str] = []
    original_bounded = events_api._bounded_json_body
    original_mapping = IngestAnsvisEvent._validate_source_mapping

    async def bounded(request: Request) -> bytes:
        stages.append("enforce_content_type_body_size_and_rate_limit")
        return await original_bounded(request)

    def captured_now() -> datetime:
        stages.extend(
            [
                "capture_trusted_receipt_time_and_request_id",
                "verify_receiver_clock_health",
            ]
        )
        return NOW

    def event_time(payload: Mapping[str, object]) -> datetime:
        stages.append("validate_event_timestamp_and_replay_nonce")
        return parse_declared_event_time(payload)

    def normalize(payload: Mapping[str, object]) -> NormalizedAnsvisEvent:
        stages.append("validate_schema_event_time_and_event_type")
        return normalize_event(payload)

    def mapping(event: NormalizedAnsvisEvent, source: AuthenticatedSource) -> None:
        stages.append("validate_source_camera_task_mapping")
        return original_mapping(event, source)

    monkeypatch.setattr(events_api, "_bounded_json_body", bounded)
    monkeypatch.setattr(service_module, "declared_event_time", event_time)
    monkeypatch.setattr(service_module, "parse_and_normalize_event", normalize)
    monkeypatch.setattr(
        IngestAnsvisEvent,
        "_validate_source_mapping",
        staticmethod(mapping),
    )
    application = create_app(
        Settings(environment="test", log_level="CRITICAL"),
        authenticator=FakeAuthenticator(stages),
        idempotency_deriver=RecordingIdempotencyDeriver(stages),
        receipt_port=RecordingReceiptPort(stages),
        rate_limiter=StaticRateLimiter(),
        now=captured_now,
    )

    with TestClient(application, base_url="https://testserver") as client:
        response = client.post("/integration/ansvis/events", json=event_payload())

    assert response.status_code == 202
    assert stages == [
        "capture_trusted_receipt_time_and_request_id",
        "verify_receiver_clock_health",
        "enforce_content_type_body_size_and_rate_limit",
        "authenticate_source_and_bearer_token",
        "validate_event_timestamp_and_replay_nonce",
        "validate_schema_event_time_and_event_type",
        "validate_source_camera_task_mapping",
        "derive_idempotency_and_canonical_fingerprint",
        "commit_durable_receipt_before_ack",
    ]


def test_declared_and_streamed_oversize_are_413_under_200ms_p95() -> None:
    authenticator = FakeAuthenticator()
    application = app_with(
        limiter=StaticRateLimiter(),
        authenticator=authenticator,
    )
    overflow = b"{" + b"x" * MAX_EVENT_BODY_BYTES + b"}"
    durations: list[float] = []

    with TestClient(application, base_url="https://testserver") as client:
        for _ in range(20):
            started = perf_counter()
            declared = client.post(
                "/integration/ansvis/events",
                content=b"{}",
                headers={
                    "Content-Type": "application/json",
                    "Content-Length": str(MAX_EVENT_BODY_BYTES + 1),
                },
            )
            durations.append(perf_counter() - started)
            started = perf_counter()
            streamed = client.post(
                "/integration/ansvis/events",
                content=overflow,
                headers={
                    "Content-Type": "application/json",
                    "Content-Length": "1",
                },
            )
            durations.append(perf_counter() - started)
            assert declared.status_code == 413
            assert streamed.status_code == 413

    p95 = quantiles(durations, n=20)[18]
    assert p95 <= 0.2
    assert authenticator.calls == 0


def test_local_200_rps_60_second_profile_has_no_5xx_or_backlog_growth() -> None:
    limiter = SimulatedProfileLimiter()
    receipt = RecordingReceiptPort()
    application = app_with(limiter=limiter, receipt=receipt)
    statuses: dict[int, int] = {}

    with TestClient(application, base_url="https://testserver") as client:
        for _ in range(12_000):
            response = client.post("/integration/ansvis/events", json=event_payload())
            statuses[response.status_code] = statuses.get(response.status_code, 0) + 1

    assert 3_199 <= statuses[202] <= 3_200
    assert 8_800 <= statuses[429] <= 8_801
    assert statuses[429] / 12_000 == pytest.approx(0.7334, abs=0.0001)
    assert not any(status >= 500 for status in statuses)
    assert receipt.calls == statuses[202]
    assert receipt.backlog == 0
