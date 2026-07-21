from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path

import pytest
from ansvis_adapter.application.ports import (
    AuthenticatedSource,
    DurableReceipt,
    ReceiptOutcome,
    SourceAuthRequest,
)
from ansvis_adapter.application.service import IngestAnsvisEvent
from ansvis_adapter.domain.errors import AnsvisAdapterError
from ansvis_adapter.domain.idempotency import IdempotencyDescriptor
from ansvis_adapter.domain.models import NormalizedAnsvisEvent
from ansvis_adapter.infrastructure.idempotency import ContractIdempotencyDeriver

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
EVENT_FIXTURE = REPOSITORY_ROOT / "packages" / "test-fixtures" / "ansvis" / "event.synthetic.json"
CASE_FIXTURE = (
    REPOSITORY_ROOT
    / "packages"
    / "test-fixtures"
    / "ansvis"
    / "event-contract-cases.synthetic.json"
)
RECEIVED_AT = datetime(2030, 1, 1, 0, 0, 10, tzinfo=UTC)
FALLBACK_KEY = hashlib.sha256(b"SYNTHETIC_TEST_DATA_ONLY:contract-matrix-fallback-key").digest()


def _object(value: object) -> dict[str, object]:
    assert isinstance(value, dict)
    assert all(isinstance(key, str) for key in value)
    return value


def _objects(value: object) -> list[dict[str, object]]:
    assert isinstance(value, list)
    return [_object(item) for item in value]


def _load(path: Path) -> dict[str, object]:
    document: object = json.loads(path.read_text(encoding="utf-8"))
    result = _object(document)
    assert result.get("_fixture") == "SYNTHETIC_TEST_DATA_ONLY"
    return result


def _set_path(document: dict[str, object], dotted_path: str, value: object) -> None:
    parts = dotted_path.split(".")
    target = document
    for part in parts[:-1]:
        target = _object(target[part])
    target[parts[-1]] = value


def _remove_path(document: dict[str, object], dotted_path: str) -> None:
    parts = dotted_path.split(".")
    target = document
    for part in parts[:-1]:
        target = _object(target[part])
    target.pop(parts[-1], None)


def _mutated(base: dict[str, object], case: dict[str, object]) -> dict[str, object]:
    document = deepcopy(base)
    for path, value in _object(case.get("set", {})).items():
        _set_path(document, path, value)
    remove = case.get("remove", [])
    assert isinstance(remove, list)
    for path in remove:
        assert isinstance(path, str)
        _remove_path(document, path)
    return document


class SyntheticAuthenticator:
    def authenticate(self, request: SourceAuthRequest) -> AuthenticatedSource:
        return AuthenticatedSource(
            source_namespace=request.declared_source_namespace,
            subject_ref="source_subject_test_matrix_0001",
            tenant_ref="tenant_test_0001",
            school_ref="school_test_0001",
        )


class SyntheticFallbackKeys:
    def key_for(self, version: str) -> bytes | None:
        return FALLBACK_KEY if version == "ansvis_fallback_idempotency_v1" else None


class EchoReceiptPort:
    def __init__(self) -> None:
        self.event_types: list[str] = []

    def record(
        self,
        event: NormalizedAnsvisEvent,
        source: AuthenticatedSource,
        idempotency: IdempotencyDescriptor,
    ) -> DurableReceipt:
        assert event.tenant_ref == source.tenant_ref
        self.event_types.append(event.event_type.value)
        return DurableReceipt(
            receipt_id="receipt_test_matrix_0001",
            outcome=ReceiptOutcome.ACCEPTED,
            commit_confirmed=True,
            idempotency_key=idempotency.idempotency_key,
            canonical_fingerprint=idempotency.canonical_fingerprint,
        )


def test_shared_sanitized_schema_matrix_matches_the_application_boundary() -> None:
    event_fixture = _load(EVENT_FIXTURE)
    case_fixture = _load(CASE_FIXTURE)
    base = _object(event_fixture["request"])

    for case in _objects(case_fixture["schema_cases"]):
        case_code = case.get("case_code")
        expected_result = case.get("expected_result")
        assert isinstance(case_code, str)
        assert expected_result in {"accept", "reject"}
        payload = _mutated(base, case)
        receipts = EchoReceiptPort()
        service = IngestAnsvisEvent(
            SyntheticAuthenticator(),
            ContractIdempotencyDeriver(fallback_keys=SyntheticFallbackKeys()),
            receipts,
            now=lambda: RECEIVED_AT,
        )

        if expected_result == "accept":
            receipt = service.execute(payload, authorization_values=(), transport_secure=True)
            assert receipt.outcome is ReceiptOutcome.ACCEPTED, case_code
            assert receipts.event_types == [payload["event_type"]], case_code
            continue

        expected_code = case.get("expected_error_code")
        assert isinstance(expected_code, str)
        with pytest.raises(AnsvisAdapterError) as captured:
            service.execute(payload, authorization_values=(), transport_secure=True)
        assert captured.value.code == expected_code, case_code
        assert str(captured.value) == expected_code, case_code
        assert receipts.event_types == [], case_code
