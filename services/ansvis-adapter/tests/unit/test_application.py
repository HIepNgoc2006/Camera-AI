from __future__ import annotations

from datetime import UTC, datetime

import pytest
from ansvis_adapter.application.ports import (
    AuthenticatedSource,
    DurableReceipt,
    ReceiptOutcome,
    SourceAuthRequest,
)
from ansvis_adapter.application.service import IngestAnsvisEvent
from ansvis_adapter.domain.errors import AnsvisAdapterError
from ansvis_adapter.domain.idempotency import (
    IdempotencyDescriptor,
    IdempotencyIdentityKind,
)
from ansvis_adapter.domain.models import NormalizedAnsvisEvent
from ansvis_adapter.infrastructure.unavailable import (
    UnavailableDurableReceiptPort,
    UnavailableIdempotencyDeriver,
)

IDEMPOTENCY = IdempotencyDescriptor(
    identity_kind=IdempotencyIdentityKind.SOURCE,
    idempotency_key="idem_source_v1_" + "1" * 64,
    canonical_fingerprint="sha256:" + "2" * 64,
)


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
    def __init__(
        self,
        source_namespace: str = "ansvis.test.source",
        *,
        tenant_ref: str = "tenant_test_0001",
        school_ref: str = "school_test_0001",
    ) -> None:
        self.source_namespace = source_namespace
        self.tenant_ref = tenant_ref
        self.school_ref = school_ref
        self.requests: list[SourceAuthRequest] = []

    def authenticate(self, request: SourceAuthRequest) -> AuthenticatedSource:
        self.requests.append(request)
        return AuthenticatedSource(
            source_namespace=self.source_namespace,
            subject_ref="source_subject_test_0001",
            tenant_ref=self.tenant_ref,
            school_ref=self.school_ref,
        )


class FakeIdempotencyDeriver:
    def __init__(self, descriptor: IdempotencyDescriptor = IDEMPOTENCY) -> None:
        self.descriptor = descriptor
        self.events: list[NormalizedAnsvisEvent] = []

    def derive(
        self, event: NormalizedAnsvisEvent, source: AuthenticatedSource
    ) -> IdempotencyDescriptor:
        assert event.source_namespace == source.source_namespace
        self.events.append(event)
        return self.descriptor


class FakeReceiptPort:
    def __init__(
        self,
        *,
        committed: bool = True,
        outcome: ReceiptOutcome = ReceiptOutcome.ACCEPTED,
    ) -> None:
        self.committed = committed
        self.outcome = outcome
        self.events: list[NormalizedAnsvisEvent] = []

    def record(
        self,
        event: NormalizedAnsvisEvent,
        source: AuthenticatedSource,
        idempotency: IdempotencyDescriptor,
    ) -> DurableReceipt:
        assert source.subject_ref == "source_subject_test_0001"
        self.events.append(event)
        return DurableReceipt(
            receipt_id="receipt_test_ansvis_0001",
            outcome=self.outcome,
            commit_confirmed=self.committed,
            idempotency_key=idempotency.idempotency_key,
            canonical_fingerprint=idempotency.canonical_fingerprint,
        )


class InconsistentReceiptPort:
    def record(
        self,
        event: NormalizedAnsvisEvent,
        source: AuthenticatedSource,
        idempotency: IdempotencyDescriptor,
    ) -> DurableReceipt:
        del event, source
        return DurableReceipt(
            receipt_id="receipt_test_ansvis_0001",
            outcome=ReceiptOutcome.ACCEPTED,
            commit_confirmed=True,
            idempotency_key="idem_source_v1_" + "3" * 64,
            canonical_fingerprint=idempotency.canonical_fingerprint,
        )


class ConflictReceiptPort:
    def record(
        self,
        event: NormalizedAnsvisEvent,
        source: AuthenticatedSource,
        idempotency: IdempotencyDescriptor,
    ) -> DurableReceipt:
        del event, source, idempotency
        raise AnsvisAdapterError("EVENT_IDEMPOTENCY_CONFLICT")


class FakeMetrics:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.values: list[tuple[str, str]] = []
        self.observations: list[tuple[str, float]] = []
        self.gauges: list[tuple[str, float]] = []

    def increment(self, metric: str, *, outcome: str) -> None:
        if self.fail:
            raise RuntimeError("synthetic telemetry outage")
        self.values.append((metric, outcome))

    def observe(self, metric: str, *, seconds: float) -> None:
        self.observations.append((metric, seconds))

    def set_gauge(self, metric: str, *, value: float) -> None:
        self.gauges.append((metric, value))


def fixed_now() -> datetime:
    return datetime(2030, 1, 1, tzinfo=UTC)


def test_use_case_authenticates_before_record_and_returns_committed_receipt() -> None:
    auth = FakeAuthenticator()
    idempotency = FakeIdempotencyDeriver()
    receipts = FakeReceiptPort()
    service = IngestAnsvisEvent(auth, idempotency, receipts, now=fixed_now)

    receipt = service.execute(event_payload(), authorization_values=(), transport_secure=False)

    assert receipt.outcome is ReceiptOutcome.ACCEPTED
    assert len(auth.requests) == 1
    assert len(idempotency.events) == 1
    assert len(receipts.events) == 1


def test_ingestion_metrics_use_only_bounded_outcomes_and_never_change_ack() -> None:
    metrics = FakeMetrics()
    accepted = IngestAnsvisEvent(
        FakeAuthenticator(),
        FakeIdempotencyDeriver(),
        FakeReceiptPort(),
        metrics=metrics,
        now=fixed_now,
    ).execute(event_payload(), authorization_values=(), transport_secure=True)
    duplicate = IngestAnsvisEvent(
        FakeAuthenticator(),
        FakeIdempotencyDeriver(),
        FakeReceiptPort(outcome=ReceiptOutcome.DUPLICATE),
        metrics=metrics,
        now=fixed_now,
    ).execute(event_payload(), authorization_values=(), transport_secure=True)
    assert accepted.outcome is ReceiptOutcome.ACCEPTED
    assert duplicate.outcome is ReceiptOutcome.DUPLICATE

    with pytest.raises(AnsvisAdapterError, match="EVENT_IDEMPOTENCY_CONFLICT"):
        IngestAnsvisEvent(
            FakeAuthenticator(),
            FakeIdempotencyDeriver(),
            ConflictReceiptPort(),
            metrics=metrics,
            now=fixed_now,
        ).execute(event_payload(), authorization_values=(), transport_secure=True)
    invalid = event_payload()
    invalid["event_type"] = "unknown.event"
    with pytest.raises(AnsvisAdapterError, match="EVENT_TYPE_UNSUPPORTED"):
        IngestAnsvisEvent(
            FakeAuthenticator(),
            FakeIdempotencyDeriver(),
            FakeReceiptPort(),
            metrics=metrics,
            now=fixed_now,
        ).execute(invalid, authorization_values=(), transport_secure=True)

    assert metrics.values == [
        ("event_ingestion_total", "accepted"),
        ("event_ingestion_total", "duplicate"),
        ("event_ingestion_total", "conflict"),
        ("event_ingestion_total", "rejected"),
    ]
    assert (
        IngestAnsvisEvent(
            FakeAuthenticator(),
            FakeIdempotencyDeriver(),
            FakeReceiptPort(),
            metrics=FakeMetrics(fail=True),
            now=fixed_now,
        )
        .execute(event_payload(), authorization_values=(), transport_secure=True)
        .outcome
        is ReceiptOutcome.ACCEPTED
    )


def test_source_mismatch_fails_before_receipt() -> None:
    receipts = FakeReceiptPort()
    service = IngestAnsvisEvent(
        FakeAuthenticator("ansvis.test.other"), FakeIdempotencyDeriver(), receipts, now=fixed_now
    )

    with pytest.raises(AnsvisAdapterError, match="EVENT_SOURCE_UNAUTHORIZED"):
        service.execute(event_payload(), authorization_values=(), transport_secure=False)

    assert receipts.events == []


@pytest.mark.parametrize(
    ("tenant_ref", "school_ref"),
    [
        ("tenant_test_other_0001", "school_test_0001"),
        ("tenant_test_0001", "school_test_other_0001"),
    ],
)
def test_authoritative_tenant_and_school_binding_fails_before_receipt(
    tenant_ref: str, school_ref: str
) -> None:
    receipts = FakeReceiptPort()
    service = IngestAnsvisEvent(
        FakeAuthenticator(tenant_ref=tenant_ref, school_ref=school_ref),
        FakeIdempotencyDeriver(),
        receipts,
        now=fixed_now,
    )

    with pytest.raises(AnsvisAdapterError, match="EVENT_SOURCE_MAPPING_DENIED"):
        service.execute(event_payload(), authorization_values=(), transport_secure=True)

    assert receipts.events == []


def test_unavailable_receipt_port_never_acknowledges() -> None:
    service = IngestAnsvisEvent(
        FakeAuthenticator(),
        FakeIdempotencyDeriver(),
        UnavailableDurableReceiptPort(),
        now=fixed_now,
    )

    with pytest.raises(AnsvisAdapterError, match="EVENT_DURABLE_RECEIPT_UNAVAILABLE"):
        service.execute(event_payload(), authorization_values=(), transport_secure=False)


def test_unavailable_idempotency_deriver_never_reaches_receipt() -> None:
    receipts = FakeReceiptPort()
    service = IngestAnsvisEvent(
        FakeAuthenticator(), UnavailableIdempotencyDeriver(), receipts, now=fixed_now
    )

    with pytest.raises(AnsvisAdapterError, match="EVENT_DURABLE_RECEIPT_UNAVAILABLE"):
        service.execute(event_payload(), authorization_values=(), transport_secure=True)

    assert receipts.events == []


def test_unconfirmed_receipt_never_acknowledges() -> None:
    service = IngestAnsvisEvent(
        FakeAuthenticator(),
        FakeIdempotencyDeriver(),
        FakeReceiptPort(committed=False),
        now=fixed_now,
    )

    with pytest.raises(AnsvisAdapterError, match="EVENT_DURABLE_RECEIPT_UNAVAILABLE"):
        service.execute(event_payload(), authorization_values=(), transport_secure=False)


def test_receipt_must_echo_the_committed_idempotency_identity() -> None:
    service = IngestAnsvisEvent(
        FakeAuthenticator(),
        FakeIdempotencyDeriver(),
        InconsistentReceiptPort(),
        now=fixed_now,
    )

    with pytest.raises(AnsvisAdapterError, match="EVENT_DURABLE_RECEIPT_UNAVAILABLE"):
        service.execute(event_payload(), authorization_values=(), transport_secure=True)


@pytest.mark.parametrize(
    ("event_time", "expected_code"),
    [
        ("2029-12-31T23:54:59Z", "TIME_REPLAY_WINDOW_EXCEEDED"),
        ("2030-01-01T00:00:31Z", "TIME_EVENT_FUTURE"),
    ],
)
def test_use_case_enforces_replay_window(event_time: str, expected_code: str) -> None:
    payload = event_payload()
    payload["event_time"] = event_time
    receipts = FakeReceiptPort()
    idempotency = FakeIdempotencyDeriver()
    service = IngestAnsvisEvent(FakeAuthenticator(), idempotency, receipts, now=fixed_now)

    with pytest.raises(AnsvisAdapterError) as raised:
        service.execute(payload, authorization_values=(), transport_secure=False)

    assert raised.value.code == expected_code
    assert idempotency.events == []
    assert receipts.events == []
