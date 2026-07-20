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
from ansvis_adapter.domain.models import NormalizedAnsvisEvent
from ansvis_adapter.infrastructure.unavailable import UnavailableDurableReceiptPort


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


class FakeReceiptPort:
    def __init__(self, *, committed: bool = True) -> None:
        self.committed = committed
        self.events: list[NormalizedAnsvisEvent] = []

    def record(self, event: NormalizedAnsvisEvent, source: AuthenticatedSource) -> DurableReceipt:
        assert source.subject_ref == "source_subject_test_0001"
        self.events.append(event)
        return DurableReceipt(
            receipt_id="receipt_test_ansvis_0001",
            outcome=ReceiptOutcome.ACCEPTED,
            commit_confirmed=self.committed,
        )


def fixed_now() -> datetime:
    return datetime(2030, 1, 1, tzinfo=UTC)


def test_use_case_authenticates_before_record_and_returns_committed_receipt() -> None:
    auth = FakeAuthenticator()
    receipts = FakeReceiptPort()
    service = IngestAnsvisEvent(auth, receipts, now=fixed_now)

    receipt = service.execute(event_payload(), authorization_values=(), transport_secure=False)

    assert receipt.outcome is ReceiptOutcome.ACCEPTED
    assert len(auth.requests) == 1
    assert len(receipts.events) == 1


def test_source_mismatch_fails_before_receipt() -> None:
    receipts = FakeReceiptPort()
    service = IngestAnsvisEvent(FakeAuthenticator("ansvis.test.other"), receipts, now=fixed_now)

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
        FakeAuthenticator(tenant_ref=tenant_ref, school_ref=school_ref), receipts, now=fixed_now
    )

    with pytest.raises(AnsvisAdapterError, match="EVENT_SOURCE_MAPPING_DENIED"):
        service.execute(event_payload(), authorization_values=(), transport_secure=True)

    assert receipts.events == []


def test_unavailable_receipt_port_never_acknowledges() -> None:
    service = IngestAnsvisEvent(FakeAuthenticator(), UnavailableDurableReceiptPort(), now=fixed_now)

    with pytest.raises(AnsvisAdapterError, match="EVENT_DURABLE_RECEIPT_UNAVAILABLE"):
        service.execute(event_payload(), authorization_values=(), transport_secure=False)


def test_unconfirmed_receipt_never_acknowledges() -> None:
    service = IngestAnsvisEvent(
        FakeAuthenticator(), FakeReceiptPort(committed=False), now=fixed_now
    )

    with pytest.raises(AnsvisAdapterError, match="EVENT_DURABLE_RECEIPT_UNAVAILABLE"):
        service.execute(event_payload(), authorization_values=(), transport_secure=False)


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
    service = IngestAnsvisEvent(FakeAuthenticator(), receipts, now=fixed_now)

    with pytest.raises(AnsvisAdapterError) as raised:
        service.execute(payload, authorization_values=(), transport_secure=False)

    assert raised.value.code == expected_code
    assert receipts.events == []
